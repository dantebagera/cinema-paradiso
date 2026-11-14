"""Disposable desktop fixture; real Movie Follow routes and source decisions."""
import os
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlparse

if os.environ.get('CP_TEST_MODE') != '1':
    raise RuntimeError('Movie Follow fixtures require CP_TEST_MODE=1')
root = Path(os.environ['CP_TEST_ROOT']).resolve()
if Path(tempfile.gettempdir()).resolve() not in root.parents:
    raise RuntimeError('An OS-temporary test root is required')
port = int(os.environ.get('CP_PORT', '5118'))
if port == 5000:
    raise RuntimeError('Production port is prohibited')

import app
from tests.test_movie_follow_contract import MovieFollowContractTest
from tests.test_yts_option2 import FakeResponse

fixture = MovieFollowContractTest()
fixture.setUp()
stage = 0
movies = [
    {'title': 'Practical Magic 2', 'year': '2026', 'tmdb_id': '1302904', 'imdb_id': 'tt32588798'},
    {'title': 'The Uprising', 'year': '2026', 'tmdb_id': '977942', 'imdb_id': 'tt36983905'},
    {'title': 'Northspur', 'year': '2021', 'tmdb_id': '842353', 'imdb_id': 'tt8709312'},
]
release_titles = ['Practical Magic 2 (2026) 1080p WEBRip -YTS',
                  'The Rage (2026) 1080p WEBRip -YTS',
                  'Northspur (2022) 1080p BRRip -YTS']


def reset():
    global stage
    stage = 0
    fixture.store.save_followed_all([])
    app._yts_source_identity_cache.clear()
    seeded = [fixture.store.follow_movie({**movie, 'release_date': '2026-01-01'}) for movie in movies]
    for movie in seeded:
        movie['next_check_at'] = app.time.time() + 7 * 86400
    fixture.store.save_followed_all(seeded)


def provider(request, timeout=0):
    url = request.full_url
    if '/api/v1/search?' in url:
        query = parse_qs(urlparse(url).query)['query'][0]
        for index, movie in enumerate(movies):
            if query == movie['imdb_id'] and index <= stage:
                return FakeResponse([{**fixture.release(release_titles[index]),
                                      'infoUrl': f'https://yts.gg/movies/fixture-{index}'}])
        return FakeResponse([])
    if url.startswith('https://yts.gg/movies/fixture-'):
        index = int(url.rsplit('-', 1)[1])
        return FakeResponse(f'<a href="https://www.imdb.com/title/{movies[index]["imdb_id"]}/">IMDb</a>', raw=True)
    return fixture.provider(request, timeout)


app.urllib.request.urlopen = provider
reset()


@app.app.route('/api/test/movie-follow/advance', methods=['POST'])
def advance():
    global stage
    stage = min(2, stage + 1)
    return app.jsonify({'stage': stage})


@app.app.route('/api/test/movie-follow/reset', methods=['POST'])
def reset_fixture():
    reset()
    return app.jsonify({'stage': stage})


app.app.run(host='127.0.0.1', port=port, threaded=True, use_reloader=False)
