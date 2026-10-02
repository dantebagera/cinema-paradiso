"""Prove that the shipped seed is reproducible and can bootstrap independently."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from services.movie_awards_refresh import bundled_seed_loader
from services.movie_awards_store import MovieAwardsStore
from tools.build_movie_awards_snapshot import build_snapshot, canonical_bytes


class MovieAwardsBundleTests(unittest.TestCase):
    def test_pinned_offline_inputs_reproduce_complete_seed_and_bootstrap_both_organizations(self):
        project = Path(__file__).resolve().parents[1]
        source = project / 'docs/verification/movie-awards/reproduction'
        manifest = json.loads((source / 'sources-manifest.json').read_text(encoding='utf-8'))
        overrides = json.loads((source / 'identity-overrides.json').read_text(encoding='utf-8'))['overrides']
        inputs = manifest['sources'] + [program['independent_source'] for program in manifest['programs']]
        inputs += [item for program in manifest['programs'] for item in program.get('independent_supplements', [])]
        for item in inputs:
            item['path'] = str(project / item['path'])
        result = build_snapshot(manifest, overrides=overrides)
        seed, runtime_manifest = bundled_seed_loader(project / 'static/movie-awards')()
        raw = (project / 'static/movie-awards/seed.json').read_bytes()
        self.assertEqual(canonical_bytes(result['seed']), raw)
        self.assertEqual(hashlib.sha256(raw).hexdigest(), runtime_manifest['seed_sha256'])
        self.assertEqual(len(seed['ceremonies']), 181)
        self.assertEqual({org: sum(c['organization'] == org for c in seed['ceremonies']) for org in ('oscar', 'golden_globe')}, {'oscar': 98, 'golden_globe': 83})
        self.assertEqual(result['unresolved_count'], 0)
        self.assertFalse(result['identity_conflicts'])
        self.assertFalse(result['source_failures'])
        self.assertTrue(all(item['complete'] for item in result['audit']))
        with tempfile.TemporaryDirectory() as directory:
            store = MovieAwardsStore(Path(directory) / 'awards/awards.sqlite')
            self.assertEqual(store.install_seed(seed, runtime_manifest), 1)
            snapshot = store.read_snapshot()
            self.assertTrue(snapshot['ready'])
            self.assertEqual(snapshot['coverage']['oscar']['last_ceremony'], 98)
            self.assertEqual(snapshot['coverage']['golden_globe']['status'], 'complete')
            self.assertEqual(snapshot['coverage']['golden_globe']['last_ceremony'], 83)
            self.assertEqual(snapshot['movies']['imdb:tt0058541']['golden_globe'], 3)  # Sallah: New Star, Foreign Language and Samuel Goldwyn remain distinct.
            self.assertEqual(snapshot['movies']['imdb:tt0050631']['golden_globe'], 2)  # Les Girls: shared actresses do not multiply the film award.
            self.assertFalse(any('movie:imdb:tt0051911' in c['films'] for c in seed['ceremonies'] if c['organization'] == 'golden_globe'))  # Marjorie Morningstar illustration is no film award.
            self.assertEqual(snapshot['movies']['tmdb:98']['golden_globe'], 2)  # Gladiator: film and score, shared composers counted once.
            self.assertEqual(snapshot['people']['tmdb:500']['actor']['golden_globe'], 3)  # Tom Cruise's actual winning performances.
            winners = store.person_films(500, 'actor', 'golden_globe', 1, 100)
            self.assertEqual({row['id'] for row in winners['results']}, {2604, 9390, 334})
            self.assertEqual(store.install_seed(seed, runtime_manifest), 1)
