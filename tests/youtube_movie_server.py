"""Disposable real HTTP/UI fixture: only upstream YouTube and TMDB are replaced."""
import os
from flask import jsonify
if os.environ.get('CP_TEST_MODE') != '1':
    raise RuntimeError('Requires isolated CP test mode')
import app
from tests.test_youtube_movies import video

app._streaming_enabled = True
app._youtube_service.api_key = 'fixture-not-a-real-key'
app._youtube_movie_search.details = lambda identity: {
    'id': int(identity), 'title': 'Terrorism and Kebab', 'original_title': 'الإرهاب والكباب',
    'original_language': 'ar', 'runtime': 100, 'release_date': '1992-01-01'}
calls = []
rows = {v['id']: v for v in [video('aaaaaa1', 5700, 'الإرهاب والكباب كامل'),
    video('aaaaaa2', 6300, 'الإرهاب والكباب نسخة أخرى', embeddable=False),
    video('aaaaaa3', 6301, 'الإرهاب والكباب خارج المدة'),
    video('aaaaaa4', 5699, 'الإرهاب والكباب مقطع'),
    video('aaaaaa5', 6000, 'الإرهاب والكباب ' + 'نسخة كاملة باللغة العربية ' * 12)]}


def youtube(path, params):
    calls.append({'path': path, 'params': params})
    if path == 'search':
        identities = ['aaaaaa1', 'aaaaaa2', 'aaaaaa3', 'aaaaaa4'] if not params.get('pageToken') else ['aaaaaa1', 'aaaaaa5']
        return {'items': [{'id': {'videoId': identity}} for identity in identities],
                'nextPageToken': '' if params.get('pageToken') else 'next'}
    if path == 'videos':
        return {'items': [rows[identity] for identity in params['id'].split(',')]}
    raise AssertionError('Unexpected YouTube call')


app._youtube_service._request_json = youtube


@app.app.get('/__test/youtube-calls')
def test_calls():
    return jsonify(calls)


if __name__ == '__main__':
    app.app.run(host='127.0.0.1', port=int(os.environ.get('CP_PORT', '5140')), threaded=True, use_reloader=False)
