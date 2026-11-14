import os
import secrets
import sqlite3
import subprocess
import threading
import time
import uuid
from pathlib import Path

from services.player_protocol import (
    PLAYER_PROTOCOL_VERSION,
    PlayerProtocolError,
    validate_message,
)
from services.player_runtime import PlayerRuntimeError
from services.player_windows_pipe import WindowsNamedPipeServer
from services.playback_history import PlaybackHistoryError
from services.subtitle_service import SubtitleServiceError
from services.player_catalog import PlayerMediaError
from services.player_queue import PlayerQueue


PLAYER_STARTUP_TIMEOUT_SECONDS = 10
PLAYER_EVENT_TIMEOUT_SECONDS = 1
PLAYER_SHUTDOWN_TIMEOUT_SECONDS = 5


class PlayerLaunchError(RuntimeError):
    pass


def safe_player_preferences(payload):
    allowed = {
        "preferred_audio_languages",
        "preferred_subtitle_languages",
        "prefer_forced_subtitles",
        "prefer_hearing_impaired_subtitles",
        "hardware_decoding",
        "hdr_handling",
        "tone_mapping",
        "audio_output",
        "audio_downmix",
        "audio_passthrough",
        "subtitle_style",
        "keyboard_shortcuts",
        "window_state",
        "autoplay",
    }
    return {
        key: value
        for key, value in dict(payload or {}).items()
        if key in allowed
    }


def launch_player_process(executable, environment):
    return subprocess.Popen(
        [str(executable)],
        cwd=str(Path(executable).parent),
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        shell=False,
    )


class PlayerSession:
    def __init__(
        self,
        session_id,
        process,
        transport,
        on_event,
        playback_context=None,
        media=None,
    ):
        self.session_id = session_id
        self.process = process
        self.transport = transport
        self.on_event = on_event
        self.playback_context = playback_context
        self.media = dict(media or {})
        self.media_generation = 1
        self.queue = {}
        self.ended = False
        self.transition_pending = False
        self.last_sequence = 0
        self.closed = threading.Event()
        self._send_sequence = 1
        self._send_lock = threading.Lock()
        self._reader = None
        self._closed_event_received = False
        self._subtitle_downloads = {}
        self._subtitle_downloads_lock = threading.Lock()

    def remember_subtitle_download(self, result_id, path):
        with self._subtitle_downloads_lock:
            self._subtitle_downloads[result_id] = path

    def subtitle_download_path(self, result_id):
        with self._subtitle_downloads_lock:
            return self._subtitle_downloads.get(result_id)

    def forget_subtitle_download(self, result_id):
        with self._subtitle_downloads_lock:
            self._subtitle_downloads.pop(result_id, None)

    def send(self, message_type, **payload):
        with self._send_lock:
            message = {
                "type": message_type,
                "protocol": PLAYER_PROTOCOL_VERSION,
                "session_id": self.session_id,
                "sequence": self._send_sequence,
                "media_generation": self.media_generation,
                **payload,
            }
            self._send_sequence += 1
            self.transport.send(message)

    def start_reader(self):
        self._reader = threading.Thread(
            target=self._read_events,
            name=f"cp-player-{self.session_id[:8]}",
            daemon=True,
        )
        self._reader.start()

    def _read_events(self):
        try:
            while not self.closed.is_set():
                if self.process.poll() is not None:
                    break
                try:
                    message = self.transport.receive(PLAYER_EVENT_TIMEOUT_SECONDS)
                except TimeoutError:
                    continue
                validated = validate_message(message, session_id=self.session_id)
                sequence = validated.get("sequence", 0)
                if sequence <= self.last_sequence:
                    continue
                self.last_sequence = sequence
                self.on_event(self, validated)
                if validated["type"] == "closed":
                    self._closed_event_received = True
                    break
        except (PlayerProtocolError, OSError, RuntimeError):
            pass
        finally:
            if not self._closed_event_received:
                try:
                    self.on_event(self, {
                        "type": "closed",
                        "protocol": PLAYER_PROTOCOL_VERSION,
                        "session_id": self.session_id,
                        "sequence": self.last_sequence + 1,
                        "reason": "transport_closed",
                    })
                except (OSError, RuntimeError):
                    pass
            self.closed.set()
            self.transport.close()

    def close(self):
        if self.closed.is_set():
            return
        try:
            self.send("close")
        except (OSError, RuntimeError):
            pass
        if not self.closed.wait(PLAYER_SHUTDOWN_TIMEOUT_SECONDS):
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.process.kill()
            self.closed.set()
            self.transport.close()


