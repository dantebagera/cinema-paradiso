from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from services.tv_bulk_actions import TVBulkActions
from services.tv_catalog_repository import TVCatalogRepository


class TVBulkActionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = TVCatalogRepository(self.root/'tv.sqlite')
        self.show = self.repo.refresh({'tmdb_id': 73, 'title': 'Example', 'status': 'Ended',
            'seasons': [{'season_number': 1, 'episode_count': 1}]},
            [{'season_number': 1, 'episode_number': 1, 'title': 'Pilot', 'air_date': '2020-01-01'}])
        self.episode = self.repo.episodes(self.show)[0]['id']
        self.video = self.root/'S01E01.mkv'; self.video.write_bytes(b'video')
        self.subtitle = self.root/'S01E01.srt'; self.subtitle.write_bytes(b'subtitle')
        self.repo.bind_file(self.video, [self.episode], {'quality_class':'1080p'}, [self.root])
        self.jobs = {}
        self.playing = ''
        self.trash = Mock(side_effect=lambda path: Path(path).unlink())
        self.actions = TVBulkActions(self.repo, lambda:[self.root], lambda:self.jobs,
            lambda:self.playing, self.trash)

    def test_exact_preview_and_recycle_keep_history_and_list_membership(self):
        self.repo.create_tv_list('Favorites')
        preview = self.actions.preview_delete([self.show])
        self.assertEqual((preview['video_count'], preview['sidecar_count']), (1, 1))
        self.assertEqual({row['path'] for row in preview['files']}, {str(self.video), str(self.subtitle)})
        self.repo.save_progress(self.episode, completed=True)
        result = self.actions.delete([self.show], preview['token'])
        self.assertEqual(len(result['removed']), 2)
        self.assertFalse(self.video.exists())
        self.assertTrue(self.repo.episodes(self.show)[0]['completed'])
        self.assertEqual(len(self.actions.history()['items']), 1)

    def test_transfer_playback_and_changed_file_block_execution(self):
        self.jobs = {'a'*40: {'state':'downloading','tv_request':{'series_id':self.show}}}
        self.assertTrue(self.actions.preview_delete([self.show])['blocked'])
        self.jobs = {}
        self.playing = str(self.video)
        self.assertTrue(self.actions.preview_delete([self.show])['blocked'])
        self.playing = ''
        preview = self.actions.preview_delete([self.show])
        self.video.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'changed after preview'):
            self.actions.delete([self.show], preview['token'])
        self.assertTrue(self.video.exists())

    def test_shared_binding_with_unselected_show_is_protected(self):
        other = self.repo.refresh({'tmdb_id': 74, 'title': 'Other', 'status': 'Ended',
            'seasons': [{'season_number': 1, 'episode_count': 1}]},
            [{'season_number': 1, 'episode_number': 1, 'title': 'Pilot', 'air_date': '2020-01-01'}])
        other_episode = self.repo.episodes(other)[0]['id']
        with self.repo.store.transaction() as db:
            file_id = db.execute('SELECT id FROM media_files WHERE path=?', (str(self.video),)).fetchone()[0]
            db.execute('INSERT INTO episode_file_bindings(episode_id,file_id) VALUES(?,?)', (other_episode,file_id))
        self.assertTrue(self.actions.preview_delete([self.show])['blocked'])
        self.assertFalse(self.actions.preview_delete([self.show, other])['blocked'])


if __name__ == '__main__':
    unittest.main()
