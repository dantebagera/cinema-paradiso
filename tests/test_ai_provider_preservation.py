"""Provider regression evidence: frozen legacy owners and offline containment."""
import ast
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import unittest

from tests.ai_provider_server import OfflineGuard, validate_environment, capture_legacy


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/ai_provider_ollama_baseline.json'


class ProviderPreservationTests(unittest.TestCase):
    def test_offline_guard_refuses_network_including_live_local_services(self):
        with OfflineGuard():
            for address in [('api.openai.com', 443), ('127.0.0.1', 5000), ('127.0.0.1', 32400),
                            ('127.0.0.1', 18686), ('127.0.0.1', 11434)]:
                with self.assertRaises(RuntimeError):
                    socket.create_connection(address, timeout=0.01)
            with self.assertRaises(RuntimeError):
                subprocess.Popen(['unreachable-fixture-service'])

    def test_production_environment_cannot_be_used(self):
        with self.assertRaises(RuntimeError):
            validate_environment({'CP_TEST_MODE': '1', 'CP_TEST_ROOT': str(ROOT), 'CP_PORT': '5000'})
        with self.assertRaises(RuntimeError):
            validate_environment({'CP_TEST_MODE': '0'})

    def test_app_test_mode_network_block_survives_fixture_guard(self):
        import urllib.request
        with OfflineGuard():
            import app
        self.assertIs(urllib.request.urlopen, app._blocked_test_urlopen)

    def test_exact_frozen_ollama_functions_and_ui(self):
        baseline = json.loads(FIXTURE.read_text(encoding='utf-8'))
        for location, expected in baseline['functions'].items():
            file, name = location.split(':')
            source = (ROOT / file).read_text(encoding='utf-8-sig')
            function = next(n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.FunctionDef) and n.name == name)
            actual = hashlib.sha256(ast.get_source_segment(source, function).encode()).hexdigest()
            self.assertEqual(actual, expected, location)
        self.assertEqual(hashlib.sha256((ROOT / 'src/features/settings/ollamaModels.js').read_bytes()).hexdigest(),
                         baseline['ollama_models_sha256'])
        settings = (ROOT / 'src/features/settings/SettingsWorkspace.jsx').read_text(encoding='utf-8')
        card = settings[settings.rfind('<IntegrationCard', 0, settings.index('title="Ollama"')):]
        card = card[:card.index('\n        />') + len('\n        />')]
        self.assertEqual(hashlib.sha256(card.encode()).hexdigest(), baseline['ollama_card_sha256'])

    def test_legacy_request_output_and_repair_fixtures(self):
        expected = json.loads(FIXTURE.read_text(encoding='utf-8'))['wire']
        with OfflineGuard():
            self.assertEqual(capture_legacy(), expected)

