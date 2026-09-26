"""Transient TMDB relationship pages. Rankings stay separate; no catalogue writes."""
import threading
import time
from math import ceil
from collections import OrderedDict
from concurrent.futures import Future


class MovieRelationships:
    def __init__(self, ttl=900, capacity=256):
        self.ttl = ttl
        self.capacity = capacity
        self._cache = OrderedDict()
        self._lock = threading.Lock()
        self._pending = {}

    def page(self, movie_id, source, page, fetch, normalize):
        if source not in {'recommendations', 'similar'}:
            raise ValueError('Unsupported relationship source')
        if not str(movie_id).isdigit() or int(movie_id) <= 0 or not 1 <= page <= 500:
            raise ValueError('Valid tmdb_id and page (1–500) required')
        key = (str(movie_id), source, page)
        with self._lock:
            cached = self._cache.get(key)
            if cached and time.monotonic() - cached[0] < self.ttl:
                self._cache.move_to_end(key)
                return cached[1]
            pending = self._pending.get(key)
            owner = pending is None
            if owner:
                pending = self._pending[key] = Future()
        if not owner:
            return pending.result()
        try:
            raw = fetch(movie_id, source, page)
            seen = {str(movie_id)}
            results = []
            for item in raw.get('results', []):
                identity = str(item.get('id') or '')
                if not identity or identity in seen:
                    continue
                seen.add(identity)
                results.append({**normalize(item), 'relationship_source': source})
            result = {
                'results': results, 'source': source, 'page': page,
                'total_pages': min(500, max(1, int(raw.get('total_pages') or 1))),
                'total_results': int(raw.get('total_results') or 0),
            }
            with self._lock:
                self._cache[key] = (time.monotonic(), result)
                while len(self._cache) > self.capacity:
                    self._cache.popitem(last=False)
            pending.set_result(result)
            return result
        except Exception as error:
            pending.set_exception(error)
            raise
        finally:
            with self._lock:
                self._pending.pop(key)

    def listing(self, movie_id, source, page, fetch, normalize, page_size=20):
        """Return one accessible relationship page without eagerly loading the feed."""
        if source not in {'all', 'recommendations', 'similar'}:
            raise ValueError('Unsupported relationship source')
        if not str(movie_id).isdigit() or int(movie_id) <= 0 or not 1 <= page <= 500:
            raise ValueError('Valid tmdb_id and page (1–500) required')
        if not 1 <= page_size <= 100:
            raise ValueError('Valid page_size (1–100) required')

        offset = (page - 1) * page_size
        target = offset + page_size + 1
        combined = []
        seen = {str(movie_id)}
        exhausted = True

        for relationship_source in (
            ('recommendations', 'similar') if source == 'all' else (source,)
        ):
            source_results, source_exhausted = self._collect_source(
                movie_id, relationship_source, target - len(combined),
                seen, fetch, normalize,
            )
            combined.extend(source_results)
            seen.update(str(item.get('tmdb_id') or '') for item in source_results)
            if len(combined) >= target:
                exhausted = False
                break
            if not source_exhausted:
                exhausted = False
                break

        results = combined[offset:offset + page_size]
        has_next = len(combined) > offset + page_size or not exhausted
        known_total = len(combined) if exhausted else None
        return {
            'results': results,
            'source': source,
            'page': page,
            'page_size': page_size,
            'total_pages': max(1, ceil(known_total / page_size)) if known_total is not None else None,
            'total_results': known_total,
            'has_previous': page > 1,
            'has_next': has_next,
        }

    def _collect_source(self, movie_id, source, needed, excluded, fetch, normalize):
        if needed <= 0:
            return [], False
        collected = []
        provider_page = 1
        while len(collected) < needed:
            data = self.page(movie_id, source, provider_page, fetch, normalize)
            for item in data['results']:
                identity = str(item.get('tmdb_id') or '')
                if not identity or identity in excluded:
                    continue
                excluded.add(identity)
                collected.append(item)
                if len(collected) >= needed:
                    break
            provider_pages = min(500, max(1, int(data.get('total_pages') or 1)))
            if provider_page >= provider_pages:
                return collected, True
            provider_page += 1
        return collected, False
