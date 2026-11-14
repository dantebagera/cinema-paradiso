"""Bounded speculative Movie reads; only the recommender accepts final results."""
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
import json

from services.chatgpt_skills import validate_schema


class RecommendationReader:
    """Decode complete entries in a top-level array, never keys inside strings."""
    def __init__(self, accept):
        self.accept = accept
        self.buffer, self.position, self.state, self.key = '', 0, 'object', None
        self.decoder = json.JSONDecoder()

    def feed(self, text):
        if self.state == 'done':
            return
        if len(self.buffer) + len(text) > 65536:
            self.buffer, self.state = '', 'done'
            return  # Final complete-response processing does not have this cap.
        self.buffer += text
        while self.state != 'done':
            while self.position < len(self.buffer) and self.buffer[self.position].isspace():
                self.position += 1
            if self.position == len(self.buffer):
                return
            char = self.buffer[self.position]
            if self.state == 'object':
                if char != '{':
                    self.state = 'done'
                    return
                self.position += 1
                self.state = 'key'
            elif self.state == 'key':
                if char == '}':
                    self.state = 'done'
                    return
                try:
                    self.key, end = self.decoder.raw_decode(self.buffer, self.position)
                except ValueError:
                    return
                if not isinstance(self.key, str):
                    self.state = 'done'
                    return
                self.position, self.state = end, 'colon'
            elif self.state == 'colon':
                if char != ':':
                    self.state = 'done'
                    return
                self.position += 1
                self.state = 'value'
            elif self.state == 'value':
                if self.key == 'recommendations':
                    if char != '[':
                        self.state = 'done'
                        return
                    self.position += 1
                    self.state = 'entry'
                else:
                    try:
                        _, self.position = self.decoder.raw_decode(self.buffer, self.position)
                    except ValueError:
                        return
                    self.state = 'after_value'
            elif self.state == 'entry':
                if char == ']':
                    self.position += 1
                    self.state = 'after_value'
                    continue
                try:
                    movie, end = self.decoder.raw_decode(self.buffer, self.position)
                except ValueError:
                    return
                self.position, self.state = end, 'after_entry'
                self.accept(movie)
            elif self.state == 'after_entry':
                if char == ',':
                    self.position += 1
                    self.state = 'entry'
                elif char == ']':
                    self.position += 1
                    self.state = 'after_value'
                else:
                    self.state = 'done'
            elif self.state == 'after_value':
                if char == ',':
                    self.position += 1
                    self.state = 'key'
                else:
                    self.state = 'done'


class CandidateBatch:
    """One worker owner for speculative and final title/year resolution.

    Only the transport/consumer thread submits entries. Worker threads perform
    read-only resolution and never touch session constraints or publish cards.
    """
    def __init__(self, resolve, cancel, schema):
        self.resolve_candidate, self.cancel, self.schema = resolve, cancel, schema
        self.pool, self.futures, self.closed = None, {}, False
        self.reader = RecommendationReader(self._prefetch)

    def __enter__(self):
        return self

    @staticmethod
    def _key(movie):
        return movie['title'], movie['year']

    def _future(self, movie):
        key = self._key(movie)
        if key not in self.futures:
            if self.cancel.is_set():
                future = Future()
                future.set_result(None)
            else:
                if self.pool is None:
                    self.pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix='cp-ai-movie')
                future = self.pool.submit(self._resolve, dict(movie))
            self.futures[key] = future
        return self.futures[key]

    def _resolve(self, movie):
        if self.cancel.is_set():
            return None
        return self.resolve_candidate(movie)

    def _prefetch(self, movie):
        if self.closed or self.cancel.is_set() or len(self.futures) >= 50:
            return
        try:
            validate_schema(self.schema, movie)
        except ValueError:
            return  # Final output is validated independently by its owner.
        self._future(movie)

    def feed(self, text):
        if not self.closed:
            self.reader.feed(text)

    def resolve(self, movies):
        # Terminal output wins even if it differs from the speculative stream.
        keep = {self._key(movie) for movie in movies}
        for key in list(self.futures):
            if key not in keep:
                self.futures.pop(key).cancel()
        source, pending = iter(movies), deque()
        def submit():
            movie = next(source, None)
            if movie is not None and not self.cancel.is_set():
                pending.append((movie, self._future(movie)))
        for _ in range(4):
            submit()
        while pending and not self.cancel.is_set():
            movie, future = pending.popleft()
            yield movie, future.result()
            submit()

    def __exit__(self, *exception):
        self.closed = True
        if self.pool:
            self.pool.shutdown(wait=True, cancel_futures=True)
