import unittest
from unittest.mock import patch


class RecommendationMatchingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.ai_provider_server import OfflineGuard
        with OfflineGuard():
            import app
        cls.owner = app

    def movie(self, identity, title='The Fixture', year='2001'):
        return {'id': identity, 'title': title, 'original_title': title, 'release_date': year+'-01-01',
                'vote_count': 1000, 'vote_average': 7, 'popularity': 30, 'original_language': 'en'}

    def test_exact_title_year_keeps_ranker_but_does_not_search_without_year_or_fetch_other_aliases(self):
        with patch.object(self.owner, '_smart_match_tmdb_search', return_value=[self.movie(7)]) as search, \
             patch.object(self.owner, '_smart_match_tmdb_alternative_titles', return_value=[]) as aliases:
            rows = self.owner._smart_match_tmdb_candidates('The Fixture', '2001', exact_first=True)
        self.assertEqual(str(rows[0]['tmdb_id']), '7')
        search.assert_called_once_with('The Fixture', '2001')
        aliases.assert_not_called()

    def test_wrong_year_does_not_short_circuit_existing_deeper_matching(self):
        with patch.object(self.owner, '_smart_match_tmdb_search', return_value=[self.movie(7, year='2000')]) as search, \
             patch.object(self.owner, '_smart_match_tmdb_alternative_titles', return_value=[]) as aliases:
            self.owner._smart_match_tmdb_candidates('The Fixture', '2001', exact_first=True)
        self.assertEqual(search.call_count, 2)
        aliases.assert_called_once_with('7')

    def test_legacy_default_still_runs_both_searches_and_alias_owner(self):
        with patch.object(self.owner, '_smart_match_tmdb_search', return_value=[self.movie(7)]) as search, \
             patch.object(self.owner, '_smart_match_tmdb_alternative_titles', return_value=[]) as aliases:
            self.owner._smart_match_tmdb_candidates('The Fixture', '2001')
        self.assertEqual(search.call_count, 2)
        aliases.assert_called_once_with('7')

    def test_missing_provider_release_date_cannot_become_an_exact_match_from_the_requested_year(self):
        movie = self.movie(7)
        movie['release_date'] = ''
        with patch.object(self.owner, '_smart_match_tmdb_search', return_value=[movie]) as search, \
             patch.object(self.owner, '_smart_match_tmdb_alternative_titles', return_value=[]) as aliases:
            rows = self.owner._smart_match_tmdb_candidates('The Fixture', '2001', exact_first=True)
        self.assertEqual(search.call_count, 2)
        aliases.assert_called_once_with('7')
        self.assertEqual(rows[0]['year'], '')

    def test_query_title_and_year_never_fill_missing_provider_identity_evidence(self):
        movie = {'id': 7, 'title': '', 'original_title': '', 'release_date': ''}
        with patch.object(self.owner, '_smart_match_tmdb_search', return_value=[movie]), \
             patch.object(self.owner, '_smart_match_tmdb_alternative_titles', return_value=[]):
            rows = self.owner._smart_match_tmdb_candidates('The Fixture', '2001')
        self.assertEqual(rows[0]['title'], '')
        self.assertEqual(rows[0]['year'], '')
        self.assertNotEqual(self.owner.evaluate_identity([{'title': 'The Fixture', 'year': '2001'}], rows)['outcome'], 'accepted')

    def history(self, year='2001', identity=7):
        return {**self.movie(identity, year='2002'), 'runtime': 95, 'release_dates': {'results': [
            {'iso_3166_1': 'US', 'release_dates': [{'release_date': year+'-01-01T00:00:00.000Z', 'type': 1}]}]}}

    def test_real_release_history_proves_supplied_year_without_unconstrained_search_or_alias_reads(self):
        details = self.history()
        with patch.object(self.owner, '_smart_match_tmdb_search', return_value=[self.movie(7, year='2002')]) as search, \
             patch.object(self.owner, '_smart_match_tmdb_alternative_titles', return_value=[]) as aliases:
            rows = self.owner._smart_match_tmdb_candidates('The Fixture', '2001', exact_first=True,
                                                         details=lambda identity: details)
        search.assert_called_once_with('The Fixture', '2001')
        aliases.assert_not_called()
        self.assertEqual(rows[0]['year'], '2002')
        self.assertIs(rows[0]['_resolved_details'], details)
        self.assertEqual(self.owner.evaluate_identity([{'title': 'The Fixture', 'year': '2001'}], rows)['outcome'], 'accepted')

    def test_absent_release_history_proof_and_wrong_detail_id_cannot_trigger_early_acceptance(self):
        for details in (self.history(year='2002'), self.history(identity=8), self.movie(7, year='2002')):
            with self.subTest(details_id=details.get('id')), \
                 patch.object(self.owner, '_smart_match_tmdb_search', return_value=[self.movie(7, year='2002')]) as search, \
                 patch.object(self.owner, '_smart_match_tmdb_alternative_titles', return_value=[]) as aliases:
                self.owner._smart_match_tmdb_candidates('The Fixture', '2001', exact_first=True, details=lambda identity: details)
            self.assertEqual(search.call_count, 2)
            aliases.assert_called_once_with('7')

    def test_real_same_year_remake_ambiguity_cannot_be_bypassed_by_release_history(self):
        with patch.object(self.owner, '_smart_match_tmdb_search', return_value=[self.movie(7, year='2002'), self.movie(8, year='2002')]) as search, \
             patch.object(self.owner, '_smart_match_tmdb_alternative_titles', return_value=[]) as aliases:
            rows = self.owner._smart_match_tmdb_candidates('The Fixture', '2001', exact_first=True,
                                                         details=lambda identity: self.history(identity=int(identity)))
        self.assertEqual(search.call_count, 2)
        self.assertEqual(self.owner.evaluate_identity([{'title': 'The Fixture', 'year': '2001'}], rows)['outcome'], 'ambiguous')

    def test_recommendation_reuses_the_same_details_that_proved_the_release_year(self):
        details = self.history()
        with patch.object(self.owner, '_smart_match_tmdb_search', return_value=[self.movie(7, year='2002')]) as search, \
             patch.object(self.owner, '_smart_match_tmdb_alternative_titles', return_value=[]) as aliases, \
             patch.object(self.owner, '_ai_movie_details', return_value=details) as fetch:
            result = self.owner._ai_resolve_recommendation({'title': 'The Fixture', 'year': '2001'})
        self.assertEqual(result['card']['year'], '2002')
        self.assertIs(result['raw'], details)
        self.assertEqual(fetch.call_count, 1)
        self.assertTrue(fetch.call_args.kwargs['release_history'])
        self.assertEqual(search.call_count, 1)
        aliases.assert_not_called()

    def test_ranker_ambiguity_cannot_short_circuit_to_the_first_hit(self):
        with patch.object(self.owner, '_smart_match_tmdb_search', return_value=[self.movie(7), self.movie(8)]) as search, \
             patch.object(self.owner, 'evaluate_identity', return_value={'outcome': 'ambiguous'}), \
             patch.object(self.owner, '_smart_match_tmdb_alternative_titles', return_value=[]) as aliases:
            rows = self.owner._smart_match_tmdb_candidates('The Fixture', '2001', exact_first=True)
        self.assertEqual(search.call_count, 2)
        self.assertEqual(len(rows), 2)
        self.assertEqual(aliases.call_count, 2)
