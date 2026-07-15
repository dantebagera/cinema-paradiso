import json
import urllib.parse
import urllib.request


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
