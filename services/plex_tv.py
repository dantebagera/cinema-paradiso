"""Typed Plex TV discovery. Plex supplies paths and provider IDs, never TV truth."""
import json
import urllib.parse
import urllib.request


def _tmdb_id(row):
    candidates = [row.get('guid', ''), *(item.get('id', '') for item in row.get('Guid', []))]
    for value in candidates:
        text = str(value or '')
        if text.startswith('tmdb://') and text[7:].isdigit():
            return int(text[7:])
    return None


class PlexTVDiscovery:
    def __init__(self, url_provider, token_provider, opener=None):
        self.url_provider, self.token_provider = url_provider, token_provider
        self.opener = opener

    def request(self, path, **params):
        base = str(self.url_provider() or '').rstrip('/')
        token = str(self.token_provider() or '')
        if not base or not token:
            raise ValueError('Plex is not configured')
        query = urllib.parse.urlencode(params)
        url = f'{base}{path}' + (f'?{query}' if query else '')
        request = urllib.request.Request(url, headers={'Accept': 'application/json', 'X-Plex-Token': token})
        opener = self.opener or urllib.request.urlopen
        with opener(request, timeout=15) as response:
            return json.loads(response.read())

    def entries(self, tmdb_tv_id, *, limit=5000):
        tmdb_tv_id, limit = int(tmdb_tv_id), min(5000, max(1, int(limit)))
        sections = self.request('/library/sections').get('MediaContainer', {}).get('Directory', [])
        show = None
        for section in sections:
            if section.get('type') != 'show':
                continue
            payload = self.request(f"/library/sections/{section['key']}/all", type=2, includeGuids=1)
            for candidate in payload.get('MediaContainer', {}).get('Metadata', []):
                if _tmdb_id(candidate) == tmdb_tv_id:
                    show = candidate
                    break
            if show:
                break
        if not show or not show.get('ratingKey'):
            raise LookupError('The selected TMDB TV series was not found in Plex')

        rows, start, size = [], 0, 200
        while len(rows) < limit:
            payload = self.request(
                f"/library/metadata/{show['ratingKey']}/allLeaves",
                includeGuids=1,
                **{'X-Plex-Container-Start': start, 'X-Plex-Container-Size': min(size, limit-len(rows))},
            ).get('MediaContainer', {})
            batch = payload.get('Metadata', [])
            for episode in batch:
                provider_id = _tmdb_id(episode)
                for media in episode.get('Media', []):
                    for part in media.get('Part', []):
                        if part.get('file'):
                            rows.append({
                                'path': part['file'],
                                'tmdb_episode_id': provider_id,
                                'season_number': episode.get('parentIndex'),
                                'episode_number': episode.get('index'),
                                'plex_rating_key': episode.get('ratingKey'),
                            })
                            if len(rows) >= limit:
                                break
                    if len(rows) >= limit:
                        break
                if len(rows) >= limit:
                    break
            start += len(batch)
            total = int(payload.get('totalSize') or payload.get('size') or start)
            if not batch or start >= total:
                break
        return rows
