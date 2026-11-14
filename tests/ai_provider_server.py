"""Offline AI fixture composition. Never starts CP background/runtime managers."""
from contextlib import ExitStack
import json
import os
from pathlib import Path
import tempfile
import sys
from types import SimpleNamespace
from unittest.mock import patch


def validate_environment(env=None):
    env = os.environ if env is None else env
    if env.get('CP_TEST_MODE') != '1' or not env.get('CP_TEST_ROOT'):
        raise RuntimeError('AI offline fixtures require isolated test mode')
    root = Path(env['CP_TEST_ROOT']).resolve()
    if root == Path(tempfile.gettempdir()).resolve() or Path(tempfile.gettempdir()).resolve() not in root.parents:
        raise RuntimeError('AI offline fixtures require a unique OS-temp root')
    if str(env.get('CP_PORT', '5117')) in ('5000', '11434', '32400', '18686'):
        raise RuntimeError('A live service port cannot be used for AI offline fixtures')
    dist = Path(env.get('CP_TEST_DIST_DIR') or root / 'dist').resolve()
    if not dist.is_relative_to(root):
        raise RuntimeError('AI offline dist must be inside its isolated root')
    return root


class OfflineGuard(ExitStack):
    def __enter__(self):
        super().__enter__()
        validate_environment()
        def blocked(*args, **kwargs):
            raise RuntimeError('AI offline containment blocked an external connection or runtime launch')
        for target in ['socket.socket.connect', 'socket.socket.connect_ex', 'socket.create_connection',
                       'subprocess.Popen', 'urllib.request.urlopen', 'requests.sessions.Session.request',
                       'webbrowser.open']:
            self.enter_context(patch(target, side_effect=blocked))
        if hasattr(os, 'startfile'):
            self.enter_context(patch('os.startfile', side_effect=blocked))
        return self

    def __exit__(self, *args):
        result = super().__exit__(*args)
        # Preserve app's stricter test-mode network policy after the import scope.
        owner = sys.modules.get('app')
        if owner is not None and getattr(owner, '_TEST_MODE', False):
            import urllib.request
            urllib.request.urlopen = owner._blocked_test_urlopen
        return result


class _JsonResponse:
    def __init__(self, value):
        self.value = value
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, *args):
        return json.dumps(self.value, ensure_ascii=False).encode()


def capture_legacy():
    """Synthetic legacy contracts through the actual owners, with no remote I/O."""
    import app
    from services import ai_control
    from services.iptv_movie_service import IPTVMovieService
    captured = {}
    requests = []
    def chat_wire(url, endpoint, *, payload, timeout=60):
        requests.append({'endpoint': endpoint, 'payload': payload, 'timeout': timeout})
        return {'message': {'content': json.dumps({'recommendations': [
            {'title': 'Fixture Movie', 'year': '2001', 'reason': 'Synthetic reason.'},
            {'title': 'Fixture Movie', 'year': '2001', 'reason': 'Duplicate.'}]})}}
    with patch.multiple(app, _ollama_url='http://offline.invalid', _ollama_model='fixture-model',
                        _ollama_candidate_limit=15, _tmdb_key=''), patch.object(app, '_ollama_api_json', side_effect=chat_wire):
        response = app.app.test_client().post('/api/ollama/recommend', json={'prompt': 'Synthetic mood'})
        captured['F1'] = {'requests': requests.copy(), 'status': response.status_code, 'output': response.get_json()}
    calls = []
    def interpretation(messages):
        calls.append(messages)
        if len(calls) == 1:
            return 'invalid json'
        return json.dumps({'action': 'find', 'subject': 'Fixture', 'subject_type': 'title'})
    captured['F2'] = {'output': ai_control._parse_intent('Find Fixture', config=ai_control.default_config(), ollama_chat=interpretation),
                      'requests': calls}
    calls = []
    def identity(messages):
        calls.append(messages)
        return json.dumps({'matches': [] if len(calls) == 1 else [
            {'id': 'fixture-1', 'title': 'Fixture Movie', 'year': '2001', 'alternatives': []}]})
    with patch.object(app, '_ollama_chat_content', side_effect=identity):
        output = app._smart_match_ai_batch([{'id': 'fixture-1', 'filename': 'Fixture.2001.mkv',
                                           'folder_name': 'Fixture (2001)', 'title_hint': '', 'year_hint': ''}])
    captured['F3'] = {'requests': calls, 'output': output}
    classification = {'category': 'Film', 'confidence': 0.95, 'evidence_summary': 'Synthetic evidence',
                      'mixed': False, 'uncertain': False, 'title_exceptions': []}
    with tempfile.TemporaryDirectory(dir=os.environ['CP_TEST_ROOT']) as temporary:
        calls = []
        def classify(evidence):
            calls.append(evidence)
            return classification
        service = IPTVMovieService(temporary, 'offline-fixture', None, SimpleNamespace(), ollama_runner=classify)
        captured['F4'] = {'output': service._ollama_classification_decision('Fixture Films', ['Fixture Movie']),
                          'requests': calls}
        settings = SimpleNamespace(public=lambda: {'ollama_enabled': True, 'ollama_url': 'http://127.0.0.1:11434',
                                                   'ollama_model': 'fixture-model'})
        service.metadata_settings = settings
        wire = []
        def generate(request, timeout):
            wire.append({'url': request.full_url, 'body': json.loads(request.data), 'timeout': timeout})
            return _JsonResponse({'response': '{"tmdb_id":123}'})
        evidence = {'mode': 'rank-real-tmdb-candidates', 'title': 'Fixture Movie', 'year': 2001,
                    'candidates': [{'tmdb_id': 123, 'title': 'Fixture Movie', 'year': 2001, 'deterministic_score': 100}]}
        with patch('urllib.request.urlopen', side_effect=generate):
            output = service._run_ollama(evidence)
        captured['F5'] = {'requests': wire, 'output': output}
        IPTVMovieService._instances.pop('offline-fixture', None)
    return captured


def compose(guard=None):
    validate_environment()
    # Caller keeps OfflineGuard alive for the entire server/test lifetime.
    import app
    app._qbt_mode = 'embedded'
    app._tmdb_key = ''
    app._plex_token = ''
    app._ollama_url = ''
    app._start_background_services = lambda: (_ for _ in ()).throw(RuntimeError('Offline fixtures cannot start services'))
    if guard is not None:
        from tests.ai_provider_fixture import install
        app._ai_desktop_fixture = install(app, guard)
    return app


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--qualify', action='store_true')
    args = parser.parse_args()
    with OfflineGuard() as guard:
        owner = compose(guard)
        if args.qualify:
            from tests.ai_provider_fixture import verify_matrix
            print('AI_MATRIX=' + json.dumps(verify_matrix(owner)), flush=True)
            return
        owner.app.run(host='127.0.0.1', port=int(os.environ.get('CP_PORT', '5117')),
                      threaded=True, use_reloader=False)


if __name__ == '__main__':
    main()
