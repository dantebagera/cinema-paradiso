"""Explicitly invoked, bounded real-provider timings; separate diagnostic jobs.

Never starts CP, opens consent, copies tokens, applies proposals, or confirms an
action. Uses the existing CP OAuth owner against Dante's selected CP account.
"""
from contextlib import contextmanager, nullcontext
import atexit
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import sys
import tempfile
import threading
import time
from urllib.parse import parse_qs, urlsplit
import uuid

PROJECT = Path(__file__).resolve().parents[1]
PROMPT = 'movies with very twisted story you wont expect the ending'


def safe(value):
    if isinstance(value, dict):
        metrics = {'input_tokens', 'output_tokens', 'total_tokens', 'reasoning_tokens',
                   'input_tokens_details', 'output_tokens_details', 'cached_tokens'}
        return {k: safe(v) for k, v in value.items() if k in metrics or not any(word in k.lower()
                for word in ('token', 'authorization', 'secret', 'credential', 'url', 'api_key', 'headers'))}
    if isinstance(value, (list, tuple)):
        return [safe(v) for v in value]
    return value


class Trace:
    def __init__(self, root):
        self.path = Path(root) / 'timings.jsonl'
        self.zero = time.perf_counter()
        self._lock = threading.Lock()
        self._sequence = 0

    def emit(self, event, **values):
        with self._lock:
            self._sequence += 1
            row = {'sequence': self._sequence, 'event': event,
                   'at_seconds': round(time.perf_counter() - self.zero, 6), **safe(values)}
            with self.path.open('a', encoding='utf-8') as output:
                output.write(json.dumps(row, ensure_ascii=True) + '\n')
        if event in ('gpt_reply', 'first_cards', 'job_finished', 'capture_started', 'gpt_start'):
            print(json.dumps(row), flush=True)

    @contextmanager
    def span(self, phase, **values):
        self.emit('span_start', phase=phase, **values)
        started = time.perf_counter()  # Diagnostic start-marker I/O is not the measured operation.
        try:
            yield
        except BaseException as error:
            self.emit('span_end', phase=phase, seconds=round(time.perf_counter() - started, 6),
                      state='failed', error=getattr(error, 'code', type(error).__name__), **values)
            raise
        else:
            self.emit('span_end', phase=phase, seconds=round(time.perf_counter() - started, 6), state='completed', **values)


class CallBudget:
    def __init__(self, maximum):
        self.maximum, self.used = maximum, 0
        self._lock = threading.Lock()

    def reserve(self):
        with self._lock:
            if self.used >= self.maximum:
                raise RuntimeError('diagnostic_call_budget')
            self.used += 1
            return self.used


