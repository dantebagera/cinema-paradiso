"""Generic AI HTTP composition; no inference or catalogue business rules."""
from functools import wraps
import threading
from urllib.parse import urlsplit
from flask import jsonify, request
from services.ai_jobs import BULK_OUTCOMES, bulk_catalog_generation, bulk_extra_calls, bulk_failed_after_sync, supports_bulk_catalog_resume
from services.ai_provider import AIProviderError
from services.iptv_movie_store import IPTVSelectionError


def local_json(handler=None, *, max_bytes=65536):
    if handler is None:
        return lambda function: local_json(function, max_bytes=max_bytes)
    @wraps(handler)
    def guarded(*args, **kwargs):
        host = urlsplit('http://' + request.host).hostname
        origin = request.headers.get('Origin')
        if (host not in ('localhost', '127.0.0.1', '::1') or request.remote_addr not in ('127.0.0.1', '::1', None)
                or request.headers.get('Sec-Fetch-Site') == 'cross-site'
                or (origin is not None and origin != request.host_url.rstrip('/'))):
            return jsonify(error={'code': 'invalid_local_request'}), 403
        if not request.is_json:
            return jsonify(error={'code': 'json_required'}), 415
        if request.content_length is not None and request.content_length > max_bytes:
            return jsonify(error={'code': 'request_too_large'}), 413
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(error={'code': 'invalid_json'}), 400
        try:
            return handler(data, *args, **kwargs)
        except AIProviderError as error:
            return jsonify(error={'code': error.code}), error.status
        except Exception as error:
            from services.ai_jobs import AIJobError
            from services.chatgpt_transport import ChatGPTError
            if isinstance(error, AIJobError):
                return jsonify(error={'code': error.code, **getattr(error, 'details', {})}), error.status
            if isinstance(error, ChatGPTError):
                return jsonify(error=error.public()), 502
            return jsonify(error={'code': 'ai_operation_failed'}), 500
    return guarded


