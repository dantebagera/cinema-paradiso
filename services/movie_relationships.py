"""Transient TMDB relationship pages. Rankings stay separate; no catalogue writes."""
import threading
import time
from math import ceil
from collections import OrderedDict
from concurrent.futures import Future


class MovieRelationships:
    SOURCE_LIMIT = 100

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
        """Return a page of the bounded relationship ranking without fetching its full set."""
        self._validate_listing(movie_id, source, page_size)
        if not 1 <= page <= 500:
            raise ValueError('Valid tmdb_id and page (1–500) required')

        offset = (page - 1) * page_size
        maximum = self.SOURCE_LIMIT * (2 if source == 'all' else 1)
        combined, complete = self._listing_prefix(
            movie_id, source, min(maximum, offset + page_size + 1), fetch, normalize,
        )
        results = combined[offset:offset + page_size]
        known_total = len(combined) if complete else None
        return {
            'results': results,
            'source': source,
            'page': page,
            'page_size': page_size,
            'source_limit': self.SOURCE_LIMIT,
            'total_pages': max(1, ceil(known_total / page_size)) if known_total is not None else None,
            'total_results': known_total,
            'has_previous': page > 1,
            'has_next': len(combined) > offset + page_size or not complete,
        }

    def summary(self, movie_id, source, fetch, normalize, page_size=20):
        """Count only the same bounded ranking exposed by listing."""
        self._validate_listing(movie_id, source, page_size)
        maximum = self.SOURCE_LIMIT * (2 if source == 'all' else 1)
        combined, _ = self._listing_prefix(movie_id, source, maximum, fetch, normalize)
        counts = {'recommendations': 0, 'similar': 0}
        for item in combined:
            counts[item['relationship_source']] += 1
        return {
            'source': source,
            'page_size': page_size,
            'source_limit': self.SOURCE_LIMIT,
            'total_results': len(combined),
            'total_pages': max(1, ceil(len(combined) / page_size)),
            'source_counts': counts,
        }

    @staticmethod
    def _validate_listing(movie_id, source, page_size):
        if source not in {'all', 'recommendations', 'similar'}:
            raise ValueError('Unsupported relationship source')
        if not str(movie_id).isdigit() or int(movie_id) <= 0:
            raise ValueError('Valid tmdb_id and page (1–500) required')
        if not 1 <= page_size <= 100:
            raise ValueError('Valid page_size (1–100) required')

    def _listing_prefix(self, movie_id, source, target, fetch, normalize):
        combined = []
        seen = {str(movie_id)}
        complete = True
        sources = ('recommendations', 'similar') if source == 'all' else (source,)
        for relationship_source in sources:
            quota = self.SOURCE_LIMIT - sum(
                item['relationship_source'] == relationship_source for item in combined
            )
            needed = min(quota, target - len(combined))
            if needed <= 0:
                complete = False
                break
            source_results, source_exhausted = self._collect_source(
                movie_id, relationship_source, needed, seen, fetch, normalize,
            )
            combined.extend(source_results)
            source_complete = source_exhausted or len(source_results) >= self.SOURCE_LIMIT
            if len(combined) >= target and not source_complete:
                complete = False
                break
            if len(combined) >= target and relationship_source != sources[-1]:
                complete = False
                break
            if not source_complete:
                complete = False
                break
        return combined, complete

    def _collect_source(self, movie_id, source, needed, excluded, fetch, normalize):
        if needed <= 0:
            return [], False
        collected = []
        provider_page = 1
        while len(collected) < needed:
            data = self.page(movie_id, source, provider_page, fetch, normalize)
            provider_pages = min(500, max(1, int(data.get('total_pages') or 1)))
            page_results = data['results']
            for index, item in enumerate(page_results):
                identity = str(item.get('tmdb_id') or '')
                if not identity or identity in excluded:
                    continue
                excluded.add(identity)
                collected.append(item)
                if len(collected) >= needed:
                    return collected, provider_page >= provider_pages and index == len(page_results) - 1
            if provider_page >= provider_pages:
                return collected, True
            provider_page += 1
        return collected, False
