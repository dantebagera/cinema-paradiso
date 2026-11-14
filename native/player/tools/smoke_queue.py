"""Real native queue smoke with synthetic files and no production catalog/history."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from services.player_config import PlayerConfig
from services.player_manager import PlayerManager
from services.player_queue import PlayerQueue
from services.player_windows_pipe import WindowsNamedPipeServer


class ObservedTransport(WindowsNamedPipeServer):
    def receive(self, timeout):
        result = super().receive(timeout)
        if result.get('type') in {'error', 'ready'}:
            print(json.dumps({'native_event': result}), flush=True)
        return result


class Runtime:
    def __init__(self, root): self.root = root
    def resolve_bundle(self, verify_hashes=False): return {'bundle_root': self.root}


class History:
    def __init__(self): self.starts, self.events = [], []
    def begin_session(self, media, restart=False):
        self.starts.append({'key': media['path_key'], 'restart': restart})
        return {'media': dict(media), 'start_position_ms': 0}
    def handle_event(self, session, event):
        self.events.append({'key': session.media['path_key'], **event})
    def flush_session(self, session): pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--fixtures', type=Path, required=True)
    parser.add_argument('--interactive', action='store_true')
    args = parser.parse_args()
    args.fixtures.mkdir(parents=True, exist_ok=True)
    (args.fixtures / 'stop').unlink(missing_ok=True)
    history = History()
    files = ['a', 'b']
    media = {key: {'path_key': key, 'path': str((args.fixtures / f'{key}.mp4').resolve()),
                   'title': f'Harbor Signals · S02E0{index + 3} · Synthetic fixture',
                   'year': '2026', 'poster_reference': ''} for index, key in enumerate(files)}
    for row in media.values():
        if not Path(row['path']).is_file(): raise RuntimeError('Generate synthetic fixtures first')
    rows = [{'path_key': key, 'title': media[key]['title'], 'section': 'Season 2',
             'available': True} for key in files]
    rows.append({'path_key': 'missing', 'title': 'S02E05 · Missing episode', 'section': 'Season 2',
                 'available': False, 'reason': 'Episode is missing locally'})
    log = (args.fixtures / 'native-stderr.log').open('w', encoding='utf-8')
    processes = []
    def launch(exe, env):
        env['CP_PLAYER_CACHE_ROOT'] = str(args.fixtures / 'cache')
        process = subprocess.Popen([str(exe)], cwd=str(exe.parent), env=env,
                                   stdout=log, stderr=log, stdin=subprocess.DEVNULL,
                                   creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
        processes.append(process)
        return process
    config = PlayerConfig({'mode': 'built_in'})
    manager = PlayerManager(config, Runtime(args.runtime.resolve()), media.__getitem__,
                            transport_factory=ObservedTransport,
                            playback_history=history, process_launcher=launch,
                            queue_provider=PlayerQueue(lambda _: {'title': 'Harbor Signals', 'items': rows}),
                            os_opener=lambda _: (_ for _ in ()).throw(RuntimeError('Unexpected OS fallback')))
    started = time.monotonic()
    # Surface startup errors directly instead of hiding them behind OS fallback.
    result = manager._launch_built_in(media['a'])
    print(json.dumps({'launched': result, 'pid': processes[0].pid}), flush=True)
    try:
        deadline = started + (900 if args.interactive else 25)
        while time.monotonic() < deadline:
            active = manager._active
            state = {'active': bool(active), 'media': active.media if active else {},
                     'generation': active.media_generation if active else 0,
                     'starts': history.starts, 'events': history.events,
                     'config': {'autoplay': config.storage_payload()['autoplay'],
                                'window_state': config.storage_payload()['window_state']}}
            (args.fixtures / 'state.json').write_text(json.dumps(state, indent=2), encoding='utf-8')
            if args.interactive:
                if (args.fixtures / 'stop').exists() or not active: break
            else:
                ended = [e for e in history.events if e['type'] == 'playback.state' and e.get('state') == 'ended']
                if len(ended) >= 2:
                    time.sleep(6)  # prove the missing third item is never skipped or launched
                    break
            time.sleep(0.1)
        if not args.interactive:
            assert [r['key'] for r in history.starts] == ['a', 'b'], history.starts
            assert history.starts[1]['restart'] is True
            assert len(processes) == 1, 'File switch replaced the native window/process'
            assert sum(e['type'] == 'playback.state' and e.get('state') == 'ended' for e in history.events) == 2
            assert any(e['type'] == 'progress' and e['key'] == 'b' and e.get('position_ms', 0) > 0 for e in history.events)
            print(json.dumps({'ok': True, 'same_process': True, 'starts': history.starts,
                              'elapsed': round(time.monotonic() - started, 2)}), flush=True)
    finally:
        manager.close_active()
        for process in processes:
            try: process.wait(timeout=8)
            except subprocess.TimeoutExpired: process.terminate()
        log.close()


if __name__ == '__main__': main()
