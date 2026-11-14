"""Whole-path checks supplement the feature-specific adverse-case suites."""
import unittest
import tempfile
import subprocess
import os
import sys
import json
from pathlib import Path
from types import SimpleNamespace
from urllib.error import URLError
from flask import Flask
from services.tv_routes import register_tv_routes


class FeatureMatrixTests(unittest.TestCase):
    def test_all_five_real_application_paths_and_nested_budget_under_blocked_network(self):
        with tempfile.TemporaryDirectory(prefix='cp-ai-matrix-') as root:
            env = dict(os.environ, CP_TEST_MODE='1', CP_TEST_ROOT=root,
                       CP_TEST_DIST_DIR=str(Path(root) / 'dist'), CP_PORT='5119')
            result = subprocess.run([sys.executable, '-m', 'tests.ai_provider_server', '--qualify'], env=env,
                                    capture_output=True, text=True, timeout=45)
            self.assertEqual(result.returncode, 0, (result.stdout + result.stderr)[-4000:])
            summary = json.loads(next(line.removeprefix('AI_MATRIX=') for line in result.stdout.splitlines() if line.startswith('AI_MATRIX=')))
            self.assertEqual(summary['features'], ['F1', 'F2', 'F3', 'F4', 'F5'])
            self.assertEqual(summary['nested_parent_requests'], 4)
            self.assertEqual(summary['saved_subset'], [2])
            self.assertGreaterEqual(summary['callable_tools'], 45)
    def test_tv_detail_keeps_local_identity_when_optional_online_display_enrichment_fails(self):
        def unavailable(*args, **kwargs):
            raise URLError('Synthetic offline metadata')
        owners = {'read': SimpleNamespace(detail=lambda identity: {'id': identity, 'tmdb_id': 900001, 'title': 'Harbor Signals'}),
                  'metadata': SimpleNamespace(key_provider=lambda: 'synthetic', preview=unavailable)}
        app = Flask('tv-ai-read-fixture')
        app.testing = True
        register_tv_routes(app, lambda: owners, lambda: True, None)
        response = app.test_client().get('/api/tv/series/1')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['title'], 'Harbor Signals')
        self.assertIn('unavailable', response.json['metadata_notice'])
