from pathlib import Path
import tempfile
import unittest

from services.tv_catalog_repository import TVCatalogRepository
from services.tv_read_model import TVReadModel


class TVCoverageContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = TVCatalogRepository(self.root / 'tv.sqlite')
        self.read = TVReadModel(self.repo)
        self.series = {'tmdb_id': 1234, 'title': 'Twenty Two', 'status': 'Ended',
                       'seasons': [{'season_number': 0, 'episode_count': 1},
                                   {'season_number': 1, 'episode_count': 21},
                                   {'season_number': 2, 'episode_count': 1}]}
        self.episodes = [{'season_number': 0, 'episode_number': 1, 'title': 'Special', 'air_date': '2020-01-01'}]
        self.episodes += [{'season_number': 1, 'episode_number': n, 'title': str(n), 'air_date': '2020-01-01'} for n in range(1, 22)]
        self.episodes += [{'season_number': 2, 'episode_number': 1, 'title': 'Next season', 'air_date': '2021-01-01'}]
        self.series_id = self.repo.refresh(self.series, self.episodes)

    def episode(self, season, number):
        return next(row for row in self.repo.episodes(self.series_id, season) if row['episode_number'] == number)

    def bind(self, season, number):
        row = self.episode(season, number)
        path = self.root / f'{row["code"]}.mkv'
        path.write_bytes(b'synthetic video')
        return self.repo.bind_file(path, [row['id']], {'quality_class': '1080p'}, [self.root])

    def test_complete_counts_ignore_specials_and_incomplete_catalog_has_no_percentage(self):
        self.bind(0, 1)
        for number in range(1, 11):
            self.bind(1, number)
        row = self.episode(1, 1)
        self.repo.save_progress(row['id'], completed=True)
        detail = self.read.detail(self.series_id)
        self.assertEqual((detail['episode_count'], detail['available_count'], detail['completed_count']), (22, 10, 1))
        self.assertEqual((detail['offline_percent'], detail['watched_percent']), (45, 5))
        self.assertEqual((detail['specials_count'], detail['specials_offline_count']), (1, 1))
        partial = TVCatalogRepository(self.root / 'partial.sqlite')
        partial_id = partial.refresh(self.series, self.episodes[:12], season_scope={1})
        self.assertIsNone(TVReadModel(partial).detail(partial_id)['offline_percent'])

    def test_player_cursor_resumes_then_targets_immediate_successor_across_season(self):
        file21 = self.bind(1, 21)
        self.bind(2, 1)
        episode21 = self.episode(1, 21)
        self.repo.save_progress(episode21['id'], file21, position_ms=1200, duration_ms=5000, player_activity=True)
        reopened = TVReadModel(TVCatalogRepository(self.root / 'tv.sqlite'))
        self.assertEqual(reopened.detail(self.series_id)['primary_action']['target']['code'], 'S01E21')
        self.assertEqual(reopened.detail(self.series_id)['primary_action']['position_ms'], 1200)
        self.repo.save_progress(episode21['id'], file21, position_ms=5000, duration_ms=5000, completed=True, player_activity=True)
        self.repo.save_progress(self.episode(1, 7)['id'], completed=True)
        next_action = reopened.detail(self.series_id)['primary_action']
        self.assertEqual(next_action['target']['code'], 'S02E01')
        self.assertTrue(next_action['playable'])
        self.repo.save_progress(self.episode(2, 1)['id'], completed=True, player_activity=True)
        self.assertEqual(reopened.detail(self.series_id)['primary_action']['reason'], 'Caught up')

    def test_missing_immediate_successor_does_not_jump_to_later_file(self):
        file21 = self.bind(1, 21)
        self.repo.save_progress(self.episode(1, 21)['id'], file21, completed=True, player_activity=True)
        action = self.read.detail(self.series_id)['primary_action']
        self.assertEqual(action['target']['code'], 'S02E01')
        self.assertFalse(action['playable'])
        self.assertIn('missing', action['reason'])

    def test_show_watched_requires_ended_complete_and_undo_preserves_individual_progress(self):
        individual = self.episode(1, 7)
        self.repo.save_progress(individual['id'], completed=True)
        result = self.repo.set_series_watched(self.series_id, True)
        self.assertEqual(result['changed'], 21)
        self.assertTrue(self.read.detail(self.series_id)['series_watched'])
        # A later manual edit advances this episode's revision, so undo leaves it alone.
        later = self.episode(1, 8)
        self.repo.save_progress(later['id'], completed=True)
        reopened = TVCatalogRepository(self.root / 'tv.sqlite')
        self.assertEqual(reopened.set_series_watched(self.series_id, False)['changed'], 20)
        self.assertTrue(reopened.episodes(self.series_id, 1)[6]['completed'])
        self.assertTrue(reopened.episodes(self.series_id, 1)[7]['completed'])
        self.assertFalse(reopened.episodes(self.series_id, 0)[0]['completed'])
        ongoing = dict(self.series, status='Returning Series')
        self.repo.refresh(ongoing, self.episodes)
        with self.assertRaises(ValueError):
            self.repo.set_series_watched(self.series_id, True)


if __name__ == '__main__':
    unittest.main()
