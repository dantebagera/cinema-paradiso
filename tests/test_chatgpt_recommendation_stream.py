import json
import threading
import unittest
from concurrent.futures import wait

from services.chatgpt_recommendation_stream import CandidateBatch, RecommendationReader
from services.chatgpt_skills import load


class RecommendationStreamTests(unittest.TestCase):
    def test_arbitrary_fragments_escaped_titles_and_nested_scope_are_decoded_only_at_top_level(self):
        movies = [{'title': 'Quoted "film" \\ title', 'year': '2001'}, {'title': 'لمعي', 'year': '2002'}]
        result = {'scope': {'recommendations': [{'title': 'Not a candidate', 'year': '1999'}],
                            'note': 'a string containing "recommendations":[]'}, 'recommendations': movies}
        text = json.dumps(result, ensure_ascii=False)
        for width in (1, 2, 7, len(text)):
            seen = []
            reader = RecommendationReader(seen.append)
            for start in range(0, len(text), width):
                reader.feed(text[start:start+width])
            self.assertEqual(seen, movies)

    def test_size_cap_stops_speculation_without_exposing_nested_candidates(self):
        seen = []
        reader = RecommendationReader(seen.append)
        reader.feed('{"scope":{"note":"' + ('x' * 70000))
        reader.feed('"},"recommendations":[{"title":"Movie","year":"2001"}]}')
        self.assertEqual(seen, [])

    def test_prefetch_is_bounded_deduplicated_and_reused_by_final_list(self):
        schema = load('F1')['result_schema']['properties']['recommendations']['items']
        gate = threading.Event()
        started = []
        lock = threading.Lock()
        def resolve(movie):
            with lock:
                started.append(movie['title'])
            gate.wait(2)
            return {'candidate': movie}
        movies = [{'title': 'Movie '+str(n), 'year': '2001'} for n in range(60)]
        try:
            with CandidateBatch(resolve, threading.Event(), schema) as batch:
                batch.feed(json.dumps({'recommendations': movies + movies[:3]}))
                self.assertLessEqual(len(started), 4)
                gate.set()
                selected = list(batch.resolve(movies[:50]))
                self.assertEqual([m for m, _ in selected], movies[:50])
                self.assertEqual(len(started), 50)
                self.assertEqual(len(set(started)), 50)
        finally:
            gate.set()

    def test_cancellation_and_invalid_item_shapes_do_not_schedule_reads(self):
        schema = load('F1')['result_schema']['properties']['recommendations']['items']
        called = []
        cancel = threading.Event()
        with CandidateBatch(called.append, cancel, schema) as batch:
            batch.feed(json.dumps({'recommendations': [{'title': 'Invalid', 'year': True}]}))
            cancel.set()
            batch.feed(json.dumps({'recommendations': [{'title': 'Cancelled', 'year': '2001'}]}))
            self.assertEqual(list(batch.resolve([{'title': 'Cancelled', 'year': '2001'}])), [])
        self.assertEqual(called, [])

    def test_queued_speculative_reads_do_not_start_after_cancellation(self):
        schema = load('F1')['result_schema']['properties']['recommendations']['items']
        gate, cancel = threading.Event(), threading.Event()
        started = []
        def resolve(movie):
            started.append(movie)
            gate.wait(2)
        with CandidateBatch(resolve, cancel, schema) as batch:
            movies = [{'title': 'Movie '+str(n), 'year': '2001'} for n in range(50)]
            batch.feed(json.dumps({'recommendations': movies}))
            cancel.set()
            gate.set()
            wait(list(batch.futures.values()), timeout=2)
            self.assertLessEqual(len(started), 4)