def stage_timings(rows, elapsed):
    """Sequential user wait plus separately measured overlapping network work."""
    def duration(phase):
        return sum(row['seconds'] for row in rows if row['event'] == 'span_end' and row.get('phase') == phase)
    gpt, matching = duration('gpt_run'), duration('tmdb_matching')
    def intervals(phase, identity_key):
        starts, spans = {}, []
        for row in rows:
            if row.get('phase') != phase or 'at_seconds' not in row:
                continue
            identity = row.get(identity_key)
            if row['event'] == 'span_start':
                starts[identity] = row['at_seconds']
            elif row['event'] == 'span_end' and identity in starts:
                spans.append((starts.pop(identity), row['at_seconds']))
        merged = []
        for begin, end in sorted(spans):
            if merged and begin <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((begin, end))
        return merged
    tmdb = intervals('tmdb_http', 'request')
    http = intervals('gpt_http', 'attempt')
    overlap = sum(max(0, min(b, d)-max(a, c)) for a, b in tmdb for c, d in http)
    start = next((row['at_seconds'] for row in rows if row['event'] == 'workflow_started'), None)
    first = next((row['at_seconds'] for row in rows if row['event'] == 'first_cards'), None)
    return {'gpt_seconds': round(gpt, 6), 'gpt_http_seconds': round(duration('gpt_http'), 6),
            'matching_after_gpt_seconds': round(matching, 6),
            'tmdb_http_active_seconds': round(sum(end-begin for begin, end in tmdb), 6),
            'gpt_tmdb_overlap_seconds': round(overlap, 6),
            'other_seconds': round(elapsed-gpt-matching, 6),
            'full_seconds': round(elapsed, 6),
            'first_cards_seconds': round(first-start, 6) if first is not None and start is not None else None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--feature', choices=['F1', 'F2', 'F3', 'F4', 'F5'], default='F1')
    parser.add_argument('--label', default='baseline')
    parser.add_argument('--max-calls', type=int, default=6)
    parser.add_argument('--seconds', type=int, default=600)
    parser.add_argument('--prompt', default=PROMPT)
    parser.add_argument('--count', help='Explicit positive recommendation target; otherwise use the saved default')
    parser.add_argument('--slot-diagnostics', action='store_true', help='Isolated in-memory slot/SQLite/logging phase capture')
    parser.add_argument('--plain-control', action='store_true', help='One names/years-only GPT format control; no movie verification claim')
    parser.add_argument('--plain-list', action='store_true', help='Exact user message, no extra instructions or JSON requirement')
    parser.add_argument('--reasoning-effort', choices=['default', 'low'], default='default', help='Diagnostic override only')
    args = parser.parse_args()
    if args.plain_control and args.feature != 'F1':
        parser.error('The format control applies to F1 only')
    if args.slot_diagnostics and args.feature != 'F1':
        parser.error('Slot diagnosis currently supports F1 only')
    if (args.plain_list or args.reasoning_effort != 'default') and not args.plain_control:
        parser.error('Output/effort experiments require --plain-control')
    if not 1 <= args.max_calls <= 6 or not 1 <= args.seconds <= 600:
        parser.error('A capture permits at most six inference attempts and 600 seconds')
    root = Path(tempfile.mkdtemp(prefix='cp-ai-timing-'))
    trace, budget = Trace(root), CallBudget(args.max_calls)
    print('EVIDENCE_ROOT=' + str(root), flush=True)
    cfg = json.loads((PROJECT / 'config.json').read_text(encoding='utf-8'))
    model, account = cfg['chatgpt']['model'], cfg['chatgpt']['active_account_id']
    os.environ.update(CP_TEST_MODE='1', CP_TEST_ROOT=str(root), CP_TEST_QBT_MODE='embedded',
                      CP_TEST_DIST_DIR=str(root / 'dist'), CP_PORT='5118')
    sys.path.insert(0, str(PROJECT))
    import urllib.request
    native_urlopen = urllib.request.urlopen
    with trace.span('isolated_app_import'):
        import app
    from services.ai_jobs import AIJobStore
    from services.ai_provider import AISelection
    from services.chatgpt_auth import ChatGPTAuth
    from services.chatgpt_credentials import CredentialStore
    from services.chatgpt_transport import ChatGPTTransport, PublicOpenAIHTTP, ChatGPTError
    from services.chatgpt_skills import load
    from services.chatgpt_recommendations import Recommender, JobCancellation

    deadline = time.perf_counter() + args.seconds
    app._tmdb_key = cfg['tmdb_key']
    app._tmdb_include_adult = bool(cfg.get('tmdb_include_adult', False))
    tmdb_count = CallBudget(350)

    class TimedResponse:
        def __init__(self, response, started, detail):
            self.response, self.started, self.detail = response, started, detail
        def __enter__(self):
            return self
        def __getattr__(self, name):
            return getattr(self.response, name)
        def __exit__(self, *exception):
            try:
                return self.response.__exit__(*exception)
            finally:
                trace.emit('span_end', phase='tmdb_http', seconds=round(time.perf_counter()-self.started, 6),
                           state='failed' if exception[0] else 'completed', **self.detail)

    def tmdb_open(request, *positional, **options):
        parts = urlsplit(request.full_url if hasattr(request, 'full_url') else request)
        if parts.scheme != 'https' or parts.hostname != 'api.themoviedb.org':
            raise RuntimeError('diagnostic_network_scope')
        if time.perf_counter() >= deadline:
            raise RuntimeError('diagnostic_time_budget')
        number = tmdb_count.reserve()
        query = parse_qs(parts.query)
        detail = {'request': number, 'endpoint': parts.path,
                  'title': query.get('query', [''])[0], 'year': query.get('year', [''])[0]}
        started = time.perf_counter()
        trace.emit('span_start', phase='tmdb_http', **detail)
        try:
            return TimedResponse(native_urlopen(request, *positional, **options), started, detail)
        except Exception as error:
            trace.emit('span_end', phase='tmdb_http', seconds=round(time.perf_counter()-started, 6),
                       state='failed', error=type(error).__name__, **detail)
            raise
    urllib.request.urlopen = tmdb_open

    class TimedHTTP(PublicOpenAIHTTP):
        def stream(self, url, *, payload, token, cancel):
            if args.reasoning_effort != 'default':
                payload = {**payload, 'reasoning': {'effort': args.reasoning_effort}}
            started = time.perf_counter()
            trace.emit('gpt_request_shape', attempt=budget.used,
                       input_utf8_bytes=len(json.dumps(payload.get('input', []), ensure_ascii=False).encode('utf-8')),
                       instructions_utf8_bytes=len(payload.get('instructions', '').encode('utf-8')),
                       tools_utf8_bytes=len(json.dumps(payload.get('tools', []), ensure_ascii=False).encode('utf-8')),
                       payload_utf8_bytes=len(json.dumps(payload, ensure_ascii=False).encode('utf-8')))
            trace.emit('span_start', phase='gpt_http', attempt=budget.used)
            first = True
            first_text = True
            pending = b''
            try:
                for chunk in super().stream(url, payload=payload, token=token, cancel=cancel):
                    if first:
                        trace.emit('gpt_first_bytes', attempt=budget.used, seconds=round(time.perf_counter()-started, 6))
                        first = False
                    pending += chunk
                    while b'\n\n' in pending.replace(b'\r\n', b'\n'):
                        pending = pending.replace(b'\r\n', b'\n')
                        block, pending = pending.split(b'\n\n', 1)
                        for line in block.splitlines():
                            if not line.startswith(b'data: '):
                                continue
                            try:
                                event = json.loads(line[6:])
                            except ValueError:
                                continue
                            if first_text and event.get('type') == 'response.output_text.delta' and event.get('delta'):
                                trace.emit('gpt_first_text', attempt=budget.used,
                                           seconds=round(time.perf_counter()-started, 6))
                                first_text = False
                            if event.get('type') in ('response.output_item.added', 'response.completed', 'response.failed'):
                                trace.emit('gpt_stream_event', attempt=budget.used, type=event['type'],
                                           item_type=event.get('item', {}).get('type'),
                                           seconds=round(time.perf_counter()-started, 6),
                                           usage=event.get('response', {}).get('usage'))
                    yield chunk
            finally:
                trace.emit('span_end', phase='gpt_http', attempt=budget.used,
                           seconds=round(time.perf_counter()-started, 6))

    auth = ChatGPTAuth(CredentialStore(Path(cfg['user_data_dir']) / 'ai/chatgpt'), http=TimedHTTP())
    profiles = auth.credentials.profiles()
    if not any(row['account_id'] == account and row['connected'] and row.get('plan_enabled') for row in profiles):
        raise RuntimeError('Selected CP account is not connected and consented')

    diagnostics = None
    if args.slot_diagnostics:
        from tools.ai_slot_diagnostics import SlotDiagnostics
        diagnostics = SlotDiagnostics(root, trace)
        diagnostics.start()
        atexit.register(diagnostics.close)

    class Store(AIJobStore):
        first_cards = False
        def acquire_inference_slot(self, job_id, cancel=None):
            with trace.span('lease_acquire'):
                with diagnostics.operation('slot_acquire_actual') if diagnostics else nullcontext():
                    return super().acquire_inference_slot(job_id, cancel)
        def release_inference_slot(self, lease_id):
            with trace.span('lease_release'):
                with diagnostics.operation('slot_release_actual') if diagnostics else nullcontext():
                    return super().release_inference_slot(lease_id)
        def is_cancelled(self, job_id):
            return time.perf_counter() >= deadline or super().is_cancelled(job_id)
        def add_results(self, job_id, rows, **options):
            with trace.span('persist_results', count=len(rows)):
                result = super().add_results(job_id, rows, **options)
            if result['accepted_count'] and not self.first_cards:
                self.first_cards = True
                trace.emit('first_cards', count=result['accepted_count'])
            return result

    store = Store(root / 'user-data')
    original_fix_scope = store.fix_scope
    def fix_scope(job_id, scope, **options):
        old = store.snapshot(job_id)['cursor'].get('scope')
        if old and old != scope:
            trace.emit('scope_difference', previous=old, proposed=scope)
        return original_fix_scope(job_id, scope, **options)
    store.fix_scope = fix_scope

    def access_token(account_id):
        with trace.span('account_access'):
            return auth.access_token(account_id)

    def transport_factory(selection, job_id):
        def reserve():
            try:
                budget.reserve()
            except RuntimeError:
                raise ChatGPTError('diagnostic_call_budget') from None
            if time.perf_counter() >= deadline:
                raise ChatGPTError('diagnostic_time_budget')
            with diagnostics.operation('attempt_reserve_actual') if diagnostics else nullcontext():
                store.reserve_inference(job_id)
            trace.emit('gpt_start', attempt=budget.used)
        real = ChatGPTTransport(access_token, http=TimedHTTP(), before_request=reserve,
            inference_slot=lambda cancel: store.inference_slot(job_id, cancel))
        class Runner:
            def run(self, binding, **options):
                with trace.span('gpt_run', input_bytes=len(json.dumps(options['input_items'])),
                                instructions_bytes=len(options['instructions']), tools_bytes=len(json.dumps(options['tools']))):
                    response = real.run(binding, **options)
                trace.emit('gpt_reply', response_id=response.response_id,
                    calls=[{'name': call.name, 'count': len(call.arguments.get('recommendations', []))}
                           for call in response.tool_calls])
                if args.feature == 'F1' and not args.plain_control and response.text:
                    # Public movie suggestions only, never request headers/tokens.
                    trace.emit('gpt_candidate_output', text=response.text)
                return response
        return Runner()

    original_resolve = app._ai_resolve_recommendation
    def resolve(candidate):
        with trace.span('match_candidate', title=candidate['title'], year=candidate.get('year', '')):
            result = original_resolve(candidate)
        trace.emit('candidate_result', title=candidate['title'], accepted_identity=bool(result),
                   resolved_id=(result or {}).get('card', {}).get('tmdb_id'))
        return result
    def scope_context():
        with trace.span('scope_context'):
            return app._ai_scope_context()

    # Composition changes are confined to this disposable process. Jobs and all
    # native domain stores point at its temp root; the account stays in its owner.
    app._ai_provider_config = {key: cfg[key] for key in ('ai_provider', 'chatgpt', 'ai_config_generation') if key in cfg}
    app._get_chatgpt_auth = lambda: auth
    app._get_ai_job_store = lambda: store
    app._get_chatgpt_transport = lambda job_id=None: transport_factory(None, job_id)
    app._plex_url = ''

    native_owner = None
    scope_label = 'actual CP recommendation owners; separate empty session/store; backend-ready time, not rendered paint'
    if args.feature == 'F2':
        args.prompt = 'Find The Prestige (2006) and show its movie card. Read-only lookup; do not prepare an action.'
        scope_label = 'actual CP Agent/full tool composition; one public Movie lookup; no confirmation or writes'
    elif args.feature == 'F3':
        if not cfg['chatgpt'].get('allow_movie_identity_hints'):
            raise RuntimeError('Movie title-hint permission is off')
        args.prompt = 'Synthetic Movie Smart Match batch: Alien (1979), The Prestige (2006)'
        library = root / 'synthetic-library'
        library.mkdir()
        app._movies_dirs, app._movies_dir = [str(library)], str(library)
        paths = []
        for name, title, year in [('Alien.1979.mkv', 'Alien', '1979'), ('The.Prestige.2006.mkv', 'The Prestige', '2006')]:
            path = library / name
            path.write_bytes(b'SYNTHETIC NON-PLAYABLE DIAGNOSTIC')
            app._metadata_store().update_file_record(str(path), {'filename': name, 'library_root': str(library),
                'size': path.stat().st_size, 'identity_status': 'unmatched', 'metadata_status': 'unmatched',
                'identity_revision': 1, 'parsed_title': title, 'parsed_year': year, 'exists': True})
            paths.append(str(path))
        scope_label = 'actual native Movie Smart Match coordinator, synthetic two-file batch, real GPT/TMDB, no metadata apply'
    elif args.feature in ('F4', 'F5'):
        if not cfg['chatgpt'].get('allow_iptv_titles'):
            raise RuntimeError('IPTV title permission is off')
        from services.iptv_metadata_settings import IPTVMetadataSettings
        from services.iptv_movie_service import IPTVMovieService
        from services.iptv_movie_store import source_key
        from tests.iptv_movie_fixtures import create_raw_service
        private_settings = IPTVMetadataSettings(cfg['user_data_dir'])._load_private()
        class DiagnosticSettings(IPTVMetadataSettings):
            def _load_private(self):
                return dict(private_settings)
        settings = DiagnosticSettings(root/'user-data')
        if args.feature == 'F5' and not settings.public()['tmdb_configured']:
            raise RuntimeError('IPTV native TMDB settings are not configured')
        provider_id = 'd' * 32
        raw = create_raw_service(root/'user-data', provider_id, movie_rows=[
            {'stream_id': '10', 'name': 'Alien (1979)', 'category_id': 'movies-a', 'year': '1979'},
            {'stream_id': '11', 'name': 'The Prestige (2006)', 'category_id': 'movies-a', 'year': '2006'}])
        native_owner = IPTVMovieService(raw.root, provider_id, raw, settings)
        native_owner.start_projection(wait=True)
        if args.feature == 'F5':
            native_owner.store.apply_classification_decisions([
                {'source_key': source_key(identity), 'category': 'film', 'method': 'diagnostic', 'confidence': 1}
                for identity in ('10', '11')])
        snapshot = native_owner.store.resolve_selection(selected_keys=['source:'+source_key(identity) for identity in ('10','11')])
        args.prompt = 'Synthetic two-title IPTV classification' if args.feature == 'F4' else 'Synthetic two-title IPTV supplied-candidate matching'
        scope_label = 'actual native IPTV preview/job owners; synthetic provider/two titles; real GPT/TMDB as required; no Apply'

    skill = load(args.feature)
    selected = AISelection('chatgpt', cfg.get('ai_config_generation', 0), account, model,
                           skill['id'], skill['version'], skill['hash'], args.feature,
                           native_owner.provider_id if native_owner else None)
    request = {'prompt': args.prompt}
    if args.feature == 'F1':
        request.update(count=args.count or cfg['chatgpt']['recommendation_count'],
                       count_source='explicit' if args.count is not None else 'settings')
    trace.emit('capture_started', feature=args.feature, label=args.label, prompt=args.prompt,
               model=model, count=request.get('count'), maximum_calls=args.max_calls, maximum_seconds=args.seconds,
               reasoning_effort=args.reasoning_effort, output_format='plain-list' if args.plain_list else 'JSON/tools',
               cache_state='fresh diagnostic process; no production TMDB memory cache')
    started = time.perf_counter()
    trace.emit('workflow_started')
    service = None
    control_count = None
    try:
        if args.feature == 'F3':
            request.update(paths=paths, database='tmdb')
        if native_owner:
            request['selection_snapshot'] = snapshot
        job = store.create(args.feature, selected, request, 'timed-' + uuid.uuid4().hex)
        with trace.span('feature_total'):
            if args.plain_control:
                store.start_run(job['id'], job['revision'])
                response = transport_factory(selected, job['id']).run(selected,
                    instructions='' if args.plain_list else ('Recommend '+request['count']+' distinct released feature-length movies matching the user request. '
                        'Return only JSON {"recommendations":[{"title":"Movie title","year":"YYYY"}]}. '
                        'No reasons, planning, spoilers, tools or additional fields.'),
                    input_items=[{'role': 'user', 'content': args.prompt}], tools=[],
                    cancel=JobCancellation(store, job['id']))
                control_count = (len(re.findall(r'(?m)^.*\b(?:19|20)\d{2}\b.*$', response.text)) if args.plain_list
                                 else len(json.loads(response.text)['recommendations']))
                trace.emit('plain_candidate_output', text=response.text)
                store.finish(job['id'], 'completed', output={'unverified_suggestion_count': control_count})
                scope_label = 'names/years-only GPT output-format control; no TMDB matching or verified-result claim'
            elif args.feature == 'F1':
                catalogue = app._get_ai_catalogue()
                original_eligibility = catalogue.candidate_eligibility
                def eligibility(movie, query, **options):
                    with trace.span('candidate_eligibility', title=movie.get('title'), identity=movie.get('id')):
                        result = original_eligibility(movie, query, **options)
                    trace.emit('eligibility_result', identity=movie.get('id'), title=movie.get('title'), result=result)
                    return result
                catalogue.candidate_eligibility = eligibility
                runner = Recommender(store, transport_factory, resolve, catalogue=catalogue,
                                     scope_context=scope_context, validate_identities=app._ai_validate_query_identities,
                                     measure_phase=trace.span)
                runner.run(job['id'])
            elif args.feature in ('F2', 'F3'):
                service = app._get_ai_job_service()
                if args.feature == 'F3':
                    app._get_smart_match_coordinator().start(paths, 'tmdb', 'ai', background=False,
                        ai_binding={'ai_job_id': job['id'], 'selection': selected.public()})
                service.handlers[args.feature](job['id'])
            else:
                from services.chatgpt_iptv import IPTVJob
                runner = IPTVJob(store, lambda identity: native_owner, transport_factory)
                runner.run(job['id'])
        result = store.snapshot(job['id'], page_size=100)
        elapsed = time.perf_counter()-started
        timings = stage_timings([json.loads(line) for line in trace.path.read_text().splitlines()], elapsed)
        summary = {'feature': args.feature, 'label': args.label, 'model': model, 'prompt': args.prompt,
                   'state': result['state'], 'message': result['message'], 'requested_count': result['requested_count'],
                   'accepted_count': result['accepted_count'], 'inference_attempts': budget.used,
                   'tmdb_requests': tmdb_count.used, 'elapsed_seconds': round(elapsed, 6), 'timings': timings,
                   'cards': result['results'], 'job_id': job['id'],
                   'unverified_control_count': control_count,
                   'reasoning_effort': args.reasoning_effort,
                   'output_format': 'plain-list' if args.plain_list else 'JSON/tools',
                   'source_hash': hashlib.sha256((PROJECT/'services/chatgpt_recommendations.py').read_bytes()).hexdigest(),
                   'scope': scope_label}
        if diagnostics:
            summary['slot_diagnostics'] = diagnostics.summary()
        (root/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
        trace.emit('job_finished', **{k: summary[k] for k in ['state','message','accepted_count','inference_attempts','tmdb_requests','elapsed_seconds']})
        print('TIMINGS=' + json.dumps(timings), flush=True)
    finally:
        if service:
            service.close()
        auth.close()
        if diagnostics:
            diagnostics.close()


if __name__ == '__main__':
    main()
