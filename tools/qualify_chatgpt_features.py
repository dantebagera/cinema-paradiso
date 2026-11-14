"""Five one-shot synthetic protocol qualifications after Dante's real Task 0 gate.

Uses only that explicitly connected OS-temp registration. Never imports app,
opens a browser, copies credentials, applies catalogue changes or submits media.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import threading

if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

FEATURES = ('F1', 'F2', 'F3', 'F4', 'F5')


class FeatureBudget:
    def __init__(self, root, model):
        self.root = Path(root)
        gate = json.loads((self.root / 'preflight-qualification.json').read_text())
        if gate.get('state') != 'passed' or gate.get('inference_calls') != 1 or gate.get('model') != model:
            raise ValueError('The passed user-selected Task 0 gate is required')
        self.directory = self.root / 'feature-qualification'

    def reserve(self, feature):
        if feature not in FEATURES:
            raise ValueError('Unknown qualification feature')
        self.directory.mkdir(exist_ok=True)
        # Exclusive creation is the cross-process budget claim. An interrupted or
        # failed request remains consumed, and a feature can never make a repair.
        with (self.directory / (feature + '.json')).open('x', encoding='utf-8') as output:
            json.dump({'feature': feature, 'state': 'reserved', 'inference_calls': 1}, output)
            output.flush()
            os.fsync(output.fileno())

    def record(self, feature, result):
        if feature not in FEATURES:
            raise ValueError('Unknown qualification feature')
        destination = self.directory / (feature + '.json')
        if not destination.is_file():
            raise ValueError('No inference reservation exists')
        temporary = destination.with_suffix('.tmp')
        temporary.write_text(json.dumps({'feature': feature, 'inference_calls': 1, **result}, indent=2), encoding='utf-8')
        os.replace(temporary, destination)


def qualify(root, account_id, model, features=FEATURES):
    from tools.chatgpt_login_preflight import validate_root
    from services.chatgpt_auth import ChatGPTAuth
    from services.chatgpt_credentials import CredentialStore
    from services.chatgpt_transport import ChatGPTTransport, ChatGPTError
    from services.chatgpt_skills import load
    from services.ai_provider import AISelection
    from services.ai_jobs import AIJobStore
    from services.advanced_search import normalize_query
    from services.chatgpt_matching import MovieIdentity
    from services.chatgpt_iptv import IPTVInference
    from services.chatgpt_tools import ChatGPTTools, ToolContext
    root = validate_root(root)
    budget = FeatureBudget(root, model)
    auth = ChatGPTAuth(CredentialStore(root / 'ai/chatgpt'))
    profile = next((row for row in auth.credentials.profiles() if row['account_id'] == account_id), None)
    if not profile or not profile.get('connected') or not profile.get('plan_enabled'):
        raise ValueError('The explicitly connected account is unavailable')
    store = AIJobStore(root / 'feature-qualification-data')
    def selection(feature):
        skill = load(feature)
        return AISelection('chatgpt', 0, account_id, model, skill['id'], skill['version'], skill['hash'], feature)
    models = ChatGPTTransport(auth.access_token, max_retries=0,
        inference_slot=lambda cancel: store.inference_slot('qualification-models', cancel)).list_models(selection('F1'))
    if not any(row['slug'] == model for row in models):
        raise ValueError('The user-selected model is no longer in this account catalogue')
    reports = []
    if not features or len(set(features)) != len(features) or any(feature not in FEATURES for feature in features):
        raise ValueError('Choose each qualification feature at most once')
    for feature in features:
        selected = selection(feature)
        request = {'prompt': 'Recommend the one supplied synthetic qualification fixture: Alien (1979).', 'count': '1'} if feature == 'F1' else {'prompt': 'Synthetic ' + feature + ' qualification'}
        job = store.create(feature, selected, request, 'real-protocol-' + feature)
        store.start_run(job['id'], job['revision'])
        observed = []
        def reserve():
            try:
                budget.reserve(feature)
            except FileExistsError:
                raise ChatGPTError('qualification_feature_budget_used') from None
            store.reserve_inference(job['id'])
        real = ChatGPTTransport(auth.access_token, max_retries=0, before_request=reserve,
            inference_slot=lambda cancel: store.inference_slot(job['id'], cancel))
        class Runner:
            def run(self, binding, **options):
                options['instructions'] += ('\nSynthetic, one-response protocol qualification. Follow the user-supplied '
                    'fixture facts exactly. Do not search, resolve other titles, request more evidence, or call tools '
                    'in another response. This qualification permits one HTTP inference only.')
                if feature == 'F1':
                    options['instructions'] += (' In THIS response return JSON with the supplied '
                        'Alien (1979) recommendation and its required scope: empty advanced discover query '
                        '(version 1, scope discover, mode advanced, feed catalog, sort auto desc, groups []), '
                        'subjective_requirements [], requested_count null. Full TMDB matching semantics '
                        'are tested separately; this response checks the typed protocol only.')
                response = real.run(binding, **options)
                observed.append(response)
                budget.record(feature, {'state': 'response_received', 'model': model,
                    'response_id': response.response_id, 'tool_names': [call.name for call in response.tool_calls]})
                return response
        runner = Runner()
        try:
            if feature == 'F1':
                response = runner.run(selected, instructions=load('F1')['instructions'], input_items=[
                    {'role': 'user', 'content': request['prompt']}], tools=load('F1')['tools'], cancel=threading.Event())
                from services.chatgpt_recommendations import parse_result
                arguments = parse_result(response, load('F1'))['scope']
                query = normalize_query(arguments['query'], 'discover')
                store.fix_scope(job['id'], {'query': query, 'subjective_requirements': arguments['subjective_requirements']})
                store.finish(job['id'], 'partial', message='Single-hop qualification validates scope and candidate shape; no real TMDB verification is claimed.')
            elif feature == 'F2':
                registry = ChatGPTTools({'playback_status': lambda args, context: {'state': 'stopped', 'synthetic': True}})
                context = ToolContext(selected, job['id'], job['session_id'])
                response = runner.run(selected, instructions=load('F2')['instructions'], input_items=[{'role': 'user',
                    'content': 'Read the synthetic playback status. Call cp_runtime.playback_status exactly once with {}. No other action.'}],
                    tools=registry.available(selected, context), cancel=threading.Event())
                assert len(response.tool_calls) == 1 and response.tool_calls[0].name == 'cp_runtime.playback_status'
                result = registry.call(response.tool_calls[0].name, response.tool_calls[0].arguments, context)
                assert result.model['state'] == 'stopped'
                store.finish(job['id'], 'completed', output={'synthetic_read': result.model})
            elif feature == 'F3':
                result = MovieIdentity(runner).identify(selected, [{'id': 'qualification-file', 'filename': 'Qualifié.Alien.1979.mkv',
                    'title_hint': 'Alien', 'year_hint': '1979'}], cancel=threading.Event())
                assert not result['errors'] and result['matches']['qualification-file']['title'].casefold() == 'alien', result
                store.finish(job['id'], 'completed')
            elif feature == 'F4':
                result = IPTVInference(runner).classify(selected, 'Synthetic feature film shelf', ['Alien (1979)'], cancel=threading.Event())
                assert result['category'].casefold() == 'film' and not result.get('uncertain'), result
                store.finish(job['id'], 'completed')
            else:
                result = IPTVInference(runner).rank(selected, {'mode': 'rank-real-tmdb-candidates', 'title': 'Alien', 'year': 1979,
                    'candidates': [{'tmdb_id': 348, 'title': 'Alien', 'year': 1979, 'deterministic_score': 100}]}, cancel=threading.Event())
                assert result['tmdb_id'] == 348, result
                store.finish(job['id'], 'completed')
            assert len(observed) == 1
            report = {'state': 'passed', 'model': model, 'response_id': observed[0].response_id,
                      'tool_names': [call.name for call in observed[0].tool_calls], 'skill_hash': selected.skill_hash,
                      'scope': 'single synthetic feature protocol response; full app semantics verified offline'}
            if feature == 'F1':
                report.update(state='scope_declaration_verified', recommendation_output_verified_real=False)
        except Exception as error:
            report = {'state': 'failed', 'model': model, 'code': error.code if isinstance(error, ChatGPTError) else 'feature_qualification_failed'}
            if observed:
                report.update(response_id=observed[0].response_id,
                              tool_names=[call.name for call in observed[0].tool_calls])
            if (budget.directory / (feature + '.json')).exists():
                budget.record(feature, report)
            print(json.dumps({'feature': feature, **report}), flush=True)
            raise RuntimeError('Qualification stopped; reserved requests will not be replayed') from None
        budget.record(feature, report)
        reports.append(report)
        print(json.dumps({'feature': feature, **report}), flush=True)
    auth.close()
    return reports


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True)
    parser.add_argument('--account', required=True)
    parser.add_argument('--model', required=True)
    parser.add_argument('--features', nargs='+', choices=FEATURES, default=FEATURES)
    args = parser.parse_args()
    qualify(args.root, args.account, args.model, args.features)
