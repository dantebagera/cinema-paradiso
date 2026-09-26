import json
import urllib.parse
import urllib.request
import time
from concurrent.futures import ThreadPoolExecutor, wait


class ProwlarrClient:
    """Single transport owner for Prowlarr indexer and search requests."""

    def __init__(self, base_url, api_key, opener=urllib.request.urlopen):
        self.base_url = str(base_url or '').strip().rstrip('/')
        self.api_key = str(api_key or '').strip()
        self.opener = opener

    def _request_json(self, path, *, timeout):
        if not self.base_url or not self.api_key:
            raise RuntimeError('Prowlarr not configured')
        request = urllib.request.Request(
            f'{self.base_url}{path}',
            headers={'X-Api-Key': self.api_key, 'Accept': 'application/json'},
        )
        with self.opener(request, timeout=timeout) as response:
            return json.loads(response.read().decode())

    def enabled_indexers(self, *, timeout=8):
        rows = self._request_json('/api/v1/indexer', timeout=timeout)
        return [
            {'id': str(row.get('id', '')), 'name': str(row.get('name', '') or '')}
            for row in rows
            if row.get('enable', True) and str(row.get('id', '')).strip()
        ]

    def search(self, *, query='', indexer_ids=None, limit=100, categories='2000', timeout=30):
        parts = [('query', str(query or '').strip()), ('type', 'search')]
        if categories:
            parts.append(('categories', str(categories)))
        parts.append(('limit', str(int(limit))))
        parts.extend(('indexerIds', str(indexer_id)) for indexer_id in (indexer_ids or []))
        return self._request_json(
            f'/api/v1/search?{urllib.parse.urlencode(parts)}',
            timeout=timeout,
        )

    def search_tv(self, *, tmdb_tv_id, title, season=None, episode=None, indexer_ids=None, limit=100, timeout=20):
        if int(tmdb_tv_id) <= 0 or not str(title).strip():
            raise ValueError('A canonical TV identity and title are required')
        if episode is not None and season is None:
            raise ValueError('Episode searches require a season')
        query = str(title).strip()
        if season is not None:
            if int(season) < 0:
                raise ValueError('Invalid season')
            query += f' S{int(season):02d}'
        if episode is not None:
            if int(episode) <= 0:
                raise ValueError('Invalid episode')
            query += f'E{int(episode):02d}'
        return self.search(query=query, indexer_ids=indexer_ids, limit=min(100, max(1, int(limit))), categories='5000', timeout=timeout)

    def search_tv_report(self, *, indexer_ids=None, budget=20, **target):
        """Independent indexer requests: a stalled source cannot discard fast results.

        None selects enabled TV sources; an explicitly empty selection searches none.
        Trust used for automatic acquisition is a separate decision.
        """
        started = time.monotonic()
        rows = self._request_json('/api/v1/indexer', timeout=min(8, budget))
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise RuntimeError('Invalid indexer response')
        selected = None if indexer_ids is None else {str(value) for value in indexer_ids}
        def supports_tv(row):
            categories = row.get('capabilities', {}).get('categories', [])
            return any(5000 <= int(c.get('id', 0)) < 6000 for c in categories)
        sources = [r for r in rows if r.get('enable', True) and supports_tv(r)
                   and (selected is None or str(r['id']) in selected)]
        if not sources:
            return {'items': [], 'partial': False, 'sources': [], 'notice': 'No enabled TV indexers match the search selection.'}
        pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix='tv-search')
        deadline = started + budget
        def search_one(row):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError()
            return self.search_tv(indexer_ids=[row['id']], **target, timeout=remaining)
        futures = {pool.submit(search_one, row): row for row in sources}
        done, pending = wait(futures, timeout=max(0, deadline-time.monotonic()))
        items, statuses = [], []
        for future, row in futures.items():
            status = {'id': str(row['id']), 'name': row.get('name', str(row['id']))}
            if future in done:
                try:
                    result = future.result()
                    if not isinstance(result, list) or any(not isinstance(item, dict) for item in result):
                        raise ValueError('Invalid search response')
                    items.extend(result)
                    status.update(state='complete', count=len(result))
                except Exception:
                    # Provider URLs can contain credentials. Never expose exceptions.
                    status.update(state='failed', count=0)
            else:
                future.cancel()
                status.update(state='timeout', count=0)
            statuses.append(status)
        pool.shutdown(wait=False, cancel_futures=True)
        partial = any(s['state'] != 'complete' for s in statuses)
        return {'items': items, 'sources': statuses, 'partial': partial,
                'notice': 'Some indexers did not finish. Available results are shown; retry to search again.' if partial else ''}
