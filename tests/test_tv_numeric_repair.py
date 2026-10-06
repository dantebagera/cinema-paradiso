"""One-time existing-library moves preserve identity, progress and recovery."""
from pathlib import Path
import importlib
import io
import json
import shutil
from contextlib import redirect_stdout
import tempfile
import unittest
from unittest.mock import patch

from services.tv_catalog_repository import TVCatalogRepository
from services.qbittorrent import QBittorrentJobStore
from services.verified_import import sha256


class TVNumericRepairTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.library = self.root / 'tv'
        self.library.mkdir()
        self.old = self.library / '12345'
        self.old.mkdir()
        self.home = self.library / 'Fixture'
        self.home.mkdir()
        (self.home / 'Season 01').mkdir()
        self.tv = TVCatalogRepository(self.root / 'tv.sqlite')
        self.series = self.tv.refresh({'tmdb_id': 12345, 'title': 'Fixture'}, [
            {'season_number': 1, 'episode_number': i, 'air_date': '2020-01-01'} for i in (1, 2)])
        self.tv.approve_path(self.old, 'folder', self.series)
        self.tv.approve_path(self.home, 'folder', self.series)
        self.files = []
        self.file_ids = []
        self.episodes = self.tv.episodes(self.series, 1)
        for i, ep in enumerate(self.episodes, 1):
            source = self.old / f'Fixture.S01E{i:02d}.mkv'
            source.write_bytes(f'episode {i}'.encode())
            self.files.append(source)
            self.file_ids.append(self.tv.bind_file(source, [ep['id']], {'quality_class': '1080p'}, [self.library]))
        self.tv.save_progress(self.episodes[0]['id'], self.file_ids[0], position_ms=123, duration_ms=1000)
        self.jobs = QBittorrentJobStore(self.root / 'jobs.json')
        self.staging = self.root / 'staging'
        self.staging.mkdir()
        rows = []
        for source in self.files:
            retained = self.staging / source.name
            retained.write_bytes(source.read_bytes())
            rows.append({'source': str(retained), 'target': str(source), 'temporary': str(source.with_suffix('.partial')),
                         'size': source.stat().st_size, 'sha256': sha256(source), 'state': 'published', 'method': 'copy'})
        self.jobs.upsert('a' * 40, {'media_type': 'tv', 'state': 'seed_complete', 'destination': str(self.old),
            'imported_paths': list(map(str, self.files)), 'preserving_import_plan': rows,
            'source_retained': True, 'import_mode': 'hardlink_copy', 'seeding_policy': {'seeding_mode': 'none'}})
        self.manifest = self.root / 'repair.json'

    def preview(self):
        module = importlib.import_module('tools.repair_tv_numeric_folders')
        return module, module.preview(self.tv, self.jobs, [self.library], {str(self.old): str(self.home)}, self.manifest)

    def apply(self, module):
        return module.apply(self.tv, self.jobs, [self.library], self.manifest, offline_check=lambda: None)

    def test_preserves_ids_progress_staging_and_job_policy(self):
        module, plan = self.preview()
        self.assertEqual(len(plan['moves']), 2)
        self.apply(module)
        self.assertFalse(self.old.exists())
        for source, file_id, ep in zip(self.files, self.file_ids, self.episodes):
            target = self.home / 'Season 01' / source.name
            self.assertTrue(target.exists())
            self.assertEqual(self.tv.file_binding(target)['id'], file_id)
            self.assertEqual(self.tv.binding_episode_ids(target), {ep['id']})
            self.assertTrue((self.staging / source.name).exists())
        self.assertEqual(self.tv.episodes(self.series, 1)[0]['position_ms'], 123)
        job = self.jobs.get('a' * 40)
        self.assertEqual(job['state'], 'seed_complete')
        self.assertEqual(job['import_mode'], 'hardlink_copy')
        self.assertTrue(job['source_retained'])
        self.assertEqual(job['destination'], str(self.home / 'Season 01'))
        self.assertTrue(all(Path(r['target']).exists() for r in job['preserving_import_plan']))
        self.assertEqual(self.tv.resolve_import_destination(self.series, 1, [self.library])['path'], str(self.home / 'Season 01'))

    def test_target_collision_and_unknown_neighbor_block_before_moves(self):
        target = self.home / 'Season 01' / self.files[0].name
        target.write_bytes(b'different content')
        with self.assertRaisesRegex(ValueError, 'collision'):
            self.preview()
        self.assertTrue(self.files[0].exists())
        target.unlink()
        (self.old / 'unknown.txt').write_text('preserve')
        with self.assertRaisesRegex(ValueError, 'unbound|Unknown'):
            self.preview()

    def test_changed_source_and_running_cp_block_before_move(self):
        module, _ = self.preview()
        with self.assertRaisesRegex(ValueError, 'running'):
            module.apply(self.tv, self.jobs, [self.library], self.manifest,
                         offline_check=lambda: (_ for _ in ()).throw(ValueError('CP is running')))
        self.files[0].write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.apply(module)
        self.assertTrue(self.files[1].exists())

    def test_pre_catalog_failure_reverses_only_owned_moves(self):
        module, _ = self.preview()
        rename = module.os.rename
        def fail(source, target):
            if Path(source) == self.files[1]:
                raise OSError('simulated move failure')
            return rename(source, target)
        with patch.object(module.os, 'rename', side_effect=fail), self.assertRaises(OSError):
            self.apply(module)
        self.assertTrue(all(p.exists() for p in self.files))
        self.assertEqual(self.tv.file_binding(self.files[0])['id'], self.file_ids[0])

    def test_after_catalog_crash_resumes_bookkeeping_without_new_ids(self):
        module, _ = self.preview()
        def crash(phase):
            if phase == 'catalog_committed':
                raise RuntimeError('simulated checkpoint interruption')
        with self.assertRaises(RuntimeError):
            module.apply(self.tv, self.jobs, [self.library], self.manifest, offline_check=lambda: None, checkpoint=crash)
        self.apply(module)
        self.assertEqual(self.tv.file_binding(self.home / 'Season 01' / self.files[0].name)['id'], self.file_ids[0])
        self.assertEqual(json.loads(self.manifest.read_text())['state'], 'complete')

    def test_explicit_new_home_is_approved_without_changing_filename(self):
        new_home = self.library / 'Fixture (2020)'
        module = importlib.import_module('tools.repair_tv_numeric_folders')
        module.preview(self.tv, self.jobs, [self.library], {str(self.old): str(new_home)}, self.manifest)
        self.apply(module)
        self.assertEqual(self.tv.resolve_import_destination(self.series, 1, [self.library])['path'], str(new_home / 'Season 01'))
        self.assertTrue((new_home / 'Season 01' / self.files[0].name).exists())

    def test_unknown_neighbor_after_preview_and_changed_bindings_block_before_move(self):
        module, _ = self.preview()
        unknown = self.old / 'unknown.txt'
        unknown.write_text('preserve')
        with self.assertRaisesRegex(ValueError, 'Unknown'):
            self.apply(module)
        self.assertTrue(all(p.exists() for p in self.files))
        unknown.unlink()
        with self.tv.store.transaction() as db:
            db.execute('DELETE FROM episode_file_bindings WHERE file_id=?', (self.file_ids[1],))
        with self.assertRaisesRegex(ValueError, 'bindings changed'):
            self.apply(module)
        self.assertTrue(all(p.exists() for p in self.files))

    def test_prepared_live_api_returns_new_paths_with_same_file_ids(self):
        from flask import Flask
        from services.tv_routes import register_tv_routes
        module, _ = self.preview()
        self.apply(module)
        web = Flask(__name__)
        register_tv_routes(web, lambda: {'repository': self.tv}, lambda: True, None)
        response = web.test_client().get(f'/api/tv/series/{self.series}/seasons/1')
        self.assertEqual(response.status_code, 200)
        versions = [episode['versions'][0] for episode in response.json['items']]
        self.assertEqual([v['file_id'] for v in versions], self.file_ids)
        self.assertTrue(all(v['available'] and Path(v['path']).parent == self.home / 'Season 01' for v in versions))

    def test_changed_job_references_block_and_unrelated_job_is_preserved(self):
        unrelated = self.jobs.upsert('b' * 40, {'media_type': 'movie', 'destination': 'unchanged', 'state': 'imported'})
        module, _ = self.preview()
        job = self.jobs.get('a' * 40)
        original = job['preserving_import_plan'][0]['target']
        job['preserving_import_plan'][0]['target'] = str(self.home / 'other.mkv')
        self.jobs.upsert('a' * 40, {'preserving_import_plan': job['preserving_import_plan']})
        with self.assertRaisesRegex(ValueError, 'publication references changed'):
            self.apply(module)
        self.assertTrue(all(p.exists() for p in self.files))
        job['preserving_import_plan'][0]['target'] = original
        self.jobs.upsert('a' * 40, {'preserving_import_plan': job['preserving_import_plan']})
        self.apply(module)
        self.assertEqual(self.jobs.get('b' * 40), unrelated)

    def test_preview_cli_closes_temporary_database_before_cleanup(self):
        module = importlib.import_module('tools.repair_tv_numeric_folders')
        self.tv.store.backup(self.root / 'tv-catalog.sqlite')
        (self.root / 'qbittorrent').mkdir()
        shutil.copy2(self.jobs.path, self.root / 'qbittorrent/jobs.json')
        (self.root / 'config.json').write_text(json.dumps({'user_data_dir': str(self.root), 'tv_roots': [str(self.library)]}))
        homes = self.root / 'homes.json'
        homes.write_text(json.dumps({str(self.old): str(self.home)}))
        arguments = ['repair', 'preview', '--project-root', str(self.root), '--manifest', str(self.manifest), '--homes-json', str(homes)]
        with patch('sys.argv', arguments), redirect_stdout(io.StringIO()):
            module.main()
        self.assertEqual(json.loads(self.manifest.read_text())['state'], 'preview')
        self.assertTrue(all(p.exists() for p in self.files))