class PlayerManager:
    """Single authority for local-library playback mode, launch, IPC, and fallback."""

    def __init__(
        self,
        player_config,
        player_runtime,
        media_resolver,
        *,
        os_opener=None,
        transport_factory=None,
        process_launcher=None,
        playback_history=None,
        subtitle_service=None,
        persist_config=None,
        startup_timeout=PLAYER_STARTUP_TIMEOUT_SECONDS,
        queue_provider=None,
    ):
        self.player_config = player_config
        self.player_runtime = player_runtime
        self.media_resolver = media_resolver
        self.os_opener = os_opener or getattr(os, "startfile", None)
        self.transport_factory = transport_factory or WindowsNamedPipeServer
        self.process_launcher = process_launcher or launch_player_process
        self.playback_history = playback_history
        self.subtitle_service = subtitle_service
        self.persist_config = persist_config
        self.startup_timeout = float(startup_timeout)
        self.queue_provider = queue_provider or PlayerQueue(lambda _: {})
        self._lock = threading.RLock()
        self._active = None
        self._last_event = {}

    def active_status(self):
        with self._lock:
            session = self._active
            return {
                "active": bool(session and not session.closed.is_set()),
                "session_id": session.session_id if session and not session.closed.is_set() else "",
                "last_event": dict(self._last_event),
            }

    def active_media_path(self):
        with self._lock:
            session = self._active
            return str(session.media.get('path') or '') if session and not session.closed.is_set() else ''

    def play(self, path_key, *, restart=False):
        media = self.media_resolver(path_key)
        mode = self.player_config.public_payload()["mode"]
        if mode == "os_default":
            self._open_with_os(media["path"])
            return {"ok": True, "mode": "os_default", "fallback": False}
        try:
            return self._launch_built_in(media, restart=restart)
        except (PlayerRuntimeError, PlayerProtocolError, PlayerLaunchError, OSError, RuntimeError, TimeoutError):
            self._open_with_os(media["path"])
            return {
                "ok": True,
                "mode": "os_default",
                "fallback": True,
                "reason": "Cinema Paradiso Player could not start; the OS player was opened.",
            }

    def close_active(self):
        with self._lock:
            session = self._active
            self._active = None
        if session:
            session.close()

    def _open_with_os(self, path):
        if not self.os_opener:
            raise PlayerLaunchError("Operating-system playback is unavailable")
        try:
            self.os_opener(path)
        except OSError as error:
            raise PlayerLaunchError("The operating-system player could not open the file") from error

    def _launch_built_in(self, media, *, restart=False):
        runtime = self.player_runtime.resolve_bundle(verify_hashes=False)
        executable = runtime["bundle_root"] / "cp-player.exe"
        self.close_active()

        session_id = uuid.uuid4().hex
        token = secrets.token_urlsafe(32)
        pipe_name = f"cp-player-{session_id}"
        transport = self.transport_factory(pipe_name)
        environment = {
            key: value
            for key, value in os.environ.items()
            if key.upper() in {
                "SYSTEMROOT",
                "WINDIR",
                "TEMP",
                "TMP",
                "LOCALAPPDATA",
                "APPDATA",
            }
        }
        environment.update({
            "CP_PLAYER_PIPE": pipe_name,
            "CP_PLAYER_SESSION_ID": session_id,
            "CP_PLAYER_SESSION_TOKEN": token,
            "CP_PLAYER_PROTOCOL": str(PLAYER_PROTOCOL_VERSION),
        })
        process = None
        try:
            process = self.process_launcher(executable, environment)
            transport.accept(self.startup_timeout)
            hello = transport.receive(self.startup_timeout)
            validate_message(
                hello,
                expected_type="hello",
                session_id=session_id,
                token=token,
            )
            playback_context = (
                self.playback_history.begin_session(media, restart=restart)
                if self.playback_history
                else None
            )
            session = PlayerSession(
                session_id,
                process,
                transport,
                self._handle_event,
                playback_context=playback_context,
                media=media,
            )
            session.queue = self.queue_provider.snapshot(media)
            session.send(
                "load",
                media=media,
                queue=session.queue,
                start_position_ms=(
                    playback_context["start_position_ms"]
                    if playback_context
                    else 0
                ),
                playback_state={
                    "audio_track_fingerprint": (
                        playback_context.get("audio_track_fingerprint") or ""
                        if playback_context
                        else ""
                    ),
                    "subtitle_track_fingerprint": (
                        playback_context.get("subtitle_track_fingerprint") or ""
                        if playback_context
                        else ""
                    ),
                    "subtitle_delay_ms": (
                        playback_context.get("subtitle_delay_ms", 0)
                        if playback_context
                        else 0
                    ),
                },
                preferences=safe_player_preferences(
                    self.player_config.storage_payload()
                ),
            )
            ready = transport.receive(self.startup_timeout)
            validate_message(ready, session_id=session_id)
            if ready["type"] == "error" or not (
                ready["type"] == "ready" and ready.get("accepted") is True
            ):
                raise PlayerLaunchError("The native player rejected the playback session")
            session.last_sequence = ready.get("sequence", 0)
            with self._lock:
                self._active = session
                self._last_event = {
                    "type": "ready",
                    "received_at": time.time(),
                }
            session.start_reader()
            return {
                "ok": True,
                "mode": "built_in",
                "fallback": False,
                "session_id": session_id,
                "start_position_ms": (
                    playback_context["start_position_ms"]
                    if playback_context
                    else 0
                ),
            }
        except Exception:
            transport.close()
            if process and process.poll() is None:
                process.terminate()
            raise

    def _handle_event(self, session, message):
        kind = message['type']
        if kind not in {'window.state', 'closing', 'closed'}:
            if message.get('media_generation', 1) != session.media_generation:
                return
        if kind == 'queue.select':
            self._select_queue_item(session, message)
            return
        if kind == 'player.preferences':
            if self._active is session:
                try:
                    self.player_config.update({'autoplay': message['autoplay']})
                    if self.persist_config and self.persist_config() is False:
                        raise OSError('Preference save failed')
                except (OSError, RuntimeError, ValueError):
                    self._send_to_active(session, 'queue.error',
                                         message='Autoplay changed for this session, but its preference could not be saved.')
            return
        if kind == 'ready':
            session.transition_pending = False
        if kind == 'playback.state' and message.get('state') == 'ended':
            session.ended = True
        if message["type"] == "subtitle.search" and self.subtitle_service:
            generation = session.media_generation
            self.subtitle_service.search_async(
                session.session_id,
                session.media,
                lambda payload: self._send_to_active(
                    session,
                    "subtitle.results",
                    media_generation=generation,
                    **payload,
                ),
            )
        elif message["type"] == "subtitle.download" and self.subtitle_service:
            threading.Thread(
                target=self._download_subtitle,
                args=(session, message["result_id"], session.media_generation, dict(session.media)),
                name=f"cp-subtitle-download-{session.session_id[:8]}",
                daemon=True,
            ).start()
        elif message["type"] == "subtitle.save" and self.subtitle_service:
            threading.Thread(
                target=self._save_subtitle,
                args=(session, message["result_id"], session.media_generation, dict(session.media)),
                name=f"cp-subtitle-save-{session.session_id[:8]}",
                daemon=True,
            ).start()
        elif message["type"] == "window.state":
            try:
                self.player_config.update({"window_state": message["window_state"]})
                if self.persist_config:
                    self.persist_config()
            except (OSError, RuntimeError, ValueError):
                pass
        if self.playback_history:
            try:
                self.playback_history.handle_event(session, message)
            except (PlaybackHistoryError, OSError, RuntimeError, sqlite3.Error):
                # Playback remains available if a history write is temporarily
                # unavailable; the next bounded event can retry it.
                pass
        safe_event = {
            "type": message["type"],
            "sequence": message.get("sequence", 0),
            "received_at": time.time(),
        }
        if message["type"] == "playback.state":
            safe_event["state"] = message["state"]
        elif message["type"] == "progress":
            safe_event.update({
                "position_ms": int(message["position_ms"]),
                "duration_ms": int(message["duration_ms"]),
                "paused": message["paused"],
            })
        elif message["type"] == "error":
            safe_event.update({
                "code": message["code"],
                "message": message["message"],
            })
        with self._lock:
            if self._active is session:
                self._last_event = safe_event
                if message["type"] == "closed":
                    self._active = None

    def _send_to_active(self, session, message_type, **payload):
        with self._lock:
            active = (self._active is session and not session.closed.is_set()
                      and payload.get('media_generation', session.media_generation) == session.media_generation)
            if active:
                try:
                    session.send(message_type, **payload)
                except (OSError, RuntimeError):
                    pass

    def _select_queue_item(self, session, message):
        with self._lock:
            if (self._active is not session or session.closed.is_set() or session.transition_pending
                    or message.get('media_generation') != session.media_generation):
                return
            rows = session.queue.get('items') or []
            index = next((i for i, row in enumerate(rows) if row['path_key'] == message['path_key']), -1)
            current = session.queue.get('current_index', -1)
            automatic = message['automatic']
            if index < 0 or index == current:
                return
            if automatic and (not session.ended or index != current + 1
                              or not self.player_config.storage_payload()['autoplay']
                              or session.queue.get('autoplay_blocked_reason')
                              or session.media.get('shared_without_segments')):
                return
            item = rows[index]
            try:
                if not item['available']:
                    raise PlayerMediaError(item.get('reason') or 'The next file is unavailable')
                media = self.media_resolver(item['path_key'])
                if self.playback_history:
                    self.playback_history.flush_session(session)
                context = self.playback_history.begin_session(media, restart=automatic) if self.playback_history else None
            except (PlayerMediaError, LookupError, OSError, RuntimeError, PlaybackHistoryError, sqlite3.Error) as error:
                self._send_to_active(session, 'queue.error', message=str(error)[:1024] or 'The file is unavailable')
                return
            session.transition_pending = True
            session.ended = False
            session.media_generation += 1
            session.media = dict(media)
            session.playback_context = context
            # Retain the opening sequence; availability is revalidated on every selection.
            session.queue = {**session.queue, 'current_index': index}
            with session._subtitle_downloads_lock:
                session._subtitle_downloads.clear()
            session.send('load', media=media, queue=session.queue,
                         start_position_ms=(context or {}).get('start_position_ms', 0),
                         playback_state={key: (context or {}).get(key) or (0 if key == 'subtitle_delay_ms' else '')
                                         for key in ('audio_track_fingerprint', 'subtitle_track_fingerprint', 'subtitle_delay_ms')},
                         preferences=safe_player_preferences(self.player_config.storage_payload()))

    def _download_subtitle(self, session, result_id, generation, media):
        try:
            loaded = self.subtitle_service.download(
                session.session_id,
                result_id,
                media,
            )
            save_available = bool(loaded.pop("save_available", False))
            if save_available and session.media_generation == generation:
                session.remember_subtitle_download(result_id, loaded["path"])
            self._send_to_active(
                session,
                "subtitle.loaded",
                media_generation=generation,
                result_id=result_id,
                save_available=save_available,
                **loaded,
            )
        except SubtitleServiceError:
            self._send_to_active(
                session,
                "error",
                media_generation=generation,
                code="subtitle_download_failed",
                message="The selected subtitle could not be loaded.",
            )

    def _save_subtitle(self, session, result_id, generation, media):
        cached_path = session.subtitle_download_path(result_id)
        if not cached_path:
            self._send_to_active(
                session,
                "error",
                media_generation=generation,
                code="subtitle_save_failed",
                message="The selected subtitle is not available to save.",
            )
            return
        try:
            saved = self.subtitle_service.save_beside_movie(
                cached_path,
                media,
            )
            session.forget_subtitle_download(result_id)
            self._send_to_active(
                session,
                "subtitle.saved",
                media_generation=generation,
                result_id=result_id,
                path=saved["path"],
            )
        except SubtitleServiceError:
            self._send_to_active(
                session,
                "error",
                media_generation=generation,
                code="subtitle_save_failed",
                message="The selected subtitle could not be saved beside the movie.",
            )