def register_ai_routes(app, provider, *, auth_factory=None, transport_factory=None, jobs_factory=None,
                       control_factory=None, check_permission=lambda selection: None, iptv_factory=None):
    @app.before_request
    def ai_admission():
        private_read = request.path.startswith('/api/ai/') or (
            request.path.startswith('/api/iptv/providers/') and request.path.endswith('/movies/ai/bulk-jobs/latest'))
        if private_read and request.method in ('GET', 'HEAD'):
            host = urlsplit('http://' + request.host).hostname
            origin = request.headers.get('Origin')
            if (host not in ('localhost', '127.0.0.1', '::1') or request.remote_addr not in ('127.0.0.1', '::1', None)
                    or request.headers.get('Sec-Fetch-Site') == 'cross-site'
                    or (origin is not None and origin != request.host_url.rstrip('/'))):
                return jsonify(error={'code': 'invalid_local_request'}), 403
        if request.path == '/api/ollama/recommend' and provider._config()['provider'] == 'chatgpt':
            return jsonify(error={'code': 'selected_provider_requires_ai_job_route'}), 409

    def auth():
        if auth_factory is None:
            raise AIProviderError('authentication_unavailable', 503)
        return auth_factory()

    def transport():
        if transport_factory:
            return transport_factory()
        from services.chatgpt_transport import ChatGPTTransport
        return ChatGPTTransport(auth().access_token)

    def fields(data, allowed):
        if set(data) - set(allowed):
            raise AIProviderError('unknown_field')

    def jobs():
        if jobs_factory is None:
            raise AIProviderError('jobs_unavailable', 503)
        return jobs_factory()

    def owned_job(job_id, **page):
        operation = jobs().store.snapshot(job_id, **page)
        if operation['selection']['account_id'] != provider.connection_selection().account_id:
            raise AIProviderError('job_account_mismatch', 403 if page.get('review_view') else 409)
        return operation

    def job_page():
        options = {'page': int(request.args.get('page', 1)), 'page_size': int(request.args.get('page_size', 20)),
                   'cursor': request.args.get('cursor')}
        if request.args.get('review_view') is not None:
            options['review_view'] = request.args['review_view']
        return options

    def present_job(operation):
        if operation is None or 'bulk_call_budget' not in operation.get('request', {}):
            return operation
        cursor = operation['cursor']
        snapshot = operation['request']['selection_snapshot']
        apply = operation.get('bulk_apply')
        work = cursor.get('bulk_work', {})
        recovery = work.get('recovery', {})
        recheck = cursor.get('bulk_search_recheck')
        public = {key: value for key, value in operation.items() if key not in ('bulk_apply', 'search_recheck_candidates')}
        return {**public, 'request': {'bulk_call_budget': operation['request']['bulk_call_budget'],
                                        'titles_per_request': operation['request'].get('titles_per_request', 100)},
            'cursor': {'run_number': cursor.get('run_number', 0)},
            'bulk': {'processed': operation['accepted_count'], 'total': len(snapshot['source_keys']),
                     'search_recheck_candidates': operation.get('search_recheck_candidates', 0),
                     'search_recheck': {'processed': recheck['processed'], 'total': len(recheck['keys']),
                                        'verified': recheck['verified']} if recheck else None,
                     'catalog_generation': bulk_catalog_generation(operation),
                     'resume_after_sync': bulk_failed_after_sync(operation),
                     'catalog_resume_supported': supports_bulk_catalog_resume(operation['request']),
                     'automatic': bool(operation['request'].get('bulk_auto_apply')),
                     'recovery_enabled': bool(operation['request'].get('bulk_recovery_protocol_hash')),
                     'phase': work.get('phase'),
                     'local_checked': work.get('offset', 0),
                     'previously_checked': work.get('previously_checked', 0),
                     'local_window_end': work.get('window_end', 0),
                     'first_pass_resolved': work.get('first_pass_resolved', 0),
                     'estimated_first_pass_requests': operation['request'].get('estimated_first_pass_requests'),
                     'recovery': {key: recovery.get(key, 0) for key in ('admitted', 'requests', 'completed')}
                                 | {'in_flight': len(recovery.get('in_flight', []))},
                     'automatic_counts': cursor.get('bulk_automatic_counts'),
                     'selection_scope': {'mode': snapshot.get('mode', ''), 'filters': snapshot.get('filters', {})},
                     'apply': {key: apply[key] for key in ('id', 'state', 'total', 'counts')}
                              | {'reason': apply.get('reason', ''), 'automatic': apply.get('automatic', False)} if apply else None,
                     'counts': cursor.get('bulk_counts', dict.fromkeys(BULK_OUTCOMES, 0)),
                     'checkpoint_at': cursor.get('checkpoint_at'),
                     'extra_calls': bulk_extra_calls(operation['request'], cursor) if operation['state'] == 'paused_budget' else 0,
                     'pause_requested': operation['state'] == 'running' and bool(cursor.get('bulk_pause_requested'))}}
    @app.get('/api/ai/config')
    def ai_config_get():
        return jsonify(provider.public_config())

    @app.put('/api/ai/config')
    @local_json
    def ai_config_put(data):
        payload = dict(data)
        generation = payload.pop('expected_generation', None)
        return jsonify(provider.update_config(payload, generation))

    @app.get('/api/ai/features')
    def ai_features():
        return jsonify(features=provider.features(request.args.get('provider_id')))

    @app.post('/api/ai/auth/start')
    @local_json
    def ai_auth_start(data):
        fields(data, ('account_id',))
        return jsonify(auth().start(account_id=data.get('account_id')))

    @app.get('/api/ai/auth/attempts/<attempt_id>')
    def ai_auth_status(attempt_id):
        try:
            return jsonify(auth().status(attempt_id))
        except Exception:
            return jsonify(error={'code': 'attempt_unavailable'}), 404

    @app.delete('/api/ai/auth/attempts/<attempt_id>')
    @local_json
    def ai_auth_cancel(data, attempt_id):
        fields(data, ())
        auth().cancel(attempt_id)
        return jsonify(auth().status(attempt_id))

    @app.post('/api/ai/accounts/select')
    @local_json
    def ai_account_select(data):
        fields(data, ('account_id', 'expected_generation'))
        return jsonify(provider.update_config({'active_account_id': data.get('account_id')}, data.get('expected_generation')))

    @app.delete('/api/ai/accounts/<account_id>/session')
    @local_json
    def ai_account_signout(data, account_id):
        fields(data, ())
        return jsonify(auth().sign_out(account_id))

    @app.get('/api/ai/models')
    def ai_models():
        try:
            return jsonify(models=transport().list_models(provider.connection_selection()))
        except AIProviderError as error:
            return jsonify(error={'code': error.code}), error.status
        except Exception as error:
            from services.chatgpt_transport import ChatGPTError
            return jsonify(error=error.public() if isinstance(error, ChatGPTError) else {'code': 'models_unavailable'}), 502

    @app.post('/api/ai/test')
    @local_json
    def ai_connection_test(data):
        fields(data, ())
        runner = transport()
        if hasattr(runner, 'max_retries'):
            runner.max_retries = 0  # The explicit connection button sends one request.
        result = runner.run(provider.connection_selection(require_model=True),
            instructions='Return only the exact requested connection-check text.',
            input_items=[{'role': 'user', 'content': 'Say exactly: CP_CONNECTION_OK'}],
            tools=[], cancel=threading.Event())
        if result.text.strip() != 'CP_CONNECTION_OK':
            raise AIProviderError('unexpected_connection_response', 502)
        return jsonify(success=True, response_id=result.response_id)

    @app.post('/api/ai/recommendations')
    @local_json
    def ai_recommendations(data):
        fields(data, ('prompt', 'count', 'session_id', 'request_key'))
        if not isinstance(data.get('prompt'), str) or not data['prompt'].strip():
            raise AIProviderError('prompt_required')
        selection = provider.snapshot('F1')
        if selection.provider != 'chatgpt':
            raise AIProviderError('selected_provider_requires_ollama_route', 409)
        request_data = {key: data[key] for key in ('prompt', 'session_id') if key in data}
        config = provider.public_config()
        request_data['count'] = data.get('count', config['chatgpt']['recommendation_count'])
        request_data['count_source'] = 'explicit' if 'count' in data else 'settings'
        service = jobs()
        operation = service.store.create('F1', selection, request_data, data.get('request_key'))
        service.start(operation['id'])
        return jsonify({**operation, 'job_id': operation['id']}), 202

    @app.get('/api/ai/jobs/<job_id>')
    def ai_job_status(job_id):
        try:
            return jsonify(present_job(owned_job(job_id, **job_page())))
        except AIProviderError as error:
            status = 401 if request.args.get('review_view') and error.code == 'account_disconnected' else error.status
            return jsonify(error={'code': error.code}), status
        except Exception as error:
            from services.ai_jobs import AIJobError
            status = 500 if request.args.get('review_view') is not None and not isinstance(error, ValueError) else 400
            return jsonify(error={'code': error.code if isinstance(error, AIJobError) else 'job_unavailable'}), getattr(error, 'status', status)

    def create_iptv_operation(data, provider_id, feature):
        fields(data, ('selection_mode', 'selected_keys', 'filters', 'page', 'page_size', 'request_key'))
        if iptv_factory is None:
            raise AIProviderError('iptv_unavailable', 503)
        selection = provider.snapshot(feature, domain_id=provider_id)
        if selection.provider != 'chatgpt':
            raise AIProviderError('selected_provider_requires_ollama_route', 409)
        owner = iptv_factory(provider_id)
        try:
            resolved = owner.store.resolve_selection(mode=data.get('selection_mode', 'explicit'),
                selected_keys=data.get('selected_keys') or [], filters=data.get('filters') or {},
                page=data.get('page', 1), page_size=data.get('page_size', 50))
        except IPTVSelectionError as error:
            return jsonify(error={'code': error.code, 'message': str(error)}), 422
        if not resolved['source_keys']:
            raise AIProviderError('empty_selection')
        operation = jobs().store.create(feature, selection, {'selection_snapshot': resolved}, data.get('request_key'))
        jobs().start(operation['id'])
        return jsonify({**operation, 'job_id': operation['id']}), 202

    @app.post('/api/iptv/providers/<provider_id>/movies/ai/classification-jobs')
    @local_json(max_bytes=1048576)
    def ai_iptv_classification(data, provider_id):
        return create_iptv_operation(data, provider_id, 'F4')

    @app.post('/api/iptv/providers/<provider_id>/movies/ai/match-jobs')
    @local_json(max_bytes=1048576)
    def ai_iptv_match(data, provider_id):
        return create_iptv_operation(data, provider_id, 'F5')

    @app.post('/api/iptv/providers/<provider_id>/movies/ai/bulk-jobs')
    @local_json(max_bytes=5 * 1024 * 1024)
    def ai_iptv_bulk_start(data, provider_id):
        fields(data, ('selection_mode', 'selected_keys', 'filters', 'page', 'page_size', 'request_key',
                      'call_budget', 'titles_per_request', 'expected_source_count'))
        from services.ai_jobs import BULK_MAX_CALLS
        from services.chatgpt_skills import IPTV_BULK_PROTOCOL_HASH
        budget = data.get('call_budget')
        calculated = 'titles_per_request' in data or 'expected_source_count' in data
        size, expected = data.get('titles_per_request'), data.get('expected_source_count')
        if calculated:
            if ('call_budget' in data or type(size) is not int or not 1 <= size <= 100 or
                    type(expected) is not int or expected < 1):
                raise AIProviderError('invalid_bulk_launch')
        elif type(budget) is not int or not 1 <= budget <= BULK_MAX_CALLS:
            raise AIProviderError('invalid_bulk_budget')
        if (not isinstance(data.get('selected_keys', []), list) or
                not isinstance(data.get('filters', {}), dict)):
            raise AIProviderError('invalid_bulk_selection')
        if iptv_factory is None:
            raise AIProviderError('iptv_unavailable', 503)
        selection = provider.snapshot('F5', domain_id=provider_id)
        if selection.provider != 'chatgpt':
            raise AIProviderError('selected_provider_requires_ollama_route', 409)
        check_permission(selection)
        try:
            resolved = iptv_factory(provider_id).store.resolve_selection(bulk=True,
                mode=data.get('selection_mode', 'explicit'), selected_keys=data.get('selected_keys', []),
                filters=data.get('filters', {}), page=data.get('page', 1), page_size=data.get('page_size', 50))
        except IPTVSelectionError as error:
            return jsonify(error={'code': error.code, 'message': str(error)}), 422
        count = len(resolved['source_keys'])
        options = {}
        if calculated:
            if count != expected:
                return jsonify(error={'code': 'bulk_selection_count_changed', 'actual_count': count,
                    'message': f'The selection now contains {count:,} sources. Review the selection and confirm again.'}), 409
            initial = (count + size - 1) // size
            if initial > BULK_MAX_CALLS:
                minimum = (count + BULK_MAX_CALLS - 1) // BULK_MAX_CALLS
                return jsonify(error={'code': 'bulk_budget_too_large', 'minimum_titles_per_request': minimum,
                    'message': f'Choose at least {minimum} titles per request or narrow the selection.'}), 422
            options['titles_per_request'] = size
            options['estimated_first_pass_requests'] = initial
            repair_size = min(size, 50)
            repairs = (count + repair_size - 1) // repair_size
            budget = min(BULK_MAX_CALLS, 3 * (initial + 2 * repairs))
        if not count:
            raise AIProviderError('empty_selection')
        service = jobs()
        operation = service.store.create('F5', selection, {'selection_snapshot': resolved,
            'bulk_call_budget': budget, 'bulk_protocol_hash': IPTV_BULK_PROTOCOL_HASH,
            'bulk_auto_apply': True, **options}, data.get('request_key'))
        service.start(operation['id'])
        return jsonify({**present_job(operation), 'job_id': operation['id']}), 202

    @app.get('/api/iptv/providers/<provider_id>/movies/ai/bulk-jobs/latest')
    def ai_iptv_bulk_latest(provider_id):
        try:
            account = provider.connection_selection().account_id
            return jsonify(job=present_job(jobs().store.latest_bulk_job(account, provider_id, **job_page())))
        except AIProviderError as error:
            status = 401 if request.args.get('review_view') and error.code == 'account_disconnected' else error.status
            return jsonify(error={'code': error.code}), status
        except ValueError:
            return jsonify(error={'code': 'invalid_page'}), 400

    def bulk_apply_owner(provider_id, job_id):
        from services.ai_provider import AISelection
        operation = owned_job(job_id)
        if 'bulk_call_budget' not in operation['request'] or operation['selection']['domain_id'] != provider_id:
            raise AIProviderError('bulk_review_unavailable', 409)
        selection = AISelection(**operation['selection'])
        def authorize():
            if provider.connection_selection().account_id != selection.account_id:
                raise AIProviderError('job_account_mismatch', 403)
            check_permission(selection)
            if operation['request'].get('bulk_auto_apply') and provider.snapshot('F5', domain_id=provider_id) != selection:
                raise AIProviderError('bulk_configuration_changed', 409)
        authorize()
        generation = bulk_catalog_generation(operation)
        return iptv_factory(provider_id), generation, authorize

    def dispatch_bulk_apply(job_id, apply, owner, generation, authorize):
        from services.chatgpt_iptv import run_bulk_apply
        service = jobs()
        service.start_bulk_apply(job_id, apply['id'], lambda shutdown: run_bulk_apply(
            service.store, owner, job_id, apply, generation, authorize, shutdown))

    def bulk_apply_response(apply):
        return jsonify(apply_id=apply['id'], state=apply['state'], total=apply['total'], counts=apply['counts']), 202

    @app.post('/api/iptv/providers/<provider_id>/movies/ai/bulk-jobs/<job_id>/apply')
    @local_json
    def ai_iptv_bulk_apply(data, provider_id, job_id):
        if data.get('kind') not in ('classification', 'match'):
            raise AIProviderError('invalid_bulk_proposals')
        owner, generation, authorize = bulk_apply_owner(provider_id, job_id)
        service = jobs()
        store = service.store
        if 'scope' in data:
            fields(data, ('kind', 'scope', 'expected_revision', 'expected_count', 'request_key'))
            if data['kind'] != 'match':
                raise AIProviderError('invalid_bulk_apply')
            def validate():
                if not owner.store.bulk_selection_current(generation):
                    raise AIProviderError('iptv_selection_changed', 409)
            apply, claimed = store.claim_bulk_apply(job_id, data['scope'], data.get('expected_revision'),
                                                   data.get('expected_count'), data.get('request_key'), validate=validate)
            if claimed:
                dispatch_bulk_apply(job_id, apply, owner, generation, authorize)
            return bulk_apply_response(apply)
        fields(data, ('kind', 'proposal_ids'))
        if data['kind'] == 'match' and store.snapshot(job_id)['request'].get('bulk_auto_apply'):
            raise AIProviderError('bulk_apply_is_automatic', 409)
        try:
            with store.explicit_bulk_apply(job_id):
                proposals = store.bulk_proposals(job_id, data.get('proposal_ids'))
                def apply_explicit():
                    authorize()
                    return owner.apply_bulk_proposals(proposals, data['kind'], generation)
                report = service.serialize_bulk_apply(apply_explicit)
                store.mark_bulk_applied(job_id, report['applied'])
        except ValueError as error:
            return jsonify(error={'code': 'iptv_selection_changed', 'message': str(error)}), 409
        return jsonify(report)

    @app.post('/api/iptv/providers/<provider_id>/movies/ai/bulk-jobs/<job_id>/apply/<apply_id>/<action>')
    @local_json
    def ai_iptv_bulk_apply_control(data, provider_id, job_id, apply_id, action):
        if action not in ('resume', 'stop'):
            raise AIProviderError('invalid_bulk_apply_transition', 404)
        fields(data, ('expected_revision', 'request_key'))
        owner, generation, authorize = bulk_apply_owner(provider_id, job_id)
        apply, dispatch = jobs().store.control_bulk_apply(job_id, apply_id, action, data.get('expected_revision'),
                                                         data.get('request_key'))
        if dispatch:
            dispatch_bulk_apply(job_id, apply, owner, generation, authorize)
        return bulk_apply_response(apply)

    @app.post('/api/ai/control/turns')
    @local_json
    def ai_control_turn(data):
        fields(data, ('prompt', 'session_id', 'request_key'))
        if not isinstance(data.get('prompt'), str) or not data['prompt'].strip():
            raise AIProviderError('prompt_required')
        selection = provider.snapshot('F2')
        if selection.provider != 'chatgpt':
            raise AIProviderError('selected_provider_requires_ollama_route', 409)
        operation = jobs().store.create('F2', selection,
            {**{key: data[key] for key in ('prompt', 'session_id') if key in data},
             'recommendation_count': provider.public_config()['chatgpt']['recommendation_count']}, data.get('request_key'))
        jobs().start(operation['id'])
        return jsonify({**operation, 'job_id': operation['id']}), 202

    @app.post('/api/ai/control/plans/<plan_id>/confirm')
    @local_json
    def ai_control_confirm(data, plan_id):
        from services.ai_provider import AISelection
        from services.chatgpt_tools import ToolError
        fields(data, ('revision', 'selected_keys', 'confirmation_phrase', 'request_key'))
        if control_factory is None:
            raise AIProviderError('control_unavailable', 503)
        account = provider.connection_selection().account_id
        action = jobs().store.action(plan_id, account)
        check_permission(AISelection(**action['selection']))
        try:
            result = control_factory().confirm(plan_id, account, revision=data.get('revision'),
                selected_keys=data.get('selected_keys'), confirmation_phrase=data.get('confirmation_phrase', ''),
                request_key=data.get('request_key'))
        except ToolError as error:
            raise AIProviderError(error.code, 409) from None
        return jsonify(result)

    @app.post('/api/ai/control/plans/<plan_id>/review')
    @local_json
    def ai_control_review(data, plan_id):
        from services.chatgpt_tools import ToolError
        fields(data, ())
        if control_factory is None:
            raise AIProviderError('control_unavailable', 503)
        try:
            return jsonify(control_factory().review(plan_id, provider.connection_selection().account_id))
        except ToolError as error:
            raise AIProviderError(error.code, 409) from None

    @app.get('/api/ai/control/plans/<plan_id>')
    def ai_control_plan_status(plan_id):
        try:
            if control_factory is None:
                raise AIProviderError('control_unavailable', 503)
            return jsonify(control_factory().status(plan_id, provider.connection_selection().account_id))
        except Exception as error:
            return jsonify(error={'code': getattr(error, 'code', 'action_unavailable')}), getattr(error, 'status', 409)

    @app.post('/api/ai/control/plans/<plan_id>/cancel')
    @local_json
    def ai_control_plan_cancel(data, plan_id):
        fields(data, ('revision',))
        action = jobs().store.action(plan_id, provider.connection_selection().account_id)
        result = jobs().store.cancel_action(plan_id, data.get('revision'))
        if action['payload'].get('preparation_job_id'):
            child = jobs().store.snapshot(action['payload']['preparation_job_id'])
            if child['state'] not in ('completed', 'cancelled'):
                jobs().cancel(child['id'], child['revision'], run_number=child['cursor'].get('run_number', 0))
        return jsonify(result)

    @app.post('/api/ai/jobs/<job_id>/cancel')
    @local_json
    def ai_job_cancel(data, job_id):
        fields(data, ('revision', 'run_number'))
        owned_job(job_id)
        return jsonify(present_job(jobs().cancel(job_id, data.get('revision'), run_number=data.get('run_number'))))

    @app.post('/api/ai/jobs/<job_id>/pause')
    @local_json
    def ai_job_pause(data, job_id):
        fields(data, ('run_number',))
        owned_job(job_id)
        return jsonify(present_job(jobs().store.request_bulk_pause(job_id, data.get('run_number'))))

    @app.post('/api/ai/jobs/<job_id>/continue')
    @local_json
    def ai_job_continue(data, job_id):
        fields(data, ('revision', 'request_key', 'extra_calls', 'recheck_search_limits'))
        recheck = data.get('recheck_search_limits', False)
        if type(recheck) is not bool or (recheck and 'extra_calls' in data):
            raise AIProviderError('invalid_search_recheck')
        previous = owned_job(job_id)
        refresh_catalog = None
        if 'bulk_call_budget' in previous['request']:
            from services.ai_provider import AISelection
            selection = AISelection(**previous['selection'])
            check_permission(selection)
            if (previous['request'].get('bulk_auto_apply') and
                    provider.snapshot('F5', domain_id=selection.domain_id) != selection):
                raise AIProviderError('bulk_configuration_changed', 409)
            if supports_bulk_catalog_resume(previous['request']) and iptv_factory is not None:
                refresh_catalog = iptv_factory(selection.domain_id).bulk_catalog_continuation
        elif 'extra_calls' in data or 'recheck_search_limits' in data:
            raise AIProviderError('unknown_field')
        try:
            operation = jobs().store.continue_job(job_id, data.get('revision'), data.get('request_key'),
                extra_calls=data.get('extra_calls'), refresh_catalog=refresh_catalog, recheck_search_limits=recheck)
        except IPTVSelectionError as error:
            return jsonify(error={'code': error.code, 'message': str(error)}), 409
        jobs().start(job_id)
        return jsonify(present_job(operation)), 202

    @app.get('/api/ai/sessions/<session_id>')
    def ai_session_status(session_id):
        try:
            return jsonify(jobs().store.session(session_id, provider.connection_selection().account_id))
        except Exception:
            return jsonify(error={'code': 'session_unavailable'}), 404
