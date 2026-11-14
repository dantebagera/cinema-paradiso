"""Real CP movie routes with deterministic upstream metadata; disposable root only."""
import json
import os
import tempfile
from pathlib import Path
from urllib.parse import urlparse, parse_qs

root = Path(os.environ['CP_TEST_ROOT']).resolve()
port = int(os.environ['CP_PORT'])
if os.environ.get('CP_TEST_MODE') != '1' or Path(tempfile.gettempdir()).resolve() not in root.parents or port == 5000:
    raise RuntimeError('Disposable root and nonproduction port required')

import app

app._tmdb_key = 'fixture-only'
app._tmdb_genres = {18: 'Drama'}
app._ensure_tmdb_genres = lambda: None
raw = {'id': 700701, 'title': 'The Blue Elephant', 'original_title': 'الفيل الأزرق',
       'original_language': 'ar', 'release_date': '2014-01-01', 'overview': 'English plot.',
       'genres': [{'id': 18, 'name': 'Drama'}], 'genre_ids': [18], 'runtime': 120,
       'vote_average': 8, 'vote_count': 800, 'credits': {'cast': [], 'crew': []}}


class Response:
    def __init__(self, payload): self.payload = payload
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self): return json.dumps(self.payload).encode()


def upstream(request, **kwargs):
    url = request.full_url if hasattr(request, 'full_url') else str(request)
    parsed = urlparse(url)
    if parsed.hostname != 'api.themoviedb.org':
        raise RuntimeError('Unexpected upstream request in isolated Arabic fixture')
    if parsed.path == '/3/movie/700701':
        arabic = parse_qs(parsed.query).get('language') == ['ar-SA']
        return Response({**raw, **({'title': 'الفيل الأزرق', 'overview': 'حبكة الفيلم باللغة العربية'} if arabic else {})})
    if parsed.path.endswith('/languages'): return Response([{'iso_639_1': 'ar', 'english_name': 'Arabic'}])
    if parsed.path.endswith('/countries'): return Response([])
    return Response({'results': [raw], 'page': 1, 'total_pages': 1, 'total_results': 1})


app.urllib.request.urlopen = upstream
app.app.run(host='127.0.0.1', port=port, use_reloader=False, debug=False)
