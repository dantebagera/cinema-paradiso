import unittest
from unittest.mock import Mock

from services.download_monitor import DownloadImportMonitor


class DownloadImportMonitorTest(unittest.TestCase):
    def test_success_is_recorded(self):
        manager = Mock()
        manager.process_completed.return_value = [{'state': 'imported'}]
        on_results = Mock()
        monitor = DownloadImportMonitor(lambda: manager, on_results, clock=lambda: 10)

        self.assertTrue(monitor.run_once())

        self.assertEqual(monitor.snapshot()['state'], 'healthy')
        self.assertEqual(monitor.snapshot()['processed_results'], 1)
        on_results.assert_called_once_with(manager, [{'state': 'imported'}])

    def test_failure_remains_visible_until_next_success(self):
        manager_factory = Mock(side_effect=RuntimeError('qBittorrent offline'))
        monitor = DownloadImportMonitor(manager_factory, Mock(), clock=lambda: 20)

        self.assertFalse(monitor.run_once())

        status = monitor.snapshot()
        self.assertEqual(status['state'], 'error')
        self.assertEqual(status['last_error'], 'qBittorrent offline')
        self.assertEqual(status['consecutive_errors'], 1)

    def test_disabled_monitor_does_not_touch_manager(self):
        manager_factory = Mock()
        monitor = DownloadImportMonitor(manager_factory, Mock(), clock=lambda: 30)

        self.assertFalse(monitor.run_once(enabled=False))

        self.assertEqual(monitor.snapshot()['state'], 'disabled')
        manager_factory.assert_not_called()


if __name__ == '__main__':
    unittest.main()
