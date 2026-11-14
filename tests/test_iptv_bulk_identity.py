"""Structured bulk interpretation must survive independent TMDB verification."""
import os
import tempfile
import unittest
from types import SimpleNamespace
from flask import Flask

from services.ai_jobs import AIJobStore
from services.ai_routes import register_ai_routes
from services.iptv_movie_service import IPTVMovieService
from services.iptv_movie_store import source_key
from services.iptv_tmdb import choose_automatic_match, IPTVTMDBError
from tests.iptv_movie_fixtures import FakeTMDBClient, tmdb_payload
from tests import test_iptv_chatgpt_bulk as bulk_fixtures


class BulkIdentityTests(unittest.TestCase):
    def focused_proposal(self, pages):
        first = tmdb_payload(1, 'The Return', 2020)
        others = [tmdb_payload(i, 'Completely Unrelated', 1990) for i in range(2, 21)]
        rival = tmdb_payload(21, 'The Return', 2021)
        class Client(FakeTMDBClient):
            def search_movie_page(self, title, page=1, *, primary_year=0):
                if primary_year:
                    return ([first] if primary_year == 2020 else []), 1
                return ([first, *others] if page == 1 else [rival]), pages

            def search_movies(self, title, year=0, page=1):
                return [first] if year else [first, *others]

        return object.__new__(IPTVMovieService).bulk_source_proposal(
            {**self.source('The Return (2020)', 2020), 'source_revision': 1, 'match_revision': 1},
            Client(movies={m['id']: m for m in [first, *others, rival]}),
            interpretation=self.answer('The Return', 2020), interpreted=True, automatic=True)

    def test_focused_search_accepts_a_full_final_page_without_rivals(self):
        row = self.focused_proposal(1)
        self.assertEqual((row['outcome'], row['candidate_tmdb_id']), ('verified', 1))

    def test_focused_search_checks_later_pages_and_preserves_a_real_rival(self):
        row = self.focused_proposal(2)
        self.assertEqual(row['outcome'], 'review')
        self.assertEqual({x['tmdb_id'] for x in row['evidence']['candidates']}, {1, 21})

    def test_focused_search_preserves_review_when_pages_are_incomplete(self):
        row = self.focused_proposal(9)
        self.assertEqual(row['review_reason'], 'CP couldn’t finish checking competing matches.')

    def test_focused_search_sends_primary_year_and_requires_page_metadata(self):
        from services.iptv_tmdb import IPTVTMDBClient
        client = IPTVTMDBClient(None)
        calls = []
        def request(route, params):
            calls.append((route, params))
            return {'results': [], 'total_pages': 2}
        client._request = request
        self.assertEqual(client.search_movie_page('Film', 2, primary_year=2020), ([], 2))
        self.assertEqual(calls, [('search/movie', {'query': 'Film', 'page': 2,
            'include_adult': 'false', 'primary_release_year': 2020})])
        client._request = lambda *_: {'results': []}
        with self.assertRaisesRegex(IPTVTMDBError, 'invalid search pagination'):
            client.search_movie_page('Film')

    def source(self, title, year):
        return dict(source_key='s_test', provider_title=title, provider_year=year,
                    provider_tmdb_id=0, playlist_name='Movies', category='film',
                    classification_confidence=1, classification_manual_lock=False,
                    match_manual_lock=False)

    def answer(self, title, year, **changes):
        return dict(title=title, year=str(year) if year else '', aliases=[], category='Film',
                    confidence=.99, uncertain=False, **changes)

    def proposal(self, source, answer, movies, client=None):
        owner = object.__new__(IPTVMovieService)
        client = client or FakeTMDBClient(movies={m['id']: m for m in movies}, search_results=movies)
        return owner.bulk_source_proposal(source, client, interpretation=answer, interpreted=True)

    def test_live_titles_verify_with_cleaned_identity(self):
        cases = [('Black Widow (2021) 3D', 2021, 'Black Widow', 2021, 497698),
                 ('Good Luck Chuck (2008) Multi Sub', 2008, 'Good Luck Chuck', 2007, 10030),
                 ('The Holiday (2007) Multi Sub', 2007, 'The Holiday', 2006, 1581)]
        for raw, year, title, actual, identity in cases:
            with self.subTest(raw=raw):
                row = self.proposal(self.source(raw, year), self.answer(title, actual),
                                    [tmdb_payload(identity, title, actual)])
                self.assertEqual((row['outcome'], row['candidate_tmdb_id']), ('verified', identity))
                self.assertEqual(row['evidence']['identity']['provider_year'], year)
                self.assertEqual(row['evidence']['identity']['interpreted_year'], actual)

    def test_incompatible_year_candidate_cannot_hide_valid_match(self):
        movies = [tmdb_payload(1, 'Bruiser', 2021), tmdb_payload(2, 'Bruiser', 2022)]
        row = self.proposal(self.source('Bruiser (2023)', 2023), self.answer('Bruiser', 2022), movies)
        self.assertEqual((row['outcome'], row['candidate_tmdb_id']), ('verified', 2))

    def test_catalogue_articles_and_format_tags_are_symmetric(self):
        for raw, official, alternate in [('Dirty Harry Dead Pool', 'The Dead Pool', 'Dirty Harry The Dead Pool'),
                                         ('Tunnel', 'The Tunnel', 'Tunnel 3D')]:
            with self.subTest(raw=raw):
                movie = tmdb_payload(1, official, 2014)
                movie['alternative_titles'] = {'titles': [{'title': alternate}]}
                row = self.proposal(self.source(raw, 2014), self.answer(official, 2014), [movie])
                self.assertEqual(row['outcome'], 'verified')

    def test_first_film_number_requires_collection_chronology(self):
        movie = tmdb_payload(862, 'Toy Story', 1995)
        movie['belongs_to_collection'] = {'id': 10194}
        class Client(FakeTMDBClient):
            parts = []
            def collection(self, identity):
                return {'id': identity, 'parts': self.parts}
        client = Client(movies={862: movie}, search_results=[movie])
        source, answer = self.source('Toy Story 1 (1995)', 1995), self.answer('Toy Story', 1995)
        for parts, expected in [([], 'review'),
                ([{'id': 862, 'release_date': '1995-11-22'}, {'id': 863, 'release_date': '1999-10-30'}], 'verified'),
                ([{'id': 862, 'release_date': '1995-11-22'}, {'id': 863, 'release_date': '1990-10-30'}], 'review'),
                ([{'id': 862, 'release_date': '1995-11-22'}, {'id': 863, 'release_date': ''}], 'review')]:
            with self.subTest(parts=parts):
                client.parts = parts
                self.assertEqual(self.proposal(source, answer, [movie], client)['outcome'], expected)

    def test_real_rivals_are_retained_with_diagnostics(self):
        movies = [tmdb_payload(1, 'Sing', 2016), tmdb_payload(2, 'Sing', 2016)]
        row = self.proposal(self.source('Sing (2016) 3D', 2016), self.answer('Sing', 2016), movies)
        self.assertEqual(row['outcome'], 'review')
        self.assertIn('competing', row['review_reason'].lower())
        self.assertEqual({x['tmdb_id'] for x in row['evidence']['candidates']}, {1, 2})
        self.assertTrue(row['evidence']['search_attempts'])

    def test_missing_collection_proof_does_not_disprove_a_same_name_rival(self):
        first, rival = tmdb_payload(1, 'Toy Story', 1995), tmdb_payload(2, 'Toy Story', 1995)
        first['collection_first_movie_id'] = 1
        row = self.proposal(self.source('Toy Story 1 (1995)', 1995),
                            self.answer('Toy Story', 1995), [first, rival])
        self.assertEqual((row['outcome'], row['candidate_tmdb_id']), ('review', 0))

    def test_regional_release_evidence_keeps_a_plausible_rival(self):
        first, rival = tmdb_payload(1, 'The Neighbor', 2017), tmdb_payload(2, 'The Neighbor', 2020)
        rival['release_dates'] = {'results': [{'iso_3166_1': 'US', 'release_dates': [
            {'release_date': '2017-04-23T00:00:00.000Z', 'type': 1}]}]}
        row = self.proposal(self.source('The Neighbor (2018)', 2018),
                            self.answer('The Neighbor', 2017), [first, rival])
        self.assertEqual((row['outcome'], row['candidate_tmdb_id']), ('review', 0))
        rival_evidence = next(x for x in row['evidence']['candidates'] if x['tmdb_id'] == 2)
        self.assertEqual(rival_evidence['rival_score'], 100)
        alone = self.proposal(self.source('The Neighbor (2018)', 2018),
                              self.answer('The Neighbor', 2017), [rival])
        self.assertEqual((alone['outcome'], alone['candidate_tmdb_id']), ('review', 0))

    def test_uncertain_answer_and_tmdb_errors_retain_evidence(self):
        source, answer = self.source('Example (2020)', 2020), self.answer('Example', 2020)
        uncertain = {**answer, 'uncertain': True}
        row = self.proposal(source, uncertain, [])
        self.assertEqual(row['evidence']['interpretation'], uncertain)
        class Client(FakeTMDBClient):
            def search_movies(self, *args, **kwargs):
                raise IPTVTMDBError('IPTV TMDB rate limit reached', status=429, retryable=True, retry_after=3)
        row = self.proposal(source, answer, [], Client())
        self.assertEqual(row['outcome'], 'failed')
        self.assertEqual(row['evidence']['verification_error'], {
            'message': 'IPTV TMDB rate limit reached', 'status': 429, 'retryable': True, 'retry_after': 3})

    def test_preserved_provider_year_allows_one_year_but_deterministic_path_does_not_change(self):
        movie = tmdb_payload(10030, 'Good Luck Chuck', 2007)
        row = self.proposal(self.source('Good Luck Chuck (2008)', 2008),
                            self.answer('Good Luck Chuck', 2008), [movie])
        self.assertEqual(row['outcome'], 'verified')
        self.assertEqual(choose_automatic_match('Good Luck Chuck (2008)', 2008, [movie])['state'], 'ambiguous')

    def test_no_chained_year_tolerance_or_material_model_year_conflict(self):
        for model_year, candidate_year in [(2007, 2006), (2005, 2005), (2011, 2008)]:
            with self.subTest(model_year=model_year, candidate_year=candidate_year):
                row = self.proposal(self.source('Example Film (2008)', 2008),
                                    self.answer('Example Film', model_year),
                                    [tmdb_payload(1, 'Example Film', candidate_year)])
                self.assertEqual(row['outcome'], 'review')
                self.assertEqual(row['candidate_tmdb_id'], 0)

    def test_unrelated_model_substitution_is_not_identity_evidence(self):
        row = self.proposal(self.source('A Completely Different Film (2021)', 2021),
                            self.answer('Black Widow', 2021), [tmdb_payload(497698, 'Black Widow', 2021)])
        self.assertEqual((row['outcome'], row['candidate_tmdb_id']), ('review', 0))

    def test_title_numbers_and_roman_sequels_survive_model_cleanup(self):
        for original, proposed in [('Toy Story 2', 'Toy Story'), ('Rocky IV', 'Rocky V'),
                                   ('Blade Runner 2049', 'Blade Runner'), ('1917', '1918')]:
            with self.subTest(original=original):
                row = self.proposal(self.source(original + ' (2021)', 2021),
                                    self.answer(proposed, 2021), [tmdb_payload(1, proposed, 2021)])
                self.assertEqual((row['outcome'], row['candidate_tmdb_id']), ('review', 0))

    def test_nearby_remake_is_found_after_exact_year_candidate(self):
        first, rival = tmdb_payload(1, 'The Return', 2020), tmdb_payload(2, 'The Return', 2021)
        class Client(FakeTMDBClient):
            calls = []
            def search_movies(self, title, year=0, page=1):
                self.calls.append((title, year))
                return [first] if year else [first, rival]
        client = Client(movies={1: first, 2: rival})
        row = self.proposal(self.source('The Return (2020) 3D', 2020), self.answer('The Return', 2020),
                            [first, rival], client)
        self.assertEqual((row['outcome'], row['candidate_tmdb_id']), ('review', 0))
        self.assertIn(('the return', 0), client.calls)

    def test_meaningful_nonnumeric_sequel_words_cannot_be_discarded(self):
        for title in ['After We Collided', 'After - We Collided', 'After / We Collided']:
            with self.subTest(title=title):
                row = self.proposal(self.source(title + ' (2020)', 2020), self.answer('After', 2019),
                                    [tmdb_payload(1, 'After', 2019)])
                self.assertEqual((row['outcome'], row['candidate_tmdb_id']), ('review', 0))

    def test_candidate_cap_cannot_hide_an_unchecked_nearby_remake(self):
        first, rival = tmdb_payload(1, 'The Return', 2020), tmdb_payload(100, 'The Return', 2021)
        movies = {1: first, 100: rival, **{i: tmdb_payload(i, f'Unrelated Film {i}', 2020) for i in range(2, 21)}}
        class Client(FakeTMDBClient):
            def search_movies(self, title, year=0, page=1):
                if not year:
                    return [first, rival]
                offset = {'the return': 1, 'return home': 6, 'homecoming': 11, 'coming home': 16}.get(title, 1)
                return [movies[i] for i in range(offset, offset + 5)]
        answer = {**self.answer('The Return', 2020), 'aliases': ['Return Home', 'Homecoming', 'Coming Home']}
        row = self.proposal(self.source('The Return (2020) 3D', 2020), answer, list(movies.values()), Client(movies=movies))
        self.assertEqual((row['outcome'], row['candidate_tmdb_id']), ('review', 0))

    def test_collection_label_and_multilingual_alias_have_source_support(self):
        cases = [('Donald Duck And Nephews - Home Defense (1943)', 'Home Defense', 1943),
                 ('Merry Little Batman ميلاد سعيد باتمان الصغير (2023)', 'Merry Little Batman', 2023),
                 ('فيلم اهل القمة (1981)', 'أهل القمة', 1981)]
        for raw, title, year in cases:
            with self.subTest(raw=raw):
                movie = tmdb_payload(1, title, year)
                if title == 'Home Defense':
                    movie['credits']['cast'] = [{'name': 'Clarence Nash',
                                                'character': 'Donald Duck / Huey / Dewey / Louie (voice) (uncredited)'}]
                row = self.proposal(self.source(raw, year), self.answer(title, year), [movie])
                self.assertEqual(row['outcome'], 'verified')

    def test_collection_label_requires_catalogue_support(self):
        movie = tmdb_payload(1, 'Home Defense', 1943)
        row = self.proposal(self.source('Unrelated Film - Home Defense (1943)', 1943),
                            self.answer('Home Defense', 1943), [movie])
        self.assertEqual(row['outcome'], 'review')

    def test_translation_requires_tmdb_source_alias_support(self):
        source = self.source('تحدي الأقوياء (1980)', 1980)
        movie = tmdb_payload(1, 'The Strong Challenge', 1980)
        answer = self.answer('The Strong Challenge', 1980)
        self.assertEqual(self.proposal(source, answer, [movie])['outcome'], 'review')
        movie['alternative_titles'] = {'titles': [{'title': 'تحدي الأقوياء'}]}
        self.assertEqual(self.proposal(source, answer, [movie])['outcome'], 'verified')

    def test_uncertainty_and_locks_still_stop_confirmation(self):
        movie = tmdb_payload(1, 'Black Widow', 2021)
        source = self.source('Black Widow (2021) 3D', 2021)
        answer = self.answer('Black Widow', 2021)
        for field, value in [('uncertain', True), ('confidence', .8)]:
            self.assertEqual(self.proposal(source, {**answer, field: value}, [movie])['outcome'], 'review')
        self.assertEqual(self.proposal({**source, 'match_manual_lock': True}, answer, [movie])['outcome'], 'review')

    def test_runner_stores_verified_interpretation_and_apply_uses_same_identity(self):
        with tempfile.TemporaryDirectory(dir=os.environ['CP_TEST_ROOT']) as root:
            helper = bulk_fixtures.BulkContracts()
            movie = tmdb_payload(497698, 'Black Widow', 2021)
            owner = helper.provider(root, 1, titles=['Black Widow (2021) 3D'],
                client=lambda: FakeTMDBClient(movies={497698: movie}, search_results=[movie]))
            store = AIJobStore(root)
            job = helper.launch(owner, store, 1, 1)
            def respond(rows):
                return bulk_fixtures.reply([bulk_fixtures.model_row(r, category='Film', title='Black Widow', year='2021') for r in rows])
            done = helper.runner(owner, store, respond).run(job['id'])
            self.assertEqual((done['state'], done['run_calls']), ('completed', 1))
            public = store.snapshot(job['id'], review_view='pending_matches')
            self.assertEqual(public['review_counts']['pending_matches'], 1)
            row = public['results'][0]
            self.assertEqual(row['candidate_tmdb_id'], 497698)
            app = Flask(__name__)
            register_ai_routes(app, SimpleNamespace(connection_selection=bulk_fixtures.selection),
                               jobs_factory=lambda: SimpleNamespace(store=store))
            response = app.test_client().get(f"/api/ai/jobs/{job['id']}?review_view=pending_matches")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json['bulk']['counts']['verified'], 1)
            self.assertEqual(response.json['bulk']['processed'], 1)
            self.assertEqual(response.json['bulk']['selection_scope'], {
                'mode': job['request']['selection_snapshot'].get('mode', ''),
                'filters': job['request']['selection_snapshot'].get('filters', {})})
            self.assertNotIn('source_keys', response.json['bulk']['selection_scope'])
            self.assertEqual(response.json['results'][0]['candidate_tmdb_id'], 497698)
            self.assertFalse(owner.store.movie('source:' + source_key('0'))['matched'])
            report = owner.apply_bulk_proposals([row], 'match', owner.store.source_generation())
            self.assertEqual(report['applied'], [source_key('0')])
            self.assertEqual(owner.store.movie('source:' + source_key('0'))['tmdb_id'], 497698)
