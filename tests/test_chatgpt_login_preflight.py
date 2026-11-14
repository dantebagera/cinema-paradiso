import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from services.chatgpt_transport import ChatGPTError
from tools.chatgpt_login_preflight import Preflight, validate_root, make_server


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='cp-chatgpt-', dir=os.environ['CP_TEST_ROOT'])
        self.addCleanup(self.temp.cleanup)
        self.auth = SimpleNamespace(start=lambda: {'attempt_id': 'fixture'},
            status=lambda attempt: {'state': 'complete', 'account_id': 'opaque', 'plan_enabled': True},
            close=lambda: None)
        self.calls = 0
        self.transport = SimpleNamespace(list_models=lambda selection: [{'slug': 'allowed', 'display_name': 'Allowed'}],
                                         run=self.infer)
        self.preflight = Preflight(self.temp.name, auth=self.auth, transport=self.transport)

    def infer(self, selection, **kwargs):
        self.calls += 1
        self.assertEqual(selection.model, 'allowed')
        self.assertEqual(kwargs['input_items'], [{'role': 'user', 'content': 'Say exactly: CP_CONNECTION_OK'}])
        self.assertEqual(kwargs['tools'], [])
        return SimpleNamespace(text='CP_CONNECTION_OK', response_id='resp_fixture')

    def connect(self):
        self.preflight.start()
        self.preflight.models()

    def test_explicit_connection_and_model_required_before_inference(self):
        with self.assertRaises(ChatGPTError):
            self.preflight.test('allowed')
        self.connect()
        with self.assertRaises(ChatGPTError):
            self.preflight.test('not-listed')
        self.assertEqual(self.calls, 0)
        self.assertEqual(self.preflight.test('allowed')['state'], 'passed')
        self.assertEqual(self.calls, 1)

    def test_persistent_guard_prevents_duplicate_and_restarted_inference(self):
        self.connect()
        self.preflight.test('allowed')
        for preflight in [self.preflight, Preflight(self.temp.name, auth=self.auth, transport=self.transport)]:
            with self.assertRaises(ChatGPTError):
                preflight.test('allowed')
        self.assertEqual(self.calls, 1)

    def test_uncertain_request_failure_still_spends_the_single_call(self):
        self.connect()
        self.transport.run = lambda *args, **kwargs: (_ for _ in ()).throw(ChatGPTError('network_error'))
        with self.assertRaises(ChatGPTError):
            self.preflight.test('allowed')
        self.assertEqual(self.preflight.status()['inference_calls'], 1)
        self.assertEqual(self.preflight.status()['qualification']['error']['code'], 'network_error')

    def test_production_and_temp_parent_roots_rejected(self):
        for path in [Path.cwd(), Path(tempfile.gettempdir()), Path(tempfile.gettempdir()) / 'other']:
            with self.assertRaises(ValueError):
                validate_root(path)

    def test_no_production_imports(self):
        import ast
        for path in ['tools/chatgpt_login_preflight.py', 'services/chatgpt_auth.py',
                     'services/chatgpt_credentials.py', 'services/chatgpt_transport.py']:
            tree = ast.parse(Path(path).read_text(encoding='utf-8'))
            imported = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
            self.assertFalse(any(name and (name == 'app' or 'iptv' in name or 'qbittorrent' in name) for name in imported))

    def test_diagnostic_error_remains_visible_in_status(self):
        server = make_server(self.preflight)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        import requests
        url = 'http://127.0.0.1:' + str(server.server_port)
        self.auth.start = lambda: (_ for _ in ()).throw(ChatGPTError('registration_not_admitted', status=403, request_id='req_test'))
        requests.post(url + '/start', json={}, headers={'X-CP-Preflight': server.csrf})
        state = requests.get(url + '/status').json()
        self.assertEqual(state['last_error'], {'code': 'registration_not_admitted', 'http_status': 403, 'request_id': 'req_test'})

    def test_browser_control_rejects_wrong_origin_host_and_csrf(self):
        import requests
        server = make_server(self.preflight)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        url = 'http://127.0.0.1:' + str(server.server_port)
        for headers in [{'Origin': 'https://evil.test'}, {'Host': 'evil.test'}, {'X-CP-Preflight': 'wrong'}]:
            response = requests.post(url + '/start', json={}, headers=headers)
            self.assertIn(response.status_code, (400, 403))
        self.assertIsNone(self.preflight.attempt_id)
        response = requests.post(url + '/start', json={}, headers={
            'Origin': url, 'X-CP-Preflight': server.csrf})
        self.assertEqual(response.status_code, 200)

