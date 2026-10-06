"""Isolated desktop proof with real Discover routes and overlapping provider pages."""
import os
from pathlib import Path
import tempfile
from urllib.parse import parse_qs, urlparse

if os.environ.get('CP_TEST_MODE') != '1':
    raise RuntimeError('Discover paging fixtures require CP_TEST_MODE=1')
root = Path(os.environ['CP_TEST_ROOT']).resolve()
if Path(tempfile.gettempdir()).resolve() not in root.parents:
    raise RuntimeError('A unique OS-temporary root is required')
port = int(os.environ.get('CP_PORT', '5117'))
if port == 5000:
    raise RuntimeError('Production port is prohibited')

import app

app._tmdb_key = 'isolated-discover-paging-key'
app._tmdb_genres = {18: 'Drama'}
app._ensure_tmdb_genres = lambda: None
app._tmdb_filter_options_cache = {
    'languages': [{'value': 'en', 'label': 'English'}],
    'countries': [{'value': 'US', 'label': 'United States'}],
}


def provider(url):
    params = parse_qs(urlparse(url).query)
    page = int(params['page'][0])
    small = 'lord of the rings' in params.get('query', [''])[0].lower()
    sorted_case = 'sorted' in params.get('query', [''])[0].lower()
    titles = ['The Fellowship of the Ring', 'The Two Towers', 'The Return of the King']
    batches = ([[1, 2, 3]] if small else [list(range(n, n + 20)) for n in (1, 21, 41, 61)] if sorted_case else [list(range(1, 21)), list(range(20, 40)),
               list(range(39, 59)), list(range(58, 78)), list(range(77, 82))])
    return {'page': page, 'total_pages': len(batches), 'total_results': sum(map(len, batches)),
            'results': [{'id': 50000 + i, 'title': (titles[i - 1] if small else
                         f'Sorted {"Z" if i <= 40 else "A"}{i:03d}' if sorted_case else f'Overlap Movie {i}'),
                         'release_date': '2024-01-01', 'genre_ids': [18], 'vote_average': 8,
                         'vote_count': 100, 'original_language': 'en',
                         'overview': 'Isolated Discover paging contract fixture.'}
                        for i in batches[page - 1]]}


app._tmdb_fetch_provider_page = provider
app.app.run(host='127.0.0.1', port=port, threaded=True, use_reloader=False)
