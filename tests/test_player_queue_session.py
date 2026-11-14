import unittest
import sqlite3

from services.player_config import PlayerConfig
from services.player_manager import PlayerManager, PlayerSession
from services.player_queue import PlayerQueue
from services.player_protocol import validate_message, PlayerProtocolError
from tests.test_player_manager import FakeRuntime, FakeProcess, EventTransport, FakePlaybackHistory


class QueueSessionTests(unittest.TestCase):
    def setUp(self):
        self.history = FakePlaybackHistory()
        self.media = {key: {'path_key': key, 'path': 'C:/' + key + '.mkv', 'title': key}
                      for key in ['a', 'b', 'c']}
        self.manager = PlayerManager(PlayerConfig(), FakeRuntime(), self.media.__getitem__,
                                     playback_history=self.history,
                                     queue_provider=PlayerQueue(lambda _: {'items': [
                                         {'path_key': key, 'title': key, 'available': key != 'b', 'reason': 'Missing' if key == 'b' else ''}
                                         for key in self.media]}))
        self.session = PlayerSession('test', FakeProcess(), EventTransport([]), lambda *_: None,
                                     media=self.media['a'], playback_context={'media': self.media['a']})
        self.session.queue = self.manager.queue_provider.snapshot(self.media['a'])
        self.manager._active = self.session

    def event(self, kind, generation=1, **payload):
        self.manager._handle_event(self.session, {'type': kind, 'sequence': 3,
                                                  'media_generation': generation, **payload})

    def test_unavailable_next_is_not_silently_skipped(self):
        self.event('playback.state', state='ended')
        self.event('queue.select', path_key='b', automatic=True)
        self.assertEqual(self.history.started, [])
        self.assertEqual(self.session.media['path_key'], 'a')

    def test_manual_selection_reuses_window_and_stale_progress_is_ignored(self):
        self.event('queue.select', path_key='c', automatic=False)
        self.assertEqual(self.session.media['path_key'], 'c')
        self.assertEqual(self.session.media_generation, 2)
        self.assertEqual(self.history.started[-1][0]['path_key'], 'c')
        self.assertFalse(self.history.started[-1][1])
        before = len(self.history.events)
        self.event('progress', generation=1, position_ms=999, duration_ms=1000, paused=True)
        self.assertEqual(len(self.history.events), before)
        self.assertEqual(self.session.transport.sent[-1]['type'], 'load')

    def test_automatic_selection_requires_actual_end_and_immediate_neighbor(self):
        self.event('queue.select', path_key='c', automatic=True)
        self.assertEqual(self.history.started, [])
        self.event('playback.state', state='ended')
        self.event('queue.select', path_key='c', automatic=True)
        self.assertEqual(self.history.started, [])

    def test_duplicate_manual_request_from_old_generation_cannot_load_twice(self):
        self.event('queue.select', path_key='c', automatic=False)
        self.event('queue.select', path_key='c', automatic=False)
        self.assertEqual(len(self.history.started), 1)

    def test_unknown_keys_never_reach_media_resolver(self):
        self.event('queue.select', path_key='C:/arbitrary.mkv', automatic=False)
        self.assertEqual(self.history.started, [])

    def test_autoplay_setting_persists_in_existing_config(self):
        self.event('player.preferences', autoplay=False)
        self.assertFalse(self.manager.player_config.storage_payload()['autoplay'])

    def test_preference_save_error_does_not_disconnect_playback(self):
        def fail(): raise OSError('disk unavailable')
        self.manager.persist_config = fail
        self.event('player.preferences', autoplay=False)
        self.assertIs(self.manager._active, self.session)
        self.assertFalse(self.session.transport.closed)
        self.assertEqual(self.session.transport.sent[-1]['type'], 'queue.error')

    def test_history_database_failure_during_switch_keeps_current_file(self):
        for method in ('flush_session', 'begin_session'):
            with self.subTest(method=method):
                original = getattr(self.history, method)
                def fail(*args, **kwargs): raise sqlite3.OperationalError('database is locked')
                setattr(self.history, method, fail)
                self.event('queue.select', path_key='c', automatic=False)
                self.assertEqual(self.session.media['path_key'], 'a')
                self.assertEqual(self.session.media_generation, 1)
                self.assertFalse(self.session.transition_pending)
                self.assertEqual(self.session.transport.sent[-1]['type'], 'queue.error')
                setattr(self.history, method, original)

    def test_protocol_rejects_invalid_generation_or_automatic_value(self):
        base = {'type': 'queue.select', 'protocol': 1, 'session_id': 'x', 'sequence': 1,
                'path_key': 'a', 'automatic': False, 'media_generation': 1}
        self.assertEqual(validate_message(base), base)
        for field, value in [('media_generation', True), ('media_generation', 0), ('automatic', 'yes')]:
            with self.subTest(field=field, value=value), self.assertRaises(PlayerProtocolError):
                validate_message({**base, field: value})


if __name__ == '__main__':
    unittest.main()
