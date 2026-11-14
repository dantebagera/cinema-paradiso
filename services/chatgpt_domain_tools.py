"""Typed composition over CP's existing catalogue, plan and domain HTTP owners.

The injected dispatcher is in-process: endpoint names below are authored here,
never supplied by the model. No general HTTP, filesystem or SQL tool is exposed.
"""
from dataclasses import replace
import hashlib
import json

from services import ai_control
from services.ai_catalog import AICatalogError
from services.ai_catalog import ResultSet
from services.ai_jobs import AIJobError
from services.ai_provider import canonical_count
from services.advanced_search import normalize_query
from services.chatgpt_tools import ChatGPTTools, ToolError, ToolResult, model_safe


class DomainTools:
    def __init__(self, store, catalogue, plans, dispatch, *, validate_identities=lambda query, context: None,
                 owned_movies=lambda movies: [None for movie in movies], library_roots=lambda: [],
                 download_ready=lambda: False, execute_movie=None, availability=lambda definition, context: None,
                 read_extra=None, prepare_extra=None, recommender=None, default_count=lambda: '15',
                 media_resolver=None, feature_selection=None, run_feature=None, iptv_factory=None,
                 metadata_preview=None, metadata_snapshot=None, catalogue_generation=lambda: None,
                 schedule_feature=None):
        self.store, self.catalogue, self.plans, self.dispatch = store, catalogue, plans, dispatch
        self.validate_identities, self.owned_movies = validate_identities, owned_movies
        self.library_roots, self.download_ready, self.execute_movie = library_roots, download_ready, execute_movie
        self.recommender, self.default_count = recommender, default_count
        self.media_resolver, self.feature_selection = media_resolver, feature_selection
        self.run_feature, self.iptv_factory = run_feature, iptv_factory
        self.metadata_preview, self.metadata_snapshot = metadata_preview, metadata_snapshot
        self.catalogue_generation = catalogue_generation
        self.schedule_feature = schedule_feature
        owners = {name: getattr(self, name) for name in (
            'search_movies', 'resolve_people', 'resolve_companies', 'movie_details', 'collection_details',
            'list_movie_lists', 'prepare_movie_list', 'prepare_movie_state', 'prepare_movie_download',
            'prepare_movie_delete', 'search_tv', 'tv_coverage', 'tv_lists', 'prepare_tv_list', 'prepare_tv_state',
            'prepare_tv_task', 'tv_task_status', 'prepare_tv_task_cancel', 'prepare_tv_delete',
            'search_iptv', 'iptv_details', 'iptv_lists', 'prepare_iptv_list', 'prepare_iptv_favorite',
            'iptv_facets',
            'continue_watching', 'playback_status', 'notifications', 'prepare_mark_notifications_read', 'open_review')}
        owners['prepare_collection_override'] = self.prepare_collection_override
        owners.update(read_extra or {})
        owners.update(prepare_extra or {})
        if recommender is not None:
            owners['suggest_movies'] = self.suggest_movies
        if media_resolver is not None:
            owners.update(prepare_play=self.prepare_play, prepare_clear_progress=self.prepare_clear_progress)
        if iptv_factory is not None and run_feature is not None and feature_selection is not None:
            owners.update(prepare_iptv_match=self.prepare_iptv_match, prepare_iptv_classification=self.prepare_iptv_classification)
        if metadata_preview is not None and metadata_snapshot is not None:
            owners.update(prepare_movie_match=self.prepare_movie_match, prepare_metadata_apply=self.prepare_metadata_apply,
                          prepare_rename=self.prepare_rename)
        self.registry = ChatGPTTools(owners, availability=availability)

    def _read(self, endpoint, *, values=None, query=None, body=None, method='GET'):
        return self.dispatch(endpoint, method=method, values=values or {}, query=query or {}, body=body)

    def _view(self, kind, payload):
        return ToolResult(model_safe(payload), {'kind': kind, 'data': payload})

    def resolve_people(self, args, context):
        result = self.catalogue.resolve_people(args['text'], args['role'], page=args['page'])
        context.identities['person'].extend(result['candidates'])
        return result

    def resolve_companies(self, args, context):
        result = self.catalogue.resolve_company(args['text'], page=args['page'])
        context.identities['company'].extend(result['candidates'])
        return result

    def search_movies(self, args, context):
        query = normalize_query(args['query'], 'discover')
        self.validate_identities(query, {**context.private.get('scope_context', {}), **context.identities})
        key = 'catalogue_' + hashlib.sha256(json.dumps(args, sort_keys=True).encode()).hexdigest()
        saved = self.store.snapshot(context.job_id)['cursor'].get(key)
        generation = self.catalogue_generation()
        if saved and saved.get('_local_generation') != generation:
            saved = None
        result = self.catalogue.collect(query, requested_count=args['count'], cancel=context.private['cancel'], scope=args['scope'],
            resume=saved, checkpoint=lambda progress: self.store.save_checkpoint(context.job_id, key,
                dict(progress, _local_generation=generation)))
        result = replace(result, download_ready=bool(self.download_ready()))
        self.store.save_result_set(context.job_id, result)
        context.result_sets[result.id] = result
        self.store.add_results(context.job_id, [{'domain': 'movie', 'identity': str(row.get('tmdb_id') or row.get('id')),
            'card': dict(row)} for row in result.movies])
        return ToolResult({'result_set': result.id, 'domain': 'movie', 'count': len(result.movies),
            'coverage': result.coverage, 'reason': result.reason, 'excluded': result.excluded_count,
            'unresolved': result.unresolved_count, 'fetched_pages': result.fetched_pages,
            'provider_total_results': result.provider_total_results, 'first_page': [dict(row) for row in result.movies[:20]]},
            {'kind': 'movie-results', 'result_set': result.id, 'count': len(result.movies),
             'coverage': result.coverage, 'reason': result.reason, 'plan': ai_control.prepare_resolved('find',
                result_set=result, plan_store=None, provenance=context.selection.public())})

    def movie_details(self, args, context):
        return {'items': [model_safe(self.catalogue.details(str(identity))) for identity in args['ids']]}

    def suggest_movies(self, args, context):
        from services.chatgpt_skills import load
        skill = load('F1')
        selection = (self.feature_selection(context.selection, 'F1') if self.feature_selection else
            replace(context.selection, feature='F1', skill_id=skill['id'], skill_version=skill['version'], skill_hash=skill['hash']))
        count = canonical_count(args['count'] or self.store.snapshot(context.job_id)['request'].get('recommendation_count') or self.default_count())
        key = hashlib.sha256(json.dumps([context.job_id, args], sort_keys=True).encode()).hexdigest()
        job = self._nested_job(selection, {'prompt': args['prompt'], 'count': count,
            'count_source': 'explicit' if args['count'] else 'settings'}, key, context, self.recommender.run)
        rows, page = [], 1
        while True:
            payload = self.store.snapshot(job['id'], page=page, page_size=100)
            rows.extend({key: value for key, value in row.items() if not key.startswith('result_')} for row in payload['results'])
            if not payload['has_more']:
                break
            page += 1
        result = ResultSet('suggest-' + job['id'] + '-' + str(job['revision']), key, tuple(rows), 'complete' if job['state'] == 'completed' else 'partial',
            None if job['state'] == 'completed' else job['message'], 0, 0, len(rows), 0, 0, count,
            download_ready=bool(self.download_ready()))
        self.store.save_result_set(context.job_id, result)
        context.result_sets[result.id] = result
        self.store.add_results(context.job_id, [{'domain': 'movie', 'identity': str(row['tmdb_id']), 'card': row} for row in rows])
        return ToolResult({'result_set': result.id, 'subjective': True, 'count': len(rows), 'coverage': result.coverage,
            'reason': result.reason, 'first_page': rows[:20]}, {'kind': 'movie-results', 'result_set': result.id,
            'subjective': True, 'count': len(rows), 'coverage': result.coverage, 'reason': result.reason,
            'plan': ai_control.prepare_resolved('find', result_set=result, plan_store=None, provenance=context.selection.public())})

    def _nested_job(self, selection, request, key, context, handler):
        job = self.store.create(selection.feature, selection, {**request, 'session_id': context.session_id,
                               'parent_job_id': context.job_id}, key)
        parent = self.store.snapshot(context.job_id)
        nested = parent['cursor'].get('nested', {})
        prior = nested.get(key)
        run = parent['cursor'].get('run_number', 0)
        if prior and prior['run'] != run and job['state'] in ('paused_budget', 'partial', 'interrupted'):
            job = self.store.continue_job(job['id'], job['revision'], 'parent-' + context.job_id + '-' + str(run))
        nested[key] = {'job_id': job['id'], 'run': run}
        self.store.save_checkpoint(context.job_id, 'nested', nested)
        if job['state'] == 'queued':
            job = handler(job['id'])
        parent = self.store.snapshot(context.job_id)
        if parent['state'] == 'paused_budget':
            raise AIJobError('paused_budget')
        if parent['state'] != 'running':
            raise AIJobError('job_not_running')
        if job['state'] in ('failed', 'cancelled', 'running'):
            raise ToolError(job['message'] or 'nested_preview_not_ready')
        return job

    def _prepare_iptv_review(self, args, context, feature):
        selection = self.feature_selection(context.selection, feature, domain_id=args['provider_id'])
        owner = self.iptv_factory(args['provider_id'])
        selected = args['selection']
        filters = {key: value for key, value in selected['filters'].items() if value is not None}
        snapshot = owner.store.resolve_selection(mode=selected['mode'], selected_keys=selected['keys'], filters=filters)
        if feature == 'F5' and any(self.store.action(identity, context.selection.account_id)['state'] != 'completed'
                                   for identity in args.get('depends_on', [])):
            return self._prepare(args, context, domain='iptv', items=[{
                'source_key': identity, 'iptv_provider_id': args['provider_id'],
                'title': owner.store.source(identity).get('provider_title', identity)} for identity in snapshot['source_keys']],
                summary='Prepare IPTV matching after the preceding confirmed changes',
                operation={'kind': 'iptv_deferred', 'feature': feature, 'provider_id': args['provider_id'],
                           'selection': selection.public(), 'catalog_generation': snapshot['catalog_generation']})
        key = hashlib.sha256(json.dumps([context.job_id, feature, args], sort_keys=True).encode()).hexdigest()
        job = self._nested_job(selection, {'selection_snapshot': snapshot}, key, context,
                               lambda identity: self.run_feature(feature, identity))
        if job['state'] != 'completed':
            raise ToolError('iptv_review_incomplete; explicitly continue before applying')
        review = job['output']['review']
        proposals = review['proposals']
        return self._prepare(args, context, domain='iptv', items=[dict(row, title=row.get('provider_title') or '',
            iptv_provider_id=args['provider_id']) for row in proposals],
            summary='Review IPTV classification' if feature == 'F4' else 'Review IPTV matches',
            operation={'kind': 'iptv_apply', 'feature': feature, 'provider_id': args['provider_id'],
                       'review': review, 'selection': selection.public()})

    def prepare_iptv_classification(self, args, context):
        return self._prepare_iptv_review(args, context, 'F4')

    def prepare_iptv_match(self, args, context):
        return self._prepare_iptv_review(args, context, 'F5')

    def prepare_iptv_job_review(self, job, selection, review):
        from services.chatgpt_tools import ToolContext
        context = ToolContext(selection, job['id'], job['session_id'])
        result = self._prepare({'depends_on': []}, context, domain='iptv',
            items=[dict(row, title=row.get('provider_title') or '', iptv_provider_id=selection.domain_id) for row in review['proposals']],
            summary='Review IPTV classification' if selection.feature == 'F4' else 'Review IPTV matches',
            operation={'kind': 'iptv_apply', 'feature': selection.feature, 'provider_id': selection.domain_id,
                       'review': review, 'selection': selection.public()})
        return result.ui

    def prepare_movie_match(self, args, context):
        key = hashlib.sha256(json.dumps([context.job_id, args], sort_keys=True).encode()).hexdigest()
        started = self.metadata_preview(args, context, key)
        if started.get('ai_job_id'):
            selection = self.feature_selection(context.selection, 'F3')
            child = self.store.snapshot(started['ai_job_id'])
            self._nested_job(selection, {key: value for key, value in child['request'].items()
                if key not in ('parent_job_id', 'session_id')}, key, context,
                lambda identity: self.run_feature('F3', identity))
        result = self.metadata_snapshot(started['id'])
        return ToolResult({'native_job_id': result['id'], 'status': result['status'],
            'proposals': [{key: row.get(key) for key in ('id', 'candidate', 'confidence', 'recommendation', 'preselected')}
                          for row in result.get('proposals', [])], 'applied': False}, {'kind': 'movie-match', 'data': result})

    def prepare_metadata_apply(self, args, context):
        state = self.metadata_snapshot(args['job_id'])
        selected = set(args['proposal_ids'])
        rows = [row for row in state.get('proposals', []) if row['id'] in selected]
        if {row['id'] for row in rows} != selected:
            raise ToolError('metadata_proposal_not_in_reviewed_job')
        return self._prepare(args, context, domain='movie', items=[dict(row, title=row.get('candidate', {}).get('title') or '') for row in rows],
            summary='Apply reviewed Movie identity matches', operation={'kind': 'metadata_apply', 'job_id': state['id']})

    def prepare_rename(self, args, context):
        state = self.metadata_snapshot(None)
        selected = set(args['proposal_ids'])
        rows = [row for row in state.get('proposals', []) if row['id'] in selected]
        if {row['id'] for row in rows} != selected or not rows:
            raise ToolError('rename_proposal_not_in_current_review')
        preview = self._read('smart_rename_preview', method='POST', body={'items': [{
            'path': row['path'], 'title': row.get('candidate', {}).get('title'),
            'year': row.get('candidate', {}).get('year'), 'release': row.get('parsed')} for row in rows]})
        return self._prepare(args, context, domain='movie', items=[dict(row, title=row.get('new_filename') or '') for row in preview['items']],
            summary='Rename reviewed Movie files', operation={'kind': 'metadata_rename', 'preview': preview})

    def collection_details(self, args, context):
        result = self._read('library_collection', values={'collection_id': str(args['id'])})
        context.private.setdefault('collections', {})[str(args['id'])] = result
        return self._view('movie-collection', result)

    def prepare_collection_override(self, args, context):
        original = context.private.get('collections', {}).get(str(args['collection_id']))
        if not original:
            original = self._read('library_collection', values={'collection_id': str(args['collection_id'])})
        known = {str(row.get('movie_key') or 'tmdb:' + str(row.get('tmdb_id') or row.get('id'))): dict(row)
                 for row in original.get('parts', [])}
        for result in context.result_sets.values():
            if result.domain == 'movie':
                known.update({str(row.get('movie_key') or 'tmdb:' + str(row.get('tmdb_id') or row.get('id'))): dict(row)
                              for row in result.movies})
        if any(row['key'] not in known for row in args['parts']):
            raise ToolError('resolve_collection_parts_before_preparing')
        return self._prepare(args, context, domain='movie', items=[known[row['key']] for row in args['parts']],
            summary='Save collection membership override', operation={'kind': 'collection_override',
                'collection_id': str(args['collection_id']), 'original': original})

    def list_movie_lists(self, args, context):
        payload = self._read('user_lists')
        rows = payload.get('lists', [])
        start = (args['page'] - 1) * 20
        return {'items': [{'id': row['id'], 'name': row.get('name'), 'count': len(row.get('movies', []))}
                          for row in rows[start:start+20]], 'total': len(rows), 'page': args['page']}

    def _result(self, args, context):
        result = context.result_sets.get(args.get('result_set'))
        if result is None or result.domain != 'movie':
            raise ToolError('movie_result_set_required')
        if result.coverage != 'complete':
            raise ToolError('partial_scope_requires_explicit_revision')
        return result

    def _register_plan(self, plan, args, context, kind):
        if plan.get('state') != 'valid_plan':
            raise ToolError(plan.get('message') or 'plan_unavailable')
        key = hashlib.sha256(json.dumps([kind, args], sort_keys=True).encode()).hexdigest()
        action = self.store.prepare_action(context.job_id, kind, {'owner_plan_id': plan['plan_id']},
            request_key=key, depends_on=args.get('depends_on', []))
        # Repeated preparation returns its original one-shot owner plan.
        plan = self.plans.get(action['payload']['owner_plan_id'])
        if plan is None:
            raise ToolError('review_plan_expired')
        public = {'action_id': action['action_id'], 'revision': action['revision'], 'state': action['state'],
                  'summary': plan['summary'], 'count': plan['total_matches'], 'depends_on': action['depends_on']}
        return ToolResult(public, {'kind': 'action-plan', 'action': public, 'plan': plan})

    def _prepare(self, args, context, *, domain, items, summary, operation):
        if args.get('result_set'):
            operation = dict(operation, result_set=args['result_set'])
        plan = ai_control.prepare_domain_operation(items=items, summary=summary, operation=operation,
            plan_store=self.plans, provenance=context.selection.public(), domain=domain)
        return self._register_plan(plan, args, context, operation['kind'])

    def prepare_movie_list(self, args, context):
        action = args['action']
        result = self._result(args, context) if action in ('create', 'add', 'remove') else None
        if action == 'create':
            plan = ai_control.prepare_resolved('create_list', result_set=result, list_name=args['name'],
                plan_store=self.plans, provenance=context.selection.public())
            return self._register_plan(plan, args, context, 'movie_list_create')
        lists = self._read('user_lists')['lists']
        current = next((row for row in lists if row['id'] == args['list_id']), None)
        if not current:
            raise ToolError('movie_list_not_found')
        items = [dict(row) for row in result.movies] if result else [{'id': current['id'], 'title': current['name']}]
        return self._prepare(args, context, domain='movie', items=items, summary=f"{action.title()} Movie list: {current['name']}",
            operation={'kind': 'movie_list', 'action': action, 'list_id': args['list_id'], 'name': args['name']})

    def prepare_movie_state(self, args, context):
        result = self._result(args, context)
        if args['kind'] == 'watched' and args['active'] and any(not row for row in self.owned_movies(result.movies)):
            raise ToolError('watched_requires_owned_movies')
        return self._prepare(args, context, domain='movie', items=[dict(row) for row in result.movies],
            summary=f"Set {args['kind']}: {args['active']}", operation={'kind': 'movie_state',
                'state_kind': args['kind'], 'active': args['active']})

    def prepare_movie_download(self, args, context):
        if args['quality'].casefold() != '1080p' or args['profile_id'] is not None:
            raise ToolError('unsupported_download_policy; use the Downloads review to choose another policy')
        result = self._result(args, context)
        plan = ai_control.prepare_resolved('download', result_set=result, plan_store=self.plans,
                                          provenance=context.selection.public())
        return self._register_plan(plan, args, context, 'movie_download')

    def prepare_movie_delete(self, args, context):
        if args['whole_movie_folders']:
            raise ToolError('whole_folder_delete_requires_cleanup_review')
        result = self._result(args, context)
        owned = self.owned_movies(result.movies)
        if any(not row for row in owned):
            raise ToolError('delete_requires_owned_files')
        result = replace(result, local_files=tuple(owned), library_roots=tuple(self.library_roots()))
        plan = ai_control.prepare_resolved('delete', result_set=result, plan_store=self.plans,
                                          provenance=context.selection.public())
        return self._register_plan(plan, args, context, 'movie_delete')

    def search_tv(self, args, context):
        query = args['query']
        return self._view('tv-results', self._read('tv_catalog_search', method='POST', body={
            'scope': query['scope'], 'query': query, 'page': args['page'], 'page_size': 20}))

    def tv_coverage(self, args, context):
        series_id = args['series']['series_id']
        detail = self._read('tv_series_detail', values={'series_id': series_id})
        episodes = self._read('tv_selection', values={'series_id': series_id},
            query={'season': args['season']} if args['season'] is not None else {})
        return self._view('tv-coverage', {'series': detail, 'episodes': episodes['items'],
            'scope': args['scope'], 'season': args['season']})

    def tv_lists(self, args, context):
        return self._view('tv-lists', self._read('tv_lists', query={'page': args['page'], 'page_size': 20}))

    def _tv_items(self, references):
        return [dict(self._read('tv_series_detail', values={'series_id': ref['series_id']}),
                     series_id=ref['series_id'], domain='tv') for ref in references]

    def prepare_tv_list(self, args, context):
        items = self._tv_items(args['series']) if args['action'] in ('add', 'remove', 'create') and args['series'] else [
            {'id': args['list_id'] or 'new-list', 'title': args['name'] or args['list_id'] or 'TV list', 'domain': 'tv'}]
        return self._prepare(args, context, domain='tv', items=items, summary=f"{args['action'].title()} TV list",
            operation={'kind': 'tv_list', **{key: args[key] for key in ('action', 'list_id', 'name')}})

    def prepare_tv_state(self, args, context):
        return self._prepare(args, context, domain='tv', items=self._tv_items([args['series']]),
            summary=f"Set TV {args['kind']}: {args['active']}",
            operation={'kind': 'tv_state', 'state_kind': args['kind'], 'active': args['active']})

    def prepare_tv_task(self, args, context):
        identity = args['series']['series_id']
        if args['action'] == 'finish_season':
            tasks, page = [], 1
            while True:
                payload = self._read('tv_tasks', query={'series_id': identity, 'page': page})
                tasks.extend(row for row in payload['items'] if row.get('state') == 'waiting_season_end'
                    and row.get('scope') == 'season' and row.get('season') == args['season'])
                if page >= payload['total_pages']:
                    break
                page += 1
            if len(tasks) != 1:
                raise ToolError('choose_one_waiting_season_task_in_tv_review')
            return self._prepare(args, context, domain='tv', items=self._tv_items([args['series']]),
                summary='Finish TV season follow', operation={'kind': 'tv_finish_season', 'task_id': tasks[0]['id']})
        scope = 'series' if args['scope'] == 'missing' else args['scope']
        selected = list(dict.fromkeys(args['episode_ids'] or ([args['series']['episode_id']] if args['series']['episode_id'] else [])))
        if scope == 'episode' or selected:
            scope = 'episodes'
            available = self._read('tv_selection', values={'series_id': identity})['items']
            valid = {row['id'] for row in available if not row.get('preview')}
            if not selected or set(selected) - valid:
                raise ToolError('selected_episode_identity_does_not_belong_to_series')
        body = {'scope': scope, 'action': 'future' if args['action'] == 'monitor' else 'missing',
            'season': args['season'], 'selected_episodes': selected, 'profile_id': args['profile_id'] or 'safe-hd'}
        preview = self._read('tv_task_preview', method='POST', values={'series_id': identity}, body=body)
        if not preview.get('metadata_complete') or preview.get('counts', {}).get('review'):
            raise ToolError('tv_metadata_or_file_review_required')
        return self._prepare(args, context, domain='tv', items=self._tv_items([args['series']]), summary='Review TV task',
            operation={'kind': 'tv_task', 'series_id': identity, 'body': body, 'requested_action': args['action'], 'preview': preview})

    def tv_task_status(self, args, context):
        return self._view('tv-task', self._read('tv_task_detail', values={'task_id': args['id']}))

    def prepare_tv_task_cancel(self, args, context):
        preview = self._read('tv_task_cancel_preview', values={'task_id': args['task_id']})
        return self._prepare(args, context, domain='tv', items=[{'id': args['task_id'], 'title': 'TV task'}],
            summary='Cancel TV task', operation={'kind': 'tv_task_cancel', 'task_id': args['task_id'], 'mode': args['mode'], 'preview': preview})

    def prepare_tv_delete(self, args, context):
        ids = sorted(set(row['series_id'] for row in args['series']))
        preview = self._read('tv_bulk_delete_preview', method='POST', body={'series_ids': ids})
        return self._prepare(args, context, domain='tv', items=self._tv_items(args['series']), summary='Delete selected TV shows',
            operation={'kind': 'tv_delete', 'series_ids': ids, 'preview': preview})

    def search_iptv(self, args, context):
        filters = {key: value for key, value in args['filters'].items() if value is not None}
        metadata_filters = {'category', 'metadata_status', 'year_from', 'year_to', 'genre_id', 'language', 'country', 'min_rating'}
        if args['kind'] == 'movie':
            if any(filters.get(key) for key in metadata_filters) and filters['view'] != 'cp':
                raise ToolError('metadata_filters_require_cp_view')
            query = {'page': args['page'], 'page_size': 20, **filters}
            payload = self._read('iptv_movies', values={'provider_id': args['provider_id']}, query=query)
        else:
            if any(value not in (None, '', 'provider', False) for key, value in filters.items() if key not in ('q', 'playlist_id', 'view')):
                raise ToolError('unsupported_live_or_series_filter')
            payload = self._read('iptv_items', values={'provider_id': args['provider_id']}, query={
                'kind': args['kind'], 'q': filters.get('q', ''), 'category_id': filters.get('playlist_id', ''),
                'page': args['page'], 'page_size': 20})
        for row in payload.get('items', []):
            identity = row.get('movie_key') if args['kind'] == 'movie' else row.get('item_id') or row.get('id')
            row['media_ref'] = {'domain': 'iptv', 'provider_id': args['provider_id'], 'kind': args['kind'], 'item_id': str(identity)}
        return self._view('iptv-results', payload)

    def iptv_details(self, args, context):
        ref = args['media']
        return self._view('iptv-detail', self._iptv_detail(ref))

    def _iptv_detail(self, ref):
        if ref['kind'] == 'movie':
            return self._read('iptv_movie_detail', values={'provider_id': ref['provider_id'], 'movie_key': ref['item_id']})
        return self._read('iptv_item_detail', values={key: ref[key] for key in ('provider_id', 'kind', 'item_id')})

    def iptv_lists(self, args, context):
        return self._view('iptv-lists', self._read('iptv_lists', values={'provider_id': args['provider_id']}))

    def iptv_facets(self, args, context):
        return self._read('iptv_movie_facets', values={'provider_id': args['provider_id']})

    def _iptv_items(self, references):
        rows = []
        for ref in references:
            detail = self._iptv_detail(ref)
            rows.append({**detail, 'domain': 'iptv', 'iptv_ref': ref})
        return rows

    def prepare_iptv_list(self, args, context):
        items = self._iptv_items(args['items']) if args['items'] else [{'title': args['name'] or args['list_id'] or 'IPTV list'}]
        return self._prepare(args, context, domain='iptv', items=items, summary=f"{args['action'].title()} IPTV list",
            operation={'kind': 'iptv_list', **{key: args[key] for key in ('provider_id', 'action', 'list_id', 'name')}})

    def prepare_iptv_favorite(self, args, context):
        return self._prepare(args, context, domain='iptv', items=self._iptv_items([args['media']]), summary='Change IPTV favorite',
            operation={'kind': 'iptv_favorite', 'active': args['active']})

    def continue_watching(self, args, context):
        if args['domain'] == 'iptv':
            raise ToolError('select_provider_in_iptv_review')
        return self._view(args['domain'] + '-continue-watching', self._read(
            'tv_continue' if args['domain'] == 'tv' else 'get_continue_watching'))

    def playback_status(self, args, context):
        return self._view('playback-status', self._read('get_player_status'))

    def notifications(self, args, context):
        return self._view('notifications', self._read('notification_history', query={'page': args['page']}))

    def prepare_mark_notifications_read(self, args, context):
        return self._prepare(args, context, domain='tv', items=[{'id': identity, 'title': 'Notification ' + identity} for identity in args['ids']],
            summary='Mark notifications read', operation={'kind': 'notifications_read'})

    def open_review(self, args, context):
        return self._view('open-review', {'surface': args['surface'], 'target_ref': args['target_ref'], 'applied': False})

    def _prepare_media(self, args, context, action):
        resolved = self.media_resolver(args['media'], action, args.get('restart', False))
        return self._prepare(args, context, domain=args['media']['domain'], items=[resolved['item']],
            summary='Play selected media' if action == 'play' else 'Clear selected playback progress',
            operation={'kind': 'media', 'owner': resolved['owner'], 'reference': args['media'],
                       'action': action, 'restart': args.get('restart', False),
                       'review_fingerprint': self._media_fingerprint(resolved)})

    @staticmethod
    def _media_fingerprint(resolved):
        return hashlib.sha256(json.dumps(resolved, sort_keys=True, default=str).encode()).hexdigest()

    def prepare_play(self, args, context):
        return self._prepare_media(args, context, 'play')

    def prepare_clear_progress(self, args, context):
        return self._prepare_media(args, context, 'clear_progress')

    def confirm(self, action_id, account_id, *, revision, selected_keys, confirmation_phrase, request_key):
        if not isinstance(request_key, str) or not 1 <= len(request_key) <= 160:
            raise ToolError('invalid_request_key')
        if not isinstance(selected_keys, list) or not all(isinstance(key, str) for key in selected_keys):
            raise ToolError('explicit_selection_required')
        action = self.store.action(action_id, account_id)
        confirmation = {'request_key': request_key, 'selected_keys': sorted(set(selected_keys)),
                        'confirmation_phrase': confirmation_phrase}
        if action['state'] != 'completed':
            stored_plan = self.plans.get(action['payload']['owner_plan_id'])
            if stored_plan and stored_plan.get('operation', {}).get('kind') == 'iptv_deferred':
                raise ToolError('prepare_next_step_first; use Prepare next step after confirming the preceding action')
            reviewed = self.review(action_id, account_id)
            if reviewed['action']['revision'] != revision:
                raise ToolError('review_changed; review the updated targets before confirming')
            selected, error = self.plans.validate(action['payload']['owner_plan_id'],
                selected_keys=selected_keys, confirmation_phrase=confirmation_phrase)
            if error:
                raise ToolError(error)
            operation = selected.get('operation', {})
            if operation.get('kind') == 'iptv_deferred':
                raise ToolError('prepare_next_step_first; use Prepare next step after confirming the preceding action')
            if operation.get('kind') == 'tv_delete':
                identities = sorted(set(row['series_id'] for row in selected['items']))
                if identities != operation['series_ids']:
                    preview = self._read('tv_bulk_delete_preview', method='POST', body={'series_ids': identities})
                    selected['operation'] = {**operation, 'series_ids': identities, 'preview': preview}
                    selected['warnings'] = [*selected.get('warnings', []),
                        'Deletion scope changed. Refresh this review and confirm the selected TV shows again.']
                    refreshed = self.plans.put(selected)
                    self.store.refresh_action(action_id, action['revision'], {'owner_plan_id': refreshed['plan_id']})
                    raise ToolError('review_changed; refresh review and confirm the selected TV shows again')
        claim = self.store.claim_action(action_id, revision, confirmation=confirmation)
        if claim.get('already_completed'):
            return claim
        try:
            if self.execute_movie is None:
                raise ToolError('execution_owner_unavailable')
            outcome = self.execute_movie(claim['payload']['owner_plan_id'], selected_keys=selected_keys,
                confirmation_phrase=confirmation_phrase, execute_prepared=self._execute_domain)
            state = 'completed' if outcome.get('state') == 'executed' else 'partial' if outcome.get('state') == 'partial' else 'failed'
            outcome['confirmed_media'] = [self._media_identity(row) for row in selected['items']] if state == 'completed' else []
            transient = None
            operation = selected.get('operation', {})
            if operation.get('kind') == 'media' and operation['owner']['endpoint'] == 'iptv_playback_start' and state == 'completed':
                transient = {'kind': 'iptv-playback', 'data': outcome['effects'][-1], 'media': {
                    **selected['items'][0]['iptv_ref'], 'kind': operation['owner']['body']['kind'],
                    'item_id': operation['owner']['body']['item_id'], 'title': operation['owner']['body'].get('title', '')}}
                outcome['effects'] = [{'playback_ready': True, 'media': selected['items'][0]['iptv_ref']}]
            receipt = self.store.complete_action(action_id, claim['revision'], outcome, state=state)
            self.store.finalize_actions(claim['job_id'])
            self.store.append_turn(claim['session_id'], account_id, {'role': 'assistant', 'content':
                'CP action receipt: ' + json.dumps(model_safe({'action_id': action_id, 'state': state, 'outcome': outcome}), ensure_ascii=False)})
            return dict(receipt, transient_ui=transient) if transient else receipt
        except Exception:
            # The owner may already have persisted/submitted. Preserve uncertainty; never replay.
            self.store.complete_action(action_id, claim['revision'], {'code': 'owner_outcome_uncertain'}, state='uncertain')
            raise

    def review(self, action_id, account_id):
        action = self.store.action(action_id, account_id)
        if action['state'] != 'prepared':
            return {'action': action, 'plan': None}
        plan = self.plans.get(action['payload']['owner_plan_id'])
        if plan is None:
            raise ToolError('review_plan_expired; prepare this action again')
        items = plan['items']
        for identity in action['depends_on']:
            receipt = self.store.action(identity, account_id)
            if receipt['state'] != 'completed':
                raise ToolError('action_dependency_not_completed')
            confirmed = receipt['outcome'].get('confirmed_media')
            if confirmed:
                members = {json.dumps(row, sort_keys=True) for row in confirmed}
                items = [row for row in items if json.dumps(self._media_identity(row), sort_keys=True) in members]
        if not items:
            raise ToolError('dependency_has_no_matching_confirmed_targets')
        if plan.get('operation', {}).get('kind') == 'iptv_deferred':
            return self._review_deferred_iptv(action, plan, items, account_id)
        if len(items) != len(plan['items']):
            selected, error = self.plans.validate(plan['plan_id'], selected_keys=[row['selection_key'] for row in items])
            if error:
                raise ToolError(error)
            selected['warnings'] = [*selected.get('warnings', []), 'Targets now follow the actual confirmed subset from the preceding action.']
            plan = self.plans.put(selected)
            action = self.store.refresh_action(action_id, action['revision'], {'owner_plan_id': plan['plan_id']})
        return {'action': action, 'plan': plan}

    def status(self, action_id, account_id):
        action = self.store.action(action_id, account_id)
        result = {'action': action, 'plan': self.plans.get(action['payload']['owner_plan_id']) if action['state'] == 'prepared' else None}
        if action['payload'].get('preparation_job_id'):
            result['preparation_job'] = self.store.snapshot(action['payload']['preparation_job_id'])
        return result

    def _review_deferred_iptv(self, action, plan, items, account_id):
        from services.ai_provider import AISelection
        operation = plan['operation']
        if self.store.snapshot(action['job_id'])['state'] in ('cancelled', 'interrupted'):
            raise ToolError('action_cancelled')
        selection = self.feature_selection(AISelection(**operation['selection']), operation['feature'],
                                           domain_id=operation['provider_id'])
        owner = self.iptv_factory(operation['provider_id'])
        if owner.store.source_generation() != operation['catalog_generation']:
            raise ToolError('iptv_selection_changed; start a new request')
        identity = action['payload'].get('preparation_job_id')
        if not identity:
            if self.schedule_feature is None:
                raise ToolError('preparation_owner_unavailable')
            snapshot = owner.store.resolve_selection(mode='explicit',
                selected_keys=['source:' + row['source_key'] for row in items], filters={})
            # This is an explicit next run after a confirmed mutation, with its own
            # 24-call budget. It sends only this feature's selected IPTV evidence.
            job = self.store.create(operation['feature'], selection, {'selection_snapshot': snapshot,
                'origin_control_job_id': action['job_id'], 'deferred_action_id': action['action_id']},
                'deferred-' + action['action_id'])
            action = self.store.refresh_action(action['action_id'], action['revision'],
                {**action['payload'], 'preparation_job_id': job['id']})
            self.schedule_feature(job['id'])
        else:
            job = self.store.snapshot(identity)
        if job['state'] == 'completed' and (job.get('output') or {}).get('review'):
            review = job['output']['review']
            if job['coverage'] != 'complete':
                raise ToolError('iptv_review_incomplete; explicitly continue before applying')
            refreshed = ai_control.prepare_domain_operation(domain='iptv',
                items=[dict(row, title=row.get('provider_title') or '', iptv_provider_id=operation['provider_id'])
                       for row in review['proposals']], summary='Review IPTV matches after confirmed classification',
                operation={'kind': 'iptv_apply', 'feature': operation['feature'], 'provider_id': operation['provider_id'],
                           'review': review, 'selection': selection.public()}, plan_store=self.plans,
                provenance=action['selection'])
            if refreshed.get('state') != 'valid_plan':
                raise ToolError('no_eligible_iptv_proposals; inspect the preparation results')
            action = self.store.refresh_action(action['action_id'], action['revision'],
                {**action['payload'], 'owner_plan_id': refreshed['plan_id']})
            return {'action': action, 'plan': refreshed, 'preparation_job': job}
        return {'action': action, 'plan': plan, 'preparation_job': job}

    @staticmethod
    def _media_identity(row):
        if row.get('iptv_ref'):
            return row['iptv_ref']
        if row.get('series_id'):
            return {'domain': 'tv', 'series_id': row['series_id']}
        if row.get('iptv_provider_id') and row.get('source_key'):
            return {'domain': 'iptv', 'provider_id': row['iptv_provider_id'], 'source_key': row['source_key']}
        if row.get('path') and (row.get('candidate') or row.get('new_filename')):
            import os
            return {'domain': 'movie', 'file_id': hashlib.sha256(os.path.normcase(os.path.normpath(row['path'])).encode()).hexdigest()}
        return {'domain': 'movie', 'tmdb_id': str(row.get('tmdb_id') or ''), 'movie_key': row.get('movie_key') or ''}

    def _execute_domain(self, plan):
        operation, items = plan['operation'], plan['items']
        kind, effects = operation['kind'], []
        try:
            if kind == 'movie_list':
                action, identity = operation['action'], operation['list_id']
                if action in ('rename', 'delete'):
                    effects.append(self._read('user_list_detail', values={'list_id': identity},
                        method='PATCH' if action == 'rename' else 'DELETE', body={'name': operation['name']}))
                else:
                    for movie in items:
                        effects.append(self._read('user_list_movies', values={'list_id': identity},
                            method='POST' if action == 'add' else 'DELETE', body={'movie': movie}))
            elif kind == 'movie_state':
                for movie in items:
                    if operation['state_kind'] == 'followed':
                        effects.append(self._read('user_followed_releases', method='POST' if operation['active'] else 'DELETE',
                                                  body={'movie': movie}))
                    else:
                        effects.append(self._read('user_system_list_toggle', method='POST',
                            values={'system_type': operation['state_kind']}, body={'movie': movie, 'active': operation['active']}))
            elif kind == 'tv_list':
                action, identity = operation['action'], operation['list_id']
                if action == 'create':
                    created = self._read('tv_create_list', method='POST', body={'name': operation['name']})
                    effects.append(created)
                    identity = created['id']
                if action in ('rename', 'delete'):
                    effects.append(self._read('tv_rename_list' if action == 'rename' else 'tv_delete_list',
                        method='PATCH' if action == 'rename' else 'DELETE', values={'list_id': identity}, body={'name': operation['name']}))
                elif any(row.get('series_id') for row in items):
                    effects.append(self._read('tv_add_list_series' if action in ('create', 'add') else 'tv_remove_list_series',
                        method='POST' if action in ('create', 'add') else 'DELETE', values={'list_id': identity},
                        body={'series_ids': [row['series_id'] for row in items]}))
            elif kind == 'tv_state':
                for row in items:
                    watched = operation['state_kind'] == 'watched'
                    effects.append(self._read('tv_series_watched' if watched else 'tv_watchlist', method='POST',
                        values={'series_id': row['series_id']}, body={('watched' if watched else 'watchlisted'): operation['active']}))
            elif kind == 'tv_task':
                current = self._read('tv_task_preview', method='POST', values={'series_id': operation['series_id']}, body=operation['body'])
                if current != operation['preview']:
                    raise ToolError('tv_task_preview_changed')
                saved = self._read('tv_task_save', method='POST', values={'series_id': operation['series_id']}, body=operation['body'])
                effects.append(saved)
                effects.append(self._read('tv_task_start', method='POST', values={'task_id': saved['id']}, body={}))
            elif kind == 'tv_task_cancel':
                effects.append(self._read('tv_task_cancel', method='POST', values={'task_id': operation['task_id']},
                    body={'mode': operation['mode'], 'token': operation['preview']['token']}))
            elif kind == 'tv_finish_season':
                effects.append(self._read('tv_task_finish_season', method='POST', values={'task_id': operation['task_id']}, body={}))
            elif kind == 'tv_delete':
                identities = sorted(set(row['series_id'] for row in items))
                if identities != operation['series_ids']:
                    raise ToolError('tv_delete_subset_requires_new_preview')
                effects.append(self._read('tv_bulk_delete', method='POST', body={
                    'series_ids': identities, 'token': operation['preview']['token']}))
            elif kind == 'iptv_list':
                action, identity, provider = operation['action'], operation['list_id'], operation['provider_id']
                if action == 'create':
                    created = self._read('iptv_lists', method='POST', values={'provider_id': provider}, body={'name': operation['name']})
                    effects.append(created)
                    identity = created['list_id']
                if action in ('rename', 'delete'):
                    effects.append(self._read('iptv_list_detail', method='PATCH' if action == 'rename' else 'DELETE',
                        values={'provider_id': provider, 'list_id': identity}, body={'name': operation['name']}))
                else:
                    for row in items:
                        ref = row.get('iptv_ref')
                        if ref:
                            values = {'provider_id': provider, 'list_id': identity}
                            values.update({'movie_key': ref['item_id']} if ref['kind'] == 'movie' else
                                          {'kind': ref['kind'], 'item_id': ref['item_id']})
                            effects.append(self._read('iptv_movie_list_membership' if ref['kind'] == 'movie' else 'iptv_list_item',
                                method='POST' if action in ('create', 'add') else 'DELETE', values=values, body={}))
            elif kind == 'iptv_favorite':
                for row in items:
                    ref = row['iptv_ref']
                    values = {'provider_id': ref['provider_id'], 'movie_key': ref['item_id']} if ref['kind'] == 'movie' else {
                        key: ref[key] for key in ('provider_id', 'kind', 'item_id')}
                    effects.append(self._read('iptv_movie_favorite' if ref['kind'] == 'movie' else 'iptv_favorite', method='POST',
                        values=values, body={'favorite': operation['active']}))
            elif kind == 'notifications_read':
                effects.append(self._read('notification_read', method='POST', body={'ids': [row['id'] for row in items]}))
            elif kind == 'collection_override':
                effects.append(self._read('save_user_collection', method='POST', body={
                    'collection_id': operation['collection_id'], 'original': operation['original'], 'parts': items}))
            elif kind == 'media':
                current = self.media_resolver(operation['reference'], operation['action'], operation['restart'])
                if self._media_fingerprint(current) != operation['review_fingerprint']:
                    raise ToolError('media_changed; prepare a fresh playback review')
                owner = operation['owner']
                effects.append(self._read(owner['endpoint'], method='POST', values=owner.get('values'), body=owner['body']))
            elif kind == 'metadata_apply':
                effects.append(self._read('smart_match_apply', method='POST', values={'job_id': operation['job_id']},
                    body={'proposal_ids': [row['id'] for row in items]}))
            elif kind == 'metadata_rename':
                effects.append(self._read('smart_rename_apply', method='POST', body={
                    'token': operation['preview']['token'], 'paths': [row['path'] for row in items]}))
            elif kind == 'iptv_apply':
                provider = operation['provider_id']
                if operation['feature'] == 'F4':
                    review = operation['review']
                    effects.append(self.iptv_factory(provider).classification_apply(
                        {'catalog_generation': review['catalog_generation'], 'proposals': items}, preserve_manual_locks=True))
                else:
                    effects.append(self._read('iptv_movie_match_job_apply', method='POST',
                        values={'provider_id': provider, 'job_id': operation['review']['job_id']},
                        body={'proposal_ids': [row['proposal_id'] for row in items]}))
            else:
                raise ToolError('unsupported_prepared_operation')
        except ToolError as error:
            return {'state': 'partial' if effects else 'unsafe', 'effects': effects, 'message': error.code}
        if any(isinstance(effect, dict) and effect.get('success') is False for effect in effects):
            return {'state': 'partial', 'effects': effects, 'message': 'The owner reported a failed operation; inspect its recorded results.'}
        if kind == 'iptv_apply' and any(effects[-1].get(key) for key in ('failed', 'locked', 'missing', 'skipped')):
            return {'state': 'partial', 'effects': effects, 'message': 'Review the applied, skipped, locked and failed targets.'}
        if kind in ('metadata_apply', 'metadata_rename') and effects[-1].get('failed'):
            return {'state': 'partial', 'effects': effects, 'message': 'Some reviewed metadata changes failed; inspect the owner results.'}
        return {'state': 'executed', 'effects': effects, 'message': 'CP returned the recorded operation results.'}
