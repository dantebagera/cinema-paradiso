import os
import tempfile
import threading
import unittest
from flask import Flask
from services import ai_control
from services.ai_catalog import ResultSet
from services.ai_jobs import AIJobStore
from services.ai_provider import AISelection
from services.chatgpt_skills import load
from services.chatgpt_tools import ToolContext, ToolError
from services.chatgpt_domain_tools import DomainTools
from services.curation_routes import register_curation_routes
from services.curation_store import UserCurationStore


class DomainTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ['CP_TEST_ROOT'])
        self.addCleanup(self.temp.cleanup)
        self.store, self.plans = AIJobStore(self.temp.name), ai_control.PlanStore()
        self.curation = UserCurationStore(self.temp.name)
        self.app = Flask('domain-fixture')
        register_curation_routes(self.app, lambda: self.curation, lambda movie: False)
        skill = load('F2')
        self.selection = AISelection('chatgpt', 1, 'account', 'model', skill['id'], '1', skill['hash'], 'F2')
        self.job = self.store.create('F2', self.selection, {'prompt': 'Create a studio list'}, 'request')
        self.store.start_run(self.job['id'], self.job['revision'])
        self.context = ToolContext(self.selection, self.job['id'], self.job['session_id'])
        self.context.private['cancel'] = threading.Event()
        self.result = ResultSet('set', 'query', tuple({'tmdb_id': str(i), 'title': str(i)} for i in range(1, 121)),
                                'complete', None, 6, 6, 120, 0, 0, None)
        self.context.result_sets['set'] = self.result
        self.tools = DomainTools(self.store, None, self.plans, self.dispatch,
            execute_movie=lambda plan_id, **kwargs: ai_control.execute_plan(plan_id, plan_store=self.plans,
                create_list=lambda name, movies: self.curation.create_list(name, movies=movies), **kwargs))

    def dispatch(self, endpoint, *, method, values, query, body):
        url = self.app.url_map.bind('localhost').build(endpoint, values, method=method)
        return self.app.test_client().open(url, method=method, query_string=query, json=body).json

    def test_list_preparation_uses_real_plan_and_confirmation_saves_only_the_subset_once(self):
        result = self.tools.registry.call('cp_movie.prepare_movie_list', {'action': 'create', 'name': 'Studio',
            'list_id': None, 'result_set': 'set', 'depends_on': []}, self.context)
        self.assertEqual(len(result.ui['plan']['items']), 120)
        self.assertFalse(any(row['name'] == 'Studio' for row in self.curation.list_all()))
        action = result.model
        outcome = self.tools.confirm(action['action_id'], self.selection.account_id, revision=action['revision'],
            selected_keys=['item-2', 'item-120'], confirmation_phrase='', request_key='confirm')
        self.assertEqual(outcome['state'], 'completed')
        saved = next(row for row in self.curation.list_all() if row['name'] == 'Studio')
        self.assertEqual({row['tmdb_id'] for row in saved['movies']}, {'2', '120'})
        again = self.tools.confirm(action['action_id'], self.selection.account_id, revision=action['revision'],
            selected_keys=['item-2', 'item-120'], confirmation_phrase='', request_key='confirm')
        self.assertEqual(again['outcome'], outcome['outcome'])
        self.assertEqual(len([row for row in self.curation.list_all() if row['name'] == 'Studio']), 1)

    def test_unsupported_quality_and_unowned_watched_never_prepare_a_write(self):
        for name, args in [('cp_movie.prepare_movie_download', {'quality': '4K', 'profile_id': None,
                            'result_set': 'set', 'depends_on': []}),
                           ('cp_movie.prepare_movie_state', {'kind': 'watched', 'active': True,
                            'result_set': 'set', 'depends_on': []})]:
            with self.assertRaises(ToolError):
                self.tools.registry.call(name, args, self.context)

    def test_invalid_or_empty_selection_does_not_consume_confirmation(self):
        prepared = self.tools.registry.call('cp_movie.prepare_movie_list', {'action': 'create', 'name': 'Studio',
            'list_id': None, 'result_set': 'set', 'depends_on': []}, self.context).model
        for selected in ([], ['item-121']):
            with self.assertRaises(ToolError):
                self.tools.confirm(prepared['action_id'], 'account', revision=0, selected_keys=selected,
                                   confirmation_phrase='', request_key='invalid')
        self.assertEqual(self.store.action(prepared['action_id'], 'account')['state'], 'prepared')

    def test_media_confirmation_rechecks_the_reviewed_source_before_starting_playback(self):
        writes = []
        source = {'item': {'title': 'A movie', 'path_key': 'opaque', 'size': 100},
                  'owner': {'endpoint': 'play_library_file', 'body': {'path_key': 'opaque', 'restart': False}}}
        import copy
        tools = DomainTools(self.store, None, self.plans, lambda *args, **kwargs: writes.append(kwargs) or {'success': True},
            execute_movie=self.tools.execute_movie, media_resolver=lambda *args: copy.deepcopy(source))
        prepared = tools.registry.call('cp_runtime.prepare_play', {'media': {'domain': 'movie', 'key': 'movie'},
            'restart': False, 'depends_on': []}, self.context)
        source['item']['size'] = 200
        outcome = tools.confirm(prepared.model['action_id'], 'account', revision=0,
            selected_keys=[prepared.ui['plan']['items'][0]['selection_key']], confirmation_phrase='', request_key='play')
        self.assertEqual(outcome['state'], 'failed')
        self.assertEqual(writes, [])

    def test_tv_delete_subset_requires_a_fresh_subset_review_before_any_deletion(self):
        deleted = []
        def dispatch(endpoint, **options):
            if endpoint == 'tv_series_detail':
                return {'id': options['values']['series_id'], 'title': 'Synthetic TV'}
            if endpoint == 'tv_bulk_delete_preview':
                return {'token': 'preview-' + str(options['body']['series_ids'])}
            if endpoint == 'tv_bulk_delete':
                deleted.append(options['body'])
                return {'success': True}
            self.fail(endpoint)
        tools = DomainTools(self.store, None, self.plans, dispatch, execute_movie=self.tools.execute_movie)
        prepared = tools.registry.call('cp_tv.prepare_tv_delete', {'series': [
            {'domain': 'tv', 'series_id': i, 'episode_id': None} for i in (1, 2)], 'depends_on': []}, self.context)
        action = prepared.model['action_id']
        with self.assertRaises(ToolError):
            tools.confirm(action, 'account', revision=0, selected_keys=['item-2'], confirmation_phrase='', request_key='first')
        self.assertFalse(deleted)
        reviewed = tools.review(action, 'account')
        self.assertEqual([row['series_id'] for row in reviewed['plan']['items']], [2])
        result = tools.confirm(action, 'account', revision=reviewed['action']['revision'], selected_keys=['item-2'],
                               confirmation_phrase='', request_key='reviewed-subset')
        self.assertEqual(result['state'], 'completed')
        self.assertEqual(deleted, [{'series_ids': [2], 'token': 'preview-[2]'}])

    def test_owner_failure_does_not_claim_requested_targets_were_completed(self):
        tools = DomainTools(self.store, None, self.plans, lambda *args, **kwargs: {'success': False},
                            execute_movie=self.tools.execute_movie)
        prepared = tools._prepare({'depends_on': []}, self.context, domain='movie', items=[{'tmdb_id': '1'}],
            summary='Watchlist', operation={'kind': 'movie_state', 'state_kind': 'watchlist', 'active': True})
        outcome = tools.confirm(prepared.model['action_id'], 'account', revision=0,
            selected_keys=['item-1'], confirmation_phrase='', request_key='failed-owner')
        self.assertEqual(outcome['state'], 'partial')
        self.assertEqual(outcome['outcome']['confirmed_media'], [])

    def test_iptv_matching_waits_for_confirmed_classification_then_starts_an_explicit_saved_run(self):
        from types import SimpleNamespace
        from dataclasses import replace
        from services.chatgpt_tools import IPTV_FILTERS
        scheduled = []
        row = {'source_key': 's_10', 'provider_title': 'Synthetic', 'proposal_id': 'classification'}
        native = SimpleNamespace(store=SimpleNamespace(
            source_generation=lambda: 7, source=lambda identity: dict(row),
            resolve_selection=lambda **kwargs: {'source_keys': ['s_10'], 'catalog_generation': 7}),
            classification_apply=lambda *args, **kwargs: {'applied': ['s_10']})
        def selection(parent, feature, **kwargs):
            skill = load(feature)
            return replace(parent, feature=feature, domain_id='provider', skill_id=skill['id'], skill_hash=skill['hash'])
        tools = DomainTools(self.store, None, self.plans, lambda *args, **kwargs: {'applied': ['s_10']},
            execute_movie=self.tools.execute_movie, feature_selection=selection, iptv_factory=lambda identity: native,
            run_feature=lambda *args: self.fail('Matching ran before explicit next-step preparation'),
            schedule_feature=scheduled.append)
        first = tools._prepare({'depends_on': []}, self.context, domain='iptv',
            items=[dict(row, iptv_provider_id='provider')], summary='Classify', operation={
                'kind': 'iptv_apply', 'feature': 'F4', 'provider_id': 'provider',
                'review': {'catalog_generation': 7, 'proposals': [row]}}).model
        self.context.prepared.append(first)
        filters = {key: None for key in IPTV_FILTERS['properties']}
        filters['view'] = 'provider'
        second = tools.registry.call('cp_iptv.prepare_iptv_match', {'provider_id': 'provider',
            'selection': {'mode': 'explicit', 'keys': ['source:s_10'], 'filters': filters},
            'depends_on': [first['action_id']]}, self.context)
        self.assertEqual(second.ui['plan']['operation']['kind'], 'iptv_deferred')
        self.assertFalse(scheduled)
        self.store.finish(self.job['id'], 'awaiting_confirmation')
        with self.assertRaises(ToolError): tools.review(second.model['action_id'], 'account')
        tools.confirm(first['action_id'], 'account', revision=0, selected_keys=['item-1'], confirmation_phrase='', request_key='classify')
        self.assertFalse(scheduled)
        tools.status(second.model['action_id'], 'account')
        self.assertFalse(scheduled, 'Read-only restoration cannot start inference')
        pending = tools.review(second.model['action_id'], 'account')
        self.assertEqual(len(scheduled), 1)
        child = pending['preparation_job']
        self.assertEqual(child['state'], 'queued')
        self.assertEqual(child['selection']['model'], self.selection.model)
        tools.review(second.model['action_id'], 'account')
        self.assertEqual(len(scheduled), 1, 'Repeated refresh cannot duplicate preparation')
        self.store.start_run(child['id'], 0)
        self.store.finish(child['id'], 'completed', coverage='complete', output={'review': {
            'job_id': 'native-match', 'proposals': [dict(row, proposal_id='match', candidate_tmdb_id=550)]}})
        ready = tools.review(second.model['action_id'], 'account')
        self.assertEqual(ready['plan']['operation']['kind'], 'iptv_apply')
        self.assertEqual(ready['plan']['items'][0]['source_key'], 's_10')
        result = tools.confirm(second.model['action_id'], 'account', revision=ready['action']['revision'],
            selected_keys=['item-1'], confirmation_phrase='', request_key='apply-match')
        self.assertEqual(result['state'], 'completed')

    def test_dependent_action_gets_a_new_review_for_actual_saved_subset(self):
        first = self.tools.registry.call('cp_movie.prepare_movie_list', {'action': 'create', 'name': 'Studio',
            'list_id': None, 'result_set': 'set', 'depends_on': []}, self.context).model
        self.context.prepared.append(first)
        second = self.tools.registry.call('cp_movie.prepare_movie_state', {'kind': 'watchlist', 'active': True,
            'result_set': 'set', 'depends_on': [first['action_id']]}, self.context).model
        with self.assertRaises(ToolError):
            self.tools.confirm(second['action_id'], 'account', revision=0, selected_keys=['item-1'],
                               confirmation_phrase='', request_key='blocked')
        self.tools.confirm(first['action_id'], 'account', revision=0, selected_keys=['item-2', 'item-120'],
                           confirmation_phrase='', request_key='first')
        reviewed = self.tools.review(second['action_id'], 'account')
        self.assertEqual({row['tmdb_id'] for row in reviewed['plan']['items']}, {'2', '120'})
        self.assertGreater(reviewed['action']['revision'], 0)
        outcome = self.tools.confirm(second['action_id'], 'account', revision=reviewed['action']['revision'],
            selected_keys=['item-2', 'item-120'], confirmation_phrase='', request_key='second')
        self.assertEqual(outcome['state'], 'completed')
        watched = next(row for row in self.curation.list_all() if row['id'] == 'watchlist')
        self.assertEqual({row['tmdb_id'] for row in watched['movies']}, {'2', '120'})

    def test_tv_monitor_prepares_future_policy_and_uses_actual_tv_task_owner(self):
        calls = []
        def dispatch(endpoint, **options):
            calls.append((endpoint, options))
            if endpoint == 'tv_series_detail':
                return {'id': 7, 'tmdb_id': 777, 'title': 'Fixture Show'}
            if endpoint == 'tv_task_preview':
                return {'metadata_complete': True, 'counts': {'review': 0}, 'target_episode_ids': [8]}
            if endpoint == 'tv_task_save':
                return {'id': 'actual-tv-task'}
            if endpoint == 'tv_task_start':
                return {'id': options['values']['task_id'], 'state': 'waiting'}
            self.fail(endpoint)
        tools = DomainTools(self.store, None, self.plans, dispatch, execute_movie=self.tools.execute_movie)
        prepared = tools.registry.call('cp_tv.prepare_tv_task', {'series': {'domain': 'tv', 'series_id': 7, 'episode_id': None},
            'scope': 'season', 'action': 'monitor', 'season': 2, 'episode_ids': [], 'profile_id': None, 'depends_on': []}, self.context)
        self.assertFalse(any(name in ('tv_task_save', 'tv_task_start') for name, options in calls))
        self.assertEqual(next(options['body']['action'] for name, options in calls if name == 'tv_task_preview'), 'future')
        result = tools.confirm(prepared.model['action_id'], 'account', revision=0, selected_keys=['item-1'],
                               confirmation_phrase='', request_key='tv-confirm')
        self.assertEqual(result['state'], 'completed')
        save = next(options for name, options in calls if name == 'tv_task_save')
        self.assertEqual(save['body']['action'], 'future')
        self.assertEqual(save['values']['series_id'], 7)
        self.assertEqual(result['outcome']['effects'][-1]['id'], 'actual-tv-task')

    def test_tv_episode_from_another_series_never_reaches_task_preview(self):
        def dispatch(endpoint, **options):
            self.assertEqual(endpoint, 'tv_selection')
            return {'items': [{'id': 8, 'season_number': 1, 'episode_number': 1}]}
        tools = DomainTools(self.store, None, self.plans, dispatch)
        with self.assertRaises(ToolError):
            tools.registry.call('cp_tv.prepare_tv_task', {'series': {'domain': 'tv', 'series_id': 7, 'episode_id': 99},
                'scope': 'episode', 'action': 'download', 'season': None, 'episode_ids': [], 'profile_id': None,
                'depends_on': []}, self.context)

    def test_iptv_movie_list_uses_provider_movie_owner_and_persists_actual_source_membership(self):
        from types import SimpleNamespace
        from services.iptv_routes import register_iptv_routes
        from services.iptv_movie_service import IPTVMovieService
        from services.iptv_metadata_settings import IPTVMetadataSettings
        from services.iptv_movie_store import source_key
        from tests.iptv_movie_fixtures import create_raw_service
        provider = 'a' * 32
        raw = create_raw_service(self.temp.name, provider)
        movies = IPTVMovieService(raw.root, provider, raw, IPTVMetadataSettings(self.temp.name))
        movies.start_projection(wait=True)
        manager = SimpleNamespace(service=lambda identity: raw, movie_service=lambda identity: movies,
                                  redacted_error=lambda error, identity: str(error))
        register_iptv_routes(self.app, manager)
        key = 'source:' + source_key('10')
        prepared = self.tools.registry.call('cp_iptv.prepare_iptv_list', {'provider_id': provider, 'action': 'create',
            'list_id': None, 'name': 'Provider Night', 'items': [{'domain': 'iptv', 'provider_id': provider,
                'kind': 'movie', 'item_id': key}], 'depends_on': []}, self.context)
        self.assertFalse(any(row['name'] == 'Provider Night' for row in raw.lists()))
        outcome = self.tools.confirm(prepared.model['action_id'], 'account', revision=0, selected_keys=['item-1'],
                                     confirmation_phrase='', request_key='iptv-confirm')
        self.assertEqual(outcome['state'], 'completed', outcome)
        saved = next(row for row in raw.lists() if row['name'] == 'Provider Night')
        membership = raw.list_entries(saved['list_id'])
        self.assertEqual(len(membership['items']), 1)
        self.assertEqual(str(membership['items'][0]['item_id']), '10')
        self.assertEqual(membership['items'][0]['kind'], 'movie')
