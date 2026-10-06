import json
import socket
import sqlite3
import tempfile
import unittest
import subprocess
import sys
from unittest.mock import patch
from pathlib import Path
from contextlib import closing


class FriendTestPackageTests(unittest.TestCase):
    def test_private_config_preserves_keys_and_uses_empty_package_libraries(self):
        from tools.build_portable_release import friend_test_config
        original = {'tmdb_key': 'private-test-key', 'movies_dirs': ['E:/Movies'],
                    'tv_roots': ['G:/TV'], 'user_data_dir': 'C:/private/data',
                    'ollama_model': 'nemotron-3-super:cloud', 'player': {'providers': {'key': 'secret'}}}
        copied = friend_test_config(original)
        self.assertEqual(copied['tmdb_key'], original['tmdb_key'])
        self.assertEqual(copied['player'], original['player'])
        self.assertEqual(copied['ollama_model'], original['ollama_model'])
        self.assertEqual(copied['movies_dirs'], ['library/movies'])
        self.assertEqual(copied['tv_roots'], ['library/tv'])
        self.assertEqual(copied['user_data_dir'], 'data')
        self.assertEqual(copied['qbt_webui_port'], 18686)
        self.assertEqual(original['movies_dirs'], ['E:/Movies'])

    def test_relocation_rebases_owned_paths_and_preserves_friend_external_paths(self):
        from tools.friend_test_launcher import prepare_config
        with tempfile.TemporaryDirectory(prefix='cp friend spaces ') as tmp:
            old = Path(tmp) / 'old folder'
            new = Path(tmp) / 'new folder'
            new.mkdir()
            external = Path(tmp) / 'friends own TV'
            cfg = {'movies_dir': str(old / 'library/movies'), 'movies_dirs': [str(old / 'library/movies')],
                   'tv_roots': [str(external)], 'user_data_dir': str(old / 'data'),
                   'tmdb_cache_dir': str(old / 'cache'), 'tmdb_key': 'keep-secret'}
            (new / 'config.json').write_text(json.dumps(cfg))
            (new / 'data').mkdir()
            (new / 'data/friend-root.json').write_text(json.dumps({'root': str(old)}))
            result = prepare_config(new)
            self.assertEqual(result['movies_dirs'], [str(new / 'library/movies')])
            self.assertEqual(result['tv_roots'], [str(external)])
            self.assertEqual(result['user_data_dir'], str(new / 'data'))
            self.assertEqual(result['tmdb_key'], 'keep-secret')

    def test_busy_port_fails_without_closing_existing_listener(self):
        from tools.friend_test_launcher import require_free_ports
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            listener.listen()
            port = listener.getsockname()[1]
            with self.assertRaisesRegex(RuntimeError, str(port)):
                require_free_ports({'CP': port})
            with socket.create_connection(('127.0.0.1', port), timeout=1):
                pass

    def test_snapshot_is_consistent_and_repoints_proxy_without_changing_original(self):
        from tools.build_portable_release import copy_prowlarr_settings
        with tempfile.TemporaryDirectory() as tmp:
            source, dest = Path(tmp) / 'source', Path(tmp) / 'dest'
            source.mkdir()
            (source / 'config.xml').write_text('<Config><ApiKey>private-key</ApiKey><Port>9696</Port><UrlBase>/prowlarr</UrlBase></Config>')
            with closing(sqlite3.connect(source / 'prowlarr.db')) as db:
                db.execute('CREATE TABLE IndexerProxies (Id INTEGER PRIMARY KEY, Implementation TEXT, Settings TEXT)')
                db.execute('INSERT INTO IndexerProxies VALUES (1, ?, ?)', ('FlareSolverr', '{"host":"http://localhost:8191"}'))
                db.commit()
            copy_prowlarr_settings(source, dest)
            with closing(sqlite3.connect(dest / 'prowlarr.db')) as db:
                self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
                self.assertEqual(json.loads(db.execute('SELECT Settings FROM IndexerProxies').fetchone()[0])['host'], 'http://127.0.0.1:18191/')
            with closing(sqlite3.connect(source / 'prowlarr.db')) as db:
                self.assertIn('8191', db.execute('SELECT Settings FROM IndexerProxies').fetchone()[0])
            import xml.etree.ElementTree as ET
            config = ET.parse(dest / 'config.xml').getroot()
            self.assertEqual(config.findtext('ApiKey'), 'private-key')
            self.assertEqual(config.findtext('Port'), '19696')
            self.assertEqual(config.findtext('BindAddress'), '127.0.0.1')

    def test_ollama_environment_does_not_use_host_identity(self):
        from tools.friend_test_launcher import ollama_environment
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = ollama_environment(root)
            self.assertEqual(env['USERPROFILE'], str(root / 'data/ollama-home'))
            self.assertEqual(env['OLLAMA_MODELS'], str(root / 'data/ollama-models'))
            self.assertEqual(env['OLLAMA_HOST'], '127.0.0.1:21434')

    def test_portable_catalog_is_inside_data_and_has_stable_name_after_relocation(self):
        from services.catalog_repository import catalog_database_path
        with tempfile.TemporaryDirectory() as tmp, patch.dict('os.environ', {'CP_PORTABLE_DATA': '1'}):
            old, new = Path(tmp) / 'old/data', Path(tmp) / 'new/data'
            self.assertEqual(catalog_database_path(old), old / 'catalog.sqlite')
            self.assertEqual(catalog_database_path(new), new / 'catalog.sqlite')

    def test_runtime_environment_isolates_actual_catalog_and_poster_storage(self):
        from tools.friend_test_launcher import cp_environment
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = cp_environment(root)
            self.assertEqual(env['LOCALAPPDATA'], str(root / 'data/localappdata'))
            self.assertEqual(env['CP_PORTABLE_DATA'], '1')

    def test_cached_poster_survives_moving_used_package(self):
        from services.catalog_repository import CatalogRepository
        from services.media_assets import MediaAssetService
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            old, new = Path(tmp) / 'old', Path(tmp) / 'new'
            repository = CatalogRepository(old / 'data', database_path=old / 'data/catalog.sqlite')
            service = MediaAssetService(repository, old / 'data/localappdata/Metadata')
            checksum = 'a' * 64
            asset_path = service._final_path(checksum, 'image/png')
            asset_path.parent.mkdir(parents=True, exist_ok=True)
            asset_path.write_bytes(b'fixture-poster')
            with repository.store.transaction() as db:
                db.execute("INSERT INTO media_assets(asset_key,asset_type,provider,source_url,status,local_path,checksum,mime_type,byte_size,width,height,retention_class,created_at,updated_at) VALUES('fixture','poster','tmdb','https://example.com/p.png','ready',?,?, 'image/png',14,1,1,'saved',0,0)", (str(asset_path), checksum))
            repository.close()
            shutil.move(str(old), str(new))
            moved = CatalogRepository(new / 'data', database_path=new / 'data/catalog.sqlite')
            try:
                MediaAssetService(moved, new / 'data/localappdata/Metadata')
                with closing(moved.store.connect()) as db:
                    actual = Path(db.execute("SELECT local_path FROM media_assets WHERE asset_key='fixture'").fetchone()[0])
                self.assertTrue(actual.is_file())
                self.assertTrue(actual.is_relative_to(new))
            finally:
                moved.close()

    def test_owned_process_is_stopped_on_startup_failure(self):
        from tools.friend_test_launcher import OwnedProcesses, wait_ready
        with tempfile.TemporaryDirectory() as tmp:
            owned = OwnedProcesses(tmp)
            try:
                child = owned.start('fixture', [sys.executable, '-c', 'import time; time.sleep(120)'], tmp)
                import urllib.error
                with patch('tools.friend_test_launcher.urllib.request.urlopen', side_effect=urllib.error.URLError('fixture unavailable')), self.assertRaisesRegex(RuntimeError, 'timed out'):
                    wait_ready(child, 'fixture', 'http://127.0.0.1:1/', timeout=.1)
            finally:
                owned.close()
            self.assertIsNotNone(child.poll())
            # Windows venv startup creates a base-interpreter descendant.
            (Path(tmp) / 'fixture.log').unlink()

    def test_private_assembly_preserves_settings_and_binaries_without_host_data(self):
        from tools.build_portable_release import build_friend_test_folder
        from tests.player_runtime_fixture import create_player_runtime_bundle
        import shutil
        with tempfile.TemporaryDirectory(prefix='cp friend assemble ') as tmp:
            root, out = Path(tmp) / 'source', Path(tmp) / 'private test'
            root.mkdir()
            (root / 'package.json').write_text('{"version":"9.9.9"}')
            (root / 'config.json').write_text(json.dumps({'tmdb_key': 'fixture-secret', 'prowlarr_key': 'api',
                                                         'movies_dirs': ['E:/Movies'], 'ollama_model': 'model:cloud'}))
            for name in ('AGENTS.md', '.gitignore'):
                (root / name).write_text('fixture')
            (root / 'tools').mkdir()
            actual_tools = Path(__file__).resolve().parents[1] / 'tools'
            for name in ('friend_test_run.bat', 'friend_test_signin.bat', 'friend_test_stop.bat', 'friend_test_handover.md'):
                shutil.copy2(actual_tools / name, root / 'tools' / name)
            (root / 'tests').mkdir()
            (root / 'data').mkdir()
            (root / 'data/jobs.json').write_text('private-live-job')
            (root / 'data/qbittorrent/versions/5.2.2').mkdir(parents=True)
            (root / 'data/qbittorrent/versions/5.2.2/qbittorrent.exe').write_bytes(b'qbt')
            player = create_player_runtime_bundle(root / 'runtime/player/versions', app_version='9.9.9')
            (root / 'runtime/player/current.json').write_text('{"schema":"cinema-paradiso-player-selector-v1","bundle_version":"player-test-1"}')
            ollama, prowlarr, flare = [Path(tmp) / name for name in ('ollama', 'prowlarr', 'flare')]
            (ollama / 'lib').mkdir(parents=True)
            (ollama / 'ollama.exe').write_bytes(b'ollama')
            (ollama / 'lib/backend.dll').write_bytes(b'backend')
            (prowlarr / 'bin').mkdir(parents=True)
            (prowlarr / 'bin/Prowlarr.Console.exe').write_bytes(b'prowlarr')
            (prowlarr / 'config.xml').write_text('<Config><ApiKey>api</ApiKey></Config>')
            with closing(sqlite3.connect(prowlarr / 'prowlarr.db')) as db:
                db.execute('CREATE TABLE IndexerProxies (Id INTEGER, Implementation TEXT, Settings TEXT)')
                db.commit()
            (flare / '_internal/chrome').mkdir(parents=True)
            (flare / 'flaresolverr.exe').write_bytes(b'flare')
            (flare / '_internal/chrome/chrome.exe').write_bytes(b'browser')
            ffmpeg = Path(tmp) / 'ffmpeg.exe'
            ffmpeg.write_bytes(b'ffmpeg')
            dist = Path(tmp) / 'dist'
            dist.mkdir()
            (dist / 'index.html').write_text('compiled-ui')
            with patch('tools.build_portable_release.subprocess.check_output', return_value='checkpoint\n'):
                build_friend_test_folder(root, out, ollama_source=ollama, prowlarr_source=prowlarr,
                    flaresolverr_source=flare, ffmpeg_source=ffmpeg, dist_source=dist)
            config = json.loads((out / 'config.json').read_text())
            self.assertEqual(config['tmdb_key'], 'fixture-secret')
            self.assertEqual((out / 'dist/index.html').read_text(), 'compiled-ui')
            self.assertTrue((out / 'runtime/flaresolverr/_internal/chrome/chrome.exe').is_file())
            self.assertTrue((out / 'CODEX-HANDOVER.md').is_file())
            self.assertTrue((out / 'Stop CP.bat').is_file())
            self.assertFalse((out / 'data/jobs.json').exists())
            self.assertFalse((out / 'data/ollama-home/.ollama/id_ed25519').exists())
            self.assertFalse((out / '.git').exists())
            with self.assertRaises(FileExistsError):
                build_friend_test_folder(root, out, ollama_source=ollama, prowlarr_source=prowlarr,
                    flaresolverr_source=flare, ffmpeg_source=ffmpeg, dist_source=dist)


if __name__ == '__main__':
    unittest.main()
