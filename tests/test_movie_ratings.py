import unittest

from services.movie_ratings import normalize_plex_ratings, movie_identity, plex_identity, matches_identity


class RatingsNormalizationTest(unittest.TestCase):
    def test_rt_sources_and_two_types_stay_separate(self):
        result = normalize_plex_ratings({'Rating': [
            {'image': 'imdb://image.rating', 'type': 'audience', 'value': 9.9},
            {'image': 'rottentomatoes://image.rating.ripe', 'type': 'critic', 'value': 9.5},
            {'image': 'rottentomatoes://image.rating.upright', 'type': 'audience', 'value': 7.7}]})
        self.assertEqual((result['critics'], result['audience']), (95, 77))

    def test_zero_and_59_60_100_boundaries(self):
        for raw, expected in [(0, 0), (5.9, 59), (6, 60), (10, 100), ('5.95', 60)]:
            with self.subTest(raw=raw):
                result = normalize_plex_ratings({'rating': raw, 'ratingImage': 'rottentomatoes://image.rating.rotten'})
                self.assertEqual(result['critics'], expected)
                self.assertIsNone(result['audience'])

    def test_invalid_scores_do_not_become_zero(self):
        for raw in [True, False, None, '', 'N/A', float('nan'), float('inf'), -1, 11, {}, []]:
            with self.subTest(raw=raw):
                self.assertIsNone(normalize_plex_ratings({'rating': raw, 'ratingImage': 'rottentomatoes://image.rating.ripe'})['critics'])

    def test_source_and_role_must_agree(self):
        for marker in ['', 'imdb://image.rating', 'themoviedb://image.rating', 'rottentomatoes://image.rating.upright']:
            self.assertIsNone(normalize_plex_ratings({'rating': 8.5, 'ratingImage': marker})['critics'])

    def test_conflicting_duplicates_are_unavailable_not_first_match(self):
        rows = [{'image': 'rottentomatoes://image.rating.ripe', 'type': 'critic', 'value': value} for value in [8, 9]]
        self.assertIsNone(normalize_plex_ratings({'Rating': rows, 'rating': 8, 'ratingImage': rows[0]['image']})['critics'])

    def test_local_source_markers_preserve_both_scores(self):
        value = normalize_plex_ratings({'rating': 5.8, 'ratingImage': 'rottentomatoes://image.rating.rotten',
                                      'audienceRating': 5.5, 'audienceRatingImage': 'rottentomatoes://image.rating.spilled'})
        self.assertEqual((value['critics'], value['audience']), (58, 55))

    def test_exact_id_confirmation_required(self):
        item = {'type': 'movie', 'guid': 'plex://movie/' + 'a' * 24,
                'Guid': [{'id': 'tmdb://44012'}, {'id': 'imdb://tt0073198'}]}
        self.assertTrue(matches_identity(movie_identity({'tmdb_id': '44012'}), item))
        self.assertFalse(matches_identity(movie_identity({'tmdb_id': '44012', 'imdb_id': 'tt99999'}), item))
        self.assertFalse(matches_identity(movie_identity({'tmdb_id': '44012'}), {**item, 'type': 'show'}))
        self.assertFalse(matches_identity(movie_identity({'tmdb_id': '44012'}), {'title': 'Jeanne Dielman'}))
        self.assertEqual(plex_identity(item)['tmdb_id'], '44012')

    def test_identity_rejects_missing_malformed_and_tv(self):
        for value in [{}, {'tmdb_id': True}, {'tmdb_id': -1}, {'tmdb_id': '1 OR 1'}, {'imdb_id': '123'}, {'tmdb_id': 1, 'type': 'show'}]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                movie_identity(value)
        self.assertEqual(movie_identity({'tmdb_id': '001'})['key'], 'movie:tmdb:1')


if __name__ == '__main__': unittest.main()
