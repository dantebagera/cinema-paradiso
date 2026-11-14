import hashlib
import json
import os
import tempfile
import threading
import unittest
from types import SimpleNamespace

from services.ai_jobs import AIJobError, AIJobStore
from services.ai_provider import AISelection
from services.chatgpt_iptv import IPTVJob, run_bulk_apply
from services.chatgpt_skills import load
from services.chatgpt_transport import ChatGPTError, ChatGPTTransport
from services.iptv_movie_store import IPTVSelectionError
from services.iptv_movie_store import source_key
from services.iptv_movie_service import IPTVMovieService
from services.iptv_metadata_settings import IPTVMetadataSettings
from tests.iptv_movie_fixtures import create_raw_service, FakeTMDBClient, provider_catalog, tmdb_payload


def selection():
    return AISelection('chatgpt', 1, 'fixture-account', 'fixture-model', 'iptv-matching', '1',
                       load('F5')['hash'], 'F5', 'a' * 32)


def model_row(row, **overrides):
    return {'id': row['id'], 'category': 'Music', 'title': row['title'], 'year': '',
            'aliases': [], 'confidence': .99, 'uncertain': False, **overrides}


def reply(rows):
    return SimpleNamespace(text=json.dumps({'rows': rows}))


class BulkContracts(unittest.TestCase):
    def test_advanced_prompt_reaches_transport_and_preserves_verified_and_review_results(self):
        with tempfile.TemporaryDirectory(dir=os.environ['CP_TEST_ROOT']) as root:
            owner = self.provider(root, 2, titles=['Fixture Movie (2024)', 'Unknown specimen'])
            store = AIJobStore(root)
            job = self.launch(owner, store, 2, 1)
            captured = []

            def stream(url, *, payload, token, cancel):
                captured.append(payload)
                rows = json.loads(payload['input'][0]['content'])['rows']
                answers = [model_row(row, category='Film', year='2024', uncertain=row['id'] == '1')
                           for row in rows]
                text = json.dumps({'rows': answers})
                terminal = {'type': 'response.completed', 'response': {'status': 'completed',
                    'id': 'fixture', 'output': [{'type': 'message', 'content': [
                        {'type': 'output_text', 'text': text}]}]}}
                return iter([('data: ' + json.dumps(terminal) + '\n\n').encode()])

            def factory(_selection, identity):
                return ChatGPTTransport(lambda _: 'fixture', http=SimpleNamespace(stream=stream),
                    before_request=lambda: store.reserve_inference(identity), max_retries=0)

            done = IPTVJob(store, lambda _: owner, factory).run(job['id'])
            self.assertEqual((done['state'], done['run_calls'], len(captured)), ('completed', 1, 1))
            self.assertEqual([row['id'] for row in json.loads(captured[0]['input'][0]['content'])['rows']],
                             ['1'])  # The deterministic match never needs GPT.
            self.assertEqual(hashlib.sha256(captured[0]['instructions'].encode()).hexdigest(),
                             'a281c1445f51ccbeed985352df62fc8d7a080f3a75523942a0bc6a1185abaee4')
            results = {row['source_key']: row for row in done['results']}
            self.assertEqual(results[source_key('0')]['outcome'], 'verified')
            self.assertEqual(results[source_key('0')]['candidate_tmdb_id'], 550)
            self.assertEqual(results[source_key('1')]['outcome'], 'review')
            self.assertEqual(owner.store.source(source_key('0'))['category'], 'unclassified')
            review = store.snapshot(job['id'], review_view='pending_matches')
            self.assertEqual(review['review_counts']['applied'], 0)

    def test_previous_bulk_prompt_cannot_resume_or_discard_saved_results(self):
        with tempfile.TemporaryDirectory(dir=os.environ['CP_TEST_ROOT']) as root:
            owner = self.provider(root, 2)
            store = AIJobStore(root)
            job = store.create('F5', selection(), {'bulk_call_budget': 2,
                'bulk_protocol_hash': '891a3146e483f0a4f956b1a570cc55026bd3790ceb8f186c1bcb319dc4fc719a',
                'selection_snapshot': {'source_keys': [source_key('0'), source_key('1')],
                    'catalog_generation': owner.store.source_generation()}}, 'old-prompt')
            store.start_run(job['id'], job['revision'])
            store.add_results(job['id'], [{'domain': 'iptv', 'identity': source_key('0'),
                'card': {'source_key': source_key('0'), 'outcome': 'categorized', 'category': 'music'}}])
            paused = store.finish(job['id'], 'paused')
            store.continue_job(job['id'], paused['revision'], 'resume')
            done = self.runner(owner, store, lambda _: self.fail('Old prompt job made an inference')).run(job['id'])
            self.assertEqual((done['state'], done['message'], done['run_calls']),
                             ('failed', 'bulk_protocol_changed', 0))
            self.assertEqual(done['accepted_count'], 1)
            self.assertEqual(done['results'][0]['source_key'], source_key('0'))

    def provider(self, root, count, *, titles=None, client=FakeTMDBClient):
        raw = create_raw_service(root, 'a' * 32, movie_rows=[{'stream_id': str(i),
            'name': titles[i] if titles else f'Unknown Fixture {i}', 'category_id': 'movies-a'} for i in range(count)])
        owner = IPTVMovieService(raw.root, 'a' * 32, raw, IPTVMetadataSettings(root),
                                 tmdb_client_factory=client)
        owner.start_projection(wait=True)
        return owner

    def launch(self, owner, store, count, budget):
        return store.create('F5', selection(), {'bulk_call_budget': budget, 'selection_snapshot': {
            'source_keys': [source_key(str(i)) for i in range(count)],
            'catalog_generation': owner.store.source_generation()}}, 'start')

    def runner(self, owner, store, respond):
        def factory(_selection, job_id):
            def run(_selection, *, input_items, admit_request, **kwargs):
                admit_request()
                store.reserve_inference(job_id)
                return respond(json.loads(input_items[0]['content'])['rows'])
            return SimpleNamespace(run=run)
        return IPTVJob(store, lambda _: owner, factory)

    def test_continue_after_sync_uses_only_unfinished_eligible_sources(self):
        from flask import Flask
        from services.ai_routes import register_ai_routes
        from services.chatgpt_skills import IPTV_BULK_PROTOCOL_HASH

        with tempfile.TemporaryDirectory(dir=os.environ['CP_TEST_ROOT']) as root:
            owner = self.provider(root, 6)
            store = AIJobStore(root)
            keys = [source_key(str(i)) for i in range(6)]
            owner.store.set_match_state(keys, 'unmatched')
            catalog = owner.store.source_generation()
            snapshot = {'source_keys': keys, 'catalog_generation': catalog, 'mode': 'all-filtered',
                        'filters': {'review_scope': 'leftovers', 'review_view': 'unmatched'}}
            job = store.create('F5', selection(), {'bulk_call_budget': 10, 'titles_per_request': 2,
                'bulk_protocol_hash': IPTV_BULK_PROTOCOL_HASH, 'bulk_auto_apply': True,
                'selection_snapshot': snapshot}, 'launch')
            job_id = job['id']
            store.start_run(job_id, job['revision'])
            store.reserve_inference(job_id)
            saved = {'source_key': keys[2], 'outcome': 'review', 'category': 'music',
                     'previous_category': 'unclassified', 'classification_confidence': .98,
                     'locked': False, 'match_manual_lock': False, 'evidence': {}}
            store.add_results(job_id, [{'domain': 'iptv', 'identity': keys[2], 'card': saved}],
                bulk_work={'offset': 4, 'window_end': 4, 'pending': [], 'answers': {'3': None}, 'throttles': 0})
            failed = store.finish(job_id, 'failed', message='The provider catalog changed. Start a new review.')

            dispatched = []
            app = Flask(__name__)
            register_ai_routes(app, SimpleNamespace(snapshot=lambda *args, **kwargs: selection(),
                connection_selection=selection), jobs_factory=lambda: SimpleNamespace(store=store, start=dispatched.append),
                iptv_factory=lambda _: owner)
            client = app.test_client()
            path = f'/api/ai/jobs/{job_id}'
            continuation = {'revision': failed['revision'], 'request_key': 'resume'}
            self.assertTrue(client.get(path).json['bulk']['resume_after_sync'])

            owner.raw_service.store.replace_catalog(provider_catalog(movie_rows=[{'stream_id': str(i),
                'name': f'Unknown Fixture {i}', 'category_id': 'movies-a'} for i in [0, 1, 2, 3, 4, 6]]))
            response = client.post(f'{path}/continue', json=continuation)
            self.assertEqual(response.status_code, 409, response.json)
            self.assertEqual(response.json['error']['code'], 'iptv_projection_in_progress')
            self.assertEqual(dispatched, [])

            owner.start_projection(wait=True)
            owner.store.set_match_state([keys[4]], 'unmatched', manual_lock=True)
            owner.store.set_match_state([source_key('6')], 'unmatched')
            response = client.post(f'{path}/continue', json=continuation)
            self.assertEqual(response.status_code, 202, response.json)
            self.assertEqual((response.json['id'], response.json['bulk']['total'], response.json['run_calls']),
                             (job_id, len(keys), 1))
            self.assertEqual(dispatched, [job_id])
            queued = store.snapshot(job_id)
            self.assertEqual(queued['request']['selection_snapshot'], snapshot)
            self.assertEqual(queued['inference_budget'], 10)
            self.assertEqual(store.snapshot(job_id, review_view='classifications')['review_counts']['classifications'], 0)
            proposal = store.bulk_proposals(job_id, [keys[2]])[0]
            report = owner.apply_bulk_proposals([proposal], 'classification', owner.store.source_generation())
            self.assertEqual(report['skipped'], [keys[2]])

            local, sent = [], []
            propose = owner.bulk_source_proposal

            def record(source, *args, **kwargs):
                local.append(source['source_key'])
                return propose(source, *args, **kwargs)

            def respond(rows):
                sent.extend(row['title'] for row in rows)
                return reply([model_row(row) for row in rows])

            owner.bulk_source_proposal = record
            done = self.runner(owner, store, respond).run(job_id)
            self.assertEqual((done['state'], done['accepted_count'], done['run_calls']), ('completed', 6, 3))
            self.assertEqual(set(local), {keys[0], keys[1], keys[3]})
            self.assertCountEqual(sent, ['Unknown Fixture 0', 'Unknown Fixture 1', 'Unknown Fixture 3'])
            results = {row['source_key']: row for row in done['results']}
            self.assertEqual(results[keys[2]]['outcome'], 'review')
            self.assertIn('catalog', results[keys[2]]['apply_reason'])
            self.assertIn('no longer eligible', results[keys[4]]['review_reason'])
            self.assertIn('no longer eligible', results[keys[5]]['review_reason'])
            replay = client.post(f'{path}/continue', json=continuation)
            self.assertEqual((replay.status_code, replay.json['state'], replay.json['cursor']['run_number']), (202, 'completed', 1))

    def test_continue_after_sync_recovers_committed_apply_receipt_and_retires_old_proposal(self):
        from services.chatgpt_skills import IPTV_BULK_PROTOCOL_HASH
        from services.iptv_tmdb import normalize_tmdb_movie

        with tempfile.TemporaryDirectory(dir=os.environ['CP_TEST_ROOT']) as root:
            owner = self.provider(root, 3)
            store = AIJobStore(root)
            keys = [source_key(str(i)) for i in range(3)]
            owner.store.set_match_state(keys, 'unmatched')
            generation = owner.store.source_generation()
            snapshot = {'source_keys': keys, 'catalog_generation': generation}
            job = store.create('F5', selection(), {'bulk_call_budget': 10, 'bulk_auto_apply': True,
                'bulk_protocol_hash': IPTV_BULK_PROTOCOL_HASH, 'selection_snapshot': snapshot}, 'launch')
            job_id = job['id']
            store.start_run(job_id, job['revision'])
            store.add_results(job_id, [{'domain': 'iptv', 'identity': key, 'card': {
                'source_key': key, 'outcome': 'verified', 'category': 'film', 'bulk_automatic': True,
                'candidate_tmdb_id': 550, 'evidence': {}}} for key in keys[:2]],
                bulk_work={'offset': 2, 'pending': [], 'answers': {}, 'throttles': 0})
            apply = store.claim_automatic_bulk_apply(job_id)
            owner.store.apply_match(f'source:{keys[0]}', normalize_tmdb_movie(tmdb_payload()),
                method='chatgpt-bulk', bulk_operation_id=apply['id'], expected_generation=generation, stable_projection=True)
            store.checkpoint_bulk_apply(job_id, apply['id'], state='interrupted')
            failed = store.finish(job_id, 'failed', message='iptv_selection_changed')
            owner.raw_service.store.replace_catalog(provider_catalog(movie_rows=[{'stream_id': str(i),
                'name': f'Unknown Fixture {i}', 'category_id': 'movies-a'} for i in range(3)]))
            owner.start_projection(wait=True)

            resumed = store.continue_job(job_id, failed['revision'], 'resume', refresh_catalog=owner.bulk_catalog_continuation)
            proposals = {row['source_key']: row for row in resumed['results']}
            self.assertEqual(proposals[keys[0]]['apply_state'], 'applied')
            self.assertEqual(proposals[keys[0]]['apply_id'], apply['id'])
            self.assertEqual(proposals[keys[1]]['apply_state'], 'stale')
            self.assertEqual(resumed['cursor']['bulk_automatic_counts'], {'applied': 1, 'skipped': 1, 'locked': 0, 'failed': 0})
            self.assertEqual(store.bulk_work_sources(resumed), [keys[2]])
            self.assertEqual(store.snapshot(job_id, review_view='pending_matches')['review_counts']['pending_matches'], 0)
            done = self.runner(owner, store, lambda rows: reply([model_row(row) for row in rows])).run(job_id)
            self.assertEqual((done['state'], done['accepted_count'], done['run_calls']), ('completed', 3, 1))

    def test_saved_search_recheck_reuses_hints_and_applies_only_newly_verified_results(self):
        from flask import Flask
        from services.ai_routes import register_ai_routes
        from services.chatgpt_skills import IPTV_BULK_PROTOCOL_HASH
        from services.iptv_tmdb import interpreted_title_evidence

        with tempfile.TemporaryDirectory(dir=os.environ['CP_TEST_ROOT']) as root:
            titles = ('Fixture Movie (2024)', 'Saved Other (2024)', 'Protected Listing (2024)',
                      'Earlier Title (2024)', 'Retired Listing (2024)', 'Old Proposal (2024)')
            owner = self.provider(root, len(titles), titles=titles)
            store = AIJobStore(root)
            keys = [source_key(str(i)) for i in range(len(titles))]
            generation = owner.store.source_generation()
            job = store.create('F5', selection(), {'bulk_call_budget': 10, 'bulk_auto_apply': True,
                'bulk_protocol_hash': IPTV_BULK_PROTOCOL_HASH, 'selection_snapshot': {
                    'source_keys': keys, 'catalog_generation': generation}}, 'launch')
            job_id = job['id']
            store.start_run(job_id, job['revision'])
            store.reserve_inference(job_id)
            rows = []
            sources = owner.store.bulk_sources(keys, generation)
            for index, key in enumerate(keys):
                interpretation = model_row({'id': str(index), 'title': titles[index].split(' (')[0]}, category='Film', year='2024')
                identity = interpreted_title_evidence(owner._source_title_evidence(sources[key]), interpretation)['bulk_identity']
                rows.append({'domain': 'iptv', 'identity': key, 'card': {
                    'source_key': key, 'proposal_id': key, 'outcome': 'verified' if index in (1, 5) else 'review', 'category': 'film',
                    'review_reason': 'Candidate search limit reached before competing identities could be ruled out.',
                    'match_manual_lock': False, 'evidence': {'interpretation': interpretation, 'identity': identity},
                    **({'apply_state': 'stale', 'catalog_stale': True} if index == 0 else
                       {'apply_state': 'applied', 'candidate_tmdb_id': 552} if index == 1 else
                       {'candidate_tmdb_id': 553} if index == 5 else {})}})
            store.add_results(job_id, rows, bulk_work={'offset': len(keys), 'pending': [], 'answers': {}, 'throttles': 0})
            completed = store.finish(job_id, 'completed', coverage='complete')
            owner.store.set_match_state([keys[2]], 'unmatched', manual_lock=True)

            dispatch = []
            app = Flask(__name__)
            register_ai_routes(app, SimpleNamespace(snapshot=lambda *a, **kw: selection(), connection_selection=selection),
                jobs_factory=lambda: SimpleNamespace(store=store, start=dispatch.append), iptv_factory=lambda _: owner)
            client = app.test_client()
            path = f'/api/ai/jobs/{job_id}'
            self.assertEqual(client.get(path).json['bulk']['search_recheck_candidates'], 4)
            body = {'revision': completed['revision'], 'request_key': 'focused', 'recheck_search_limits': True}
            refreshed = {0: titles[0], 1: titles[1], 2: titles[2], 3: 'Changed Title (2024)', 5: titles[5],
                         6: 'New Listing (2024)'}
            def sync():
                owner.raw_service.store.replace_catalog(provider_catalog(movie_rows=[{'stream_id': str(i),
                    'name': title, 'category_id': 'movies-a'} for i, title in refreshed.items()]))

            sync()
            pending = client.post(f'{path}/continue', json=body)
            self.assertEqual((pending.status_code, pending.json['error']['code']), (409, 'iptv_projection_in_progress'))
            self.assertEqual(dispatch, [])
            owner.start_projection(wait=True)
            self.assertNotEqual(owner.store.source_generation(), generation)
            self.assertEqual(client.post(f'{path}/continue', json=body).status_code, 202)
            self.assertEqual(dispatch, [job_id])
            queued = store.snapshot(job_id)
            self.assertEqual(queued['cursor']['bulk_catalog_generation'], owner.store.source_generation())
            self.assertEqual(queued['request']['selection_snapshot']['catalog_generation'], generation)
            self.assertEqual(queued['cursor']['bulk_search_recheck']['keys'], [keys[i] for i in (0, 2, 3, 4)])
            paused = store.request_bulk_pause(job_id, queued['cursor']['run_number'])
            self.assertEqual(paused['state'], 'paused')
            sync()
            pending = client.post(f'{path}/continue', json={'revision': paused['revision'], 'request_key': 'resume-focused'})
            self.assertEqual((pending.status_code, pending.json['error']['code']), (409, 'iptv_projection_in_progress'))
            owner.start_projection(wait=True)
            self.assertEqual(client.post(f'{path}/continue', json={'revision': paused['revision'],
                'request_key': 'resume-focused'}).status_code, 202)
            runner = IPTVJob(store, lambda _: owner, lambda *_: self.fail('Recheck created a ChatGPT transport'))
            done = runner.run(job_id)
            self.assertEqual((done['state'], done['accepted_count'], done['run_calls']), ('completed', 6, 1))
            results = {row['source_key']: row for row in done['results']}
            self.assertEqual((results[keys[0]]['apply_state'], results[keys[0]]['candidate_tmdb_id']), ('applied', 550))
            self.assertEqual(results[keys[1]]['candidate_tmdb_id'], 552)
            self.assertEqual([results[k]['outcome'] for k in keys[2:5]], ['review'] * 3)
            self.assertTrue(all('no longer eligible' in results[k]['review_reason'] for k in keys[2:5]))
            self.assertEqual(results[keys[5]]['apply_state'], 'stale')
            self.assertEqual(client.get(path).json['bulk']['search_recheck'], {'processed': 4, 'total': 4, 'verified': 1})
            self.assertEqual(client.post(f'{path}/continue', json={'revision': paused['revision'],
                'request_key': 'resume-focused'}).json['cursor']['run_number'], 2)

    def test_transport_recovers_only_completed_consistent_text(self):
        text = '{"rows":[]}'
        delta = {'type': 'response.output_text.delta', 'delta': text}
        def completed(terminal=''):
            return {'type': 'response.completed', 'response': {'status': 'completed', 'id': 'test',
                'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': terminal}]}]}}
        def run(events, recover=True):
            body = ''.join('data: ' + json.dumps(event) + '\n\n' for event in events).encode()
            http = SimpleNamespace(stream=lambda *args, **kwargs: iter([body[:31], body[31:]]))
            transport = ChatGPTTransport(lambda _: 'fixture', http=http)
            options = {'recover_completed_text': True} if recover else {}
            return transport.run(selection(), instructions='fixture', input_items=[], tools=[],
                                 cancel=threading.Event(), **options).text
        self.assertEqual(run([delta, completed()]), text)
        self.assertEqual(run([delta, completed(text)]), text)
        self.assertEqual(run([delta, completed()], recover=False), '')
        with self.assertRaises(ChatGPTError) as incomplete:
            run([delta])
        self.assertEqual(incomplete.exception.code, 'missing_terminal_event')
        with self.assertRaises(ChatGPTError) as mismatch:
            run([delta, completed('{}')])
        self.assertEqual(mismatch.exception.code, 'inconsistent_output_text')
        done = {'type': 'response.output_text.done', 'text': '{}'}
        with self.assertRaises(ChatGPTError) as mismatch:
            run([delta, done, completed()])
        self.assertEqual(mismatch.exception.code, 'inconsistent_output_text')
        with self.assertRaises(ChatGPTError) as incomplete:
            run([delta, {'type': 'response.incomplete', 'response': {
                'status': 'incomplete', 'incomplete_details': {'reason': 'max_output_tokens'}}}])
        self.assertEqual(incomplete.exception.code, 'max_output_tokens')

    def test_bulk_reservations_and_resume_keep_cumulative_budget(self):
        with tempfile.TemporaryDirectory(dir=os.environ['CP_TEST_ROOT']) as root:
            store = AIJobStore(root)
            request = {'bulk_call_budget': 1, 'selection_snapshot': {
                'source_keys': ['s_1', 's_2'], 'catalog_generation': 0}}
            job = store.create('F5', selection(), request, 'start')
            identity = job['id']
            store.start_run(identity, job['revision'])
            store.reserve_inference(identity)
            with self.assertRaises(AIJobError) as paused:
                store.reserve_inference(identity)
            self.assertEqual(paused.exception.code, 'paused_budget')
            job = store.snapshot(identity)
            self.assertEqual((job['run_calls'], job['inference_budget']), (1, 1))
            job = store.continue_job(identity, job['revision'], 'add', extra_calls=2)
            self.assertEqual((job['state'], job['run_calls'], job['inference_budget']), ('queued', 1, 3))

    def test_filtered_bulk_snapshot_above_legacy_limit(self):
        with tempfile.TemporaryDirectory(dir=os.environ['CP_TEST_ROOT']) as root:
            owner = self.provider(root, 6413)
            owner.store.set_match_state([source_key(str(i)) for i in range(6413)], 'unmatched')
            options = {'mode': 'all-filtered', 'filters': {'review_view': 'unmatched'}}
            with self.assertRaises(IPTVSelectionError):
                owner.store.resolve_selection(**options)
            resolved = owner.store.resolve_selection(**options, bulk=True)
            self.assertEqual(len(set(resolved['source_keys'])), 6413)

    def test_apply_snapshot_filters_legacy_receipts_and_persists_claim(self):
        with tempfile.TemporaryDirectory(dir=os.environ['CP_TEST_ROOT']) as root:
            owner = self.provider(root, 23)
            store = AIJobStore(root)
            job = self.launch(owner, store, 23, 100)
            identity = job['id']
            store.start_run(identity, job['revision'])
            for i in range(23):
                key = source_key(str(i))
                store.add_results(identity, [{'domain': 'iptv', 'identity': key, 'card': {
                    'source_key': key, 'outcome': 'verified' if i < 22 else 'review',
                    'category': 'film', 'candidate_tmdb_id': 550}}])
            store.finish(identity, 'paused')
            store.mark_bulk_applied(identity, [source_key('0')])
            pending = store.snapshot(identity, review_view='pending_matches', page=2)
            self.assertEqual(pending['review_counts'], {'pending_matches': 21, 'applied': 1,
                'needs_attention': 1, 'classifications': 0, 'retry_failed': 0})
            self.assertEqual(len(pending['results']), 1)
            apply, claimed = store.claim_bulk_apply(identity, 'verified_pending', pending['revision'], 21, 'all')
            self.assertTrue(claimed)
            self.assertEqual(apply['total'], 21)
            self.assertEqual(store.claim_bulk_apply(identity, 'verified_pending', pending['revision'], 21, 'all'),
                             (apply, False))
            latest = store.snapshot(identity)
            with self.assertRaisesRegex(AIJobError, 'bulk_apply_active'):
                store.continue_job(identity, latest['revision'], 'resume-scan')

    def seed_apply(self, owner, store, count):
        job = self.launch(owner, store, count, 100)
        identity = job['id']
        store.start_run(identity, job['revision'])
        keys = [source_key(str(i)) for i in range(count)]
        store.add_results(identity, [{'domain': 'iptv', 'identity': key, 'card': {
            'source_key': key, 'outcome': 'verified', 'category': 'film',
            'previous_category': 'unclassified', 'confidence': 100, 'evidence': {},
            'candidate_tmdb_id': 550 + i % 2}} for i, key in enumerate(keys)])
        return store.finish(identity, 'paused'), keys

    def test_apply_reconciles_provider_commit_and_keeps_existing_locks(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory(dir=os.environ['CP_TEST_ROOT']) as root:
            owner = self.provider(root, 23, client=lambda: FakeTMDBClient(movies={
                550: tmdb_payload(), 551: tmdb_payload(551, 'Other Fixture')}))
            store = AIJobStore(root)
            job, keys = self.seed_apply(owner, store, 23)
            identity = job['id']
            generation = owner.store.source_generation()
            applied_legacy = store.bulk_proposals(identity, keys[:1])
            owner.apply_bulk_proposals(applied_legacy, 'match', generation)
            store.mark_bulk_applied(identity, keys[:1])
            owner.store.set_match_state([keys[2]], 'unmatched', manual_lock=True)
            latest = store.snapshot(identity)
            apply, _ = store.claim_bulk_apply(identity, 'verified_pending', latest['revision'], 22, 'confirm')
            original = owner.store.apply_match
            def commit_then_crash(*args, **kwargs):
                original(*args, **kwargs)
                raise RuntimeError('test process exited after provider commit')
            with patch.object(owner.store, 'apply_match', side_effect=commit_then_crash):
                with self.assertRaisesRegex(RuntimeError, 'after provider commit'):
                    run_bulk_apply(store, owner, identity, apply, generation, lambda: None)
            with owner.store.bulk_match_receipts(keys[:3], apply['id']) as receipts:
                self.assertEqual(receipts, {keys[1]})
            recovered = AIJobStore(root, process_alive=lambda pid: False)
            interrupted = recovered.snapshot(identity, review_view='pending_matches')
            self.assertEqual(interrupted['bulk_apply']['state'], 'interrupted')
            self.assertEqual(interrupted['review_counts']['pending_matches'], 22)
            resumed, dispatch = recovered.control_bulk_apply(identity, apply['id'], 'resume',
                                                               interrupted['revision'], 'resume')
            self.assertTrue(dispatch)
            with patch.object(owner.store, 'apply_match', wraps=original) as writes:
                run_bulk_apply(recovered, owner, identity, resumed, generation, lambda: None)
                self.assertNotIn(f'source:{keys[1]}', [call.args[0] for call in writes.call_args_list])
            result = recovered.snapshot(identity, review_view='needs_attention')
            self.assertEqual(result['bulk_apply']['counts'], {'applied': 21, 'locked': 1, 'skipped': 0, 'failed': 0})
            self.assertEqual(result['review_counts']['applied'], 22)
            self.assertEqual(result['review_counts']['pending_matches'], 0)
            self.assertEqual(result['results'][0]['source_key'], keys[2])
            with owner.store.connection() as connection:
                receipts = connection.execute("SELECT count(*) FROM decision_audit WHERE job_id=? AND domain='bulk-match'",
                                              (apply['id'],)).fetchone()[0]
            self.assertEqual(receipts, 21)

    def test_apply_stop_preserves_commits_and_retry_replays_original_confirmation(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory(dir=os.environ['CP_TEST_ROOT']) as root:
            owner = self.provider(root, 5, client=lambda: FakeTMDBClient(movies={
                550: tmdb_payload(), 551: tmdb_payload(551, 'Other Fixture')}))
            store = AIJobStore(root)
            job, keys = self.seed_apply(owner, store, 5)
            identity = job['id']
            generation = owner.store.source_generation()
            claim, _ = store.claim_bulk_apply(identity, 'verified_pending', job['revision'], 5, 'first')
            original = owner.store.apply_match
            def write_then_stop(*args, **kwargs):
                result = original(*args, **kwargs)
                latest = store.snapshot(identity)
                store.control_bulk_apply(identity, claim['id'], 'stop', latest['revision'], 'stop')
                return result
            with patch.object(owner.store, 'apply_match', side_effect=write_then_stop):
                run_bulk_apply(store, owner, identity, claim, generation, lambda: None)
            stopped = store.snapshot(identity, review_view='pending_matches')
            self.assertEqual(stopped['bulk_apply']['state'], 'stopped')
            self.assertEqual([item['source_key'] for item in stopped['results']], keys[1:])
            self.assertEqual(stopped['bulk_apply']['counts']['applied'], 1)
            second, _ = store.claim_bulk_apply(identity, 'verified_pending', stopped['revision'], 4, 'second')
            replay, dispatch = store.claim_bulk_apply(identity, 'verified_pending', job['revision'], 5, 'first')
            self.assertFalse(dispatch)
            self.assertEqual((replay['id'], replay['state']), (claim['id'], 'stopped'))
            owner.store.begin_projection(generation + 1, 1)
            run_bulk_apply(store, owner, identity, second, generation, lambda: None)
            stale = store.snapshot(identity, review_view='pending_matches')
            self.assertEqual(stale['bulk_apply']['state'], 'stale')
            self.assertEqual(stale['review_counts']['pending_matches'], 4)

    def test_apply_retry_only_covers_transient_write_failures(self):
        from services.iptv_tmdb import IPTVTMDBError
        from unittest.mock import patch
        with tempfile.TemporaryDirectory(dir=os.environ['CP_TEST_ROOT']) as root:
            owner = self.provider(root, 5, client=lambda: FakeTMDBClient(movies={
                550: tmdb_payload(), 551: tmdb_payload(551, 'Other Fixture')}))
            store = AIJobStore(root)
            job, keys = self.seed_apply(owner, store, 5)
            identity = job['id']
            generation = owner.store.source_generation()
            owner.store.apply_classification_decisions([{'source_key': keys[4], 'category': 'sports', 'confidence': 1}])
            claim, _ = store.claim_bulk_apply(identity, 'verified_pending', job['revision'], 5, 'apply')
            original = FakeTMDBClient.normalized_movie
            def normalize(client, tmdb_id, language=''):
                if tmdb_id == 551:
                    raise IPTVTMDBError('Temporarily busy', status=503, retryable=True)
                return original(client, tmdb_id, language)
            with patch.object(FakeTMDBClient, 'normalized_movie', normalize):
                run_bulk_apply(store, owner, identity, claim, generation, lambda: None)
            issues = store.snapshot(identity, review_view='needs_attention')
            self.assertEqual(issues['review_counts'], {'pending_matches': 0, 'applied': 2,
                'needs_attention': 3, 'classifications': 0, 'retry_failed': 2})
            with self.assertRaisesRegex(AIJobError, 'stale_bulk_apply') as error:
                store.claim_bulk_apply(identity, 'retry_failed', issues['revision'], 3, 'stale')
            self.assertEqual(error.exception.details['actual_count'], 2)
            retry, _ = store.claim_bulk_apply(identity, 'retry_failed', issues['revision'], 2, 'retry')
            run_bulk_apply(store, owner, identity, retry, generation, lambda: None)
            complete = store.snapshot(identity, review_view='needs_attention')
            self.assertEqual(complete['review_counts']['applied'], 4)
            self.assertEqual(complete['review_counts']['retry_failed'], 0)
            self.assertEqual(complete['results'][0]['source_key'], keys[4])

    def test_resume_finishes_saved_preparation_window_before_dispatch(self):
        with tempfile.TemporaryDirectory(dir=os.environ['CP_TEST_ROOT']) as root:
            owner = self.provider(root, 8)
            store = AIJobStore(root)
            keys = [source_key(str(i)) for i in range(8)]
            job = store.create('F5', selection(), {'bulk_call_budget': 2, 'titles_per_request': 5,
                'selection_snapshot': {'source_keys': keys, 'catalog_generation': owner.store.source_generation()}}, 'start')
            identity = job['id']
            store.start_run(identity, job['revision'])
            store.add_results(identity, [], bulk_work={'offset': 2, 'window_end': 5,
                'pending': [[0, 0], [1, 0]], 'answers': {}, 'throttles': 0})
            paused = store.finish(identity, 'paused')
            with self.assertRaisesRegex(AIJobError, 'stale_bulk_allowance'):
                store.continue_job(identity, paused['revision'], 'arbitrary', extra_calls=1)
            store.continue_job(identity, paused['revision'], 'resume')
            sent = []
            def respond(rows):
                sent.append([row['id'] for row in rows])
                return reply([model_row(row) for row in rows])
            done = self.runner(owner, store, respond).run(identity)
            self.assertEqual((done['state'], done['run_calls'], done['accepted_count']), ('completed', 2, 8))
            self.assertEqual(sent, [['0', '1', '2', '3', '4'], ['5', '6', '7']])
            self.assertIsNotNone(done['cursor']['checkpoint_at'])

    def test_calculated_job_offers_only_pending_batches_after_budget_pause(self):
        from services.ai_jobs import bulk_extra_calls
        with tempfile.TemporaryDirectory(dir=os.environ['CP_TEST_ROOT']) as root:
            owner = self.provider(root, 8)
            store = AIJobStore(root)
            keys = [source_key(str(i)) for i in range(8)]
            job = store.create('F5', selection(), {'bulk_call_budget': 2, 'titles_per_request': 5,
                'selection_snapshot': {'source_keys': keys, 'catalog_generation': owner.store.source_generation()}}, 'start')
            calls = []
            def respond(rows):
                calls.append(len(rows))
                return reply([model_row(row) for row in (rows[:1] if len(calls) == 1 else rows)])
            runner = self.runner(owner, store, respond)
            paused = runner.run(job['id'])
            self.assertEqual((paused['state'], paused['run_calls'], paused['accepted_count']), ('paused_budget', 2, 5))
            self.assertEqual(bulk_extra_calls(paused['request'], paused['cursor']), 1)
            with self.assertRaisesRegex(AIJobError, 'stale_bulk_allowance'):
                store.continue_job(job['id'], paused['revision'], 'incorrect-offer', extra_calls=2)
            store.continue_job(job['id'], paused['revision'], 'approve-offer', extra_calls=1)
            done = runner.run(job['id'])
            self.assertEqual((done['state'], done['run_calls'], done['accepted_count']), ('completed', 3, 8))
            self.assertEqual(calls, [5, 4, 3])

    def test_apply_40000_proposals_with_bounded_reads(self):
        from unittest.mock import patch
        count = 40_000
        with tempfile.TemporaryDirectory(dir=os.environ['CP_TEST_ROOT']) as root:
            owner = self.provider(root, count, client=lambda: FakeTMDBClient(movies={
                550: tmdb_payload(), 551: tmdb_payload(551, 'Other Fixture')}))
            store = AIJobStore(root)
            job, keys = self.seed_apply(owner, store, count)
            identity = job['id']
            owner.store.set_match_state(keys[-3:], 'unmatched', manual_lock=True)
            apply, _ = store.claim_bulk_apply(identity, 'verified_pending', job['revision'], count, 'confirm')
            reads = []
            original = store.bulk_apply_chunk
            def chunk(*args):
                rows = original(*args)
                reads.append(len(rows))
                return rows
            with patch.object(store, 'bulk_apply_chunk', side_effect=chunk):
                run_bulk_apply(store, owner, identity, apply, owner.store.source_generation(), lambda: None)
            self.assertEqual(reads, [100] * 400 + [0])
            result = store.snapshot(identity, review_view='pending_matches')
            self.assertEqual(result['results'], [])
            self.assertEqual(result['review_counts']['applied'], count - 3)
            self.assertEqual(result['bulk_apply']['counts'], {'applied': count - 3, 'locked': 3, 'skipped': 0, 'failed': 0})
            with owner.store.connection() as connection:
                counts = dict(connection.execute("SELECT tmdb_id,count(*) FROM source_matches WHERE state='matched-manual' GROUP BY tmdb_id"))
            self.assertEqual(counts, {550: 19999, 551: 19998})

    def test_valid_rows_checkpoint_before_budget_pause_and_only_missing_rows_retry(self):
        with tempfile.TemporaryDirectory(dir=os.environ['CP_TEST_ROOT']) as root:
            raw = create_raw_service(root, 'a' * 32, movie_rows=[{'stream_id': str(i),
                'name': f'Unknown Fixture {i}', 'category_id': 'movies-a'} for i in range(100)])
            owner = IPTVMovieService(raw.root, 'a' * 32, raw, IPTVMetadataSettings(root),
                                     tmdb_client_factory=FakeTMDBClient)
            owner.start_projection(wait=True)
            keys = [source_key(str(i)) for i in range(100)]
            store = AIJobStore(root)
            request = {'bulk_call_budget': 1, 'selection_snapshot': {
                'source_keys': keys, 'catalog_generation': owner.store.source_generation()}}
            job = store.create('F5', selection(), request, 'start')
            sent = []
            def run(_selection, *, input_items, **kwargs):
                store.reserve_inference(job['id'])
                items = json.loads(input_items[0]['content'])['rows']
                sent.append([row['id'] for row in items])
                valid = items[:1] if len(sent) == 1 else items
                return SimpleNamespace(text=json.dumps({'rows': [{
                    'id': row['id'], 'category': 'Music', 'title': row['title'], 'year': '',
                    'aliases': [], 'confidence': .99, 'uncertain': False} for row in valid]}))
            runner = IPTVJob(store, lambda _: owner, lambda *_: SimpleNamespace(run=run))
            paused = runner.run(job['id'])
            self.assertEqual((paused['state'], paused['accepted_count']), ('paused_budget', 1))
            self.assertEqual(owner.store.source(keys[0])['category'], 'unclassified')
            store.continue_job(job['id'], paused['revision'], 'resume', extra_calls=2)
            done = runner.run(job['id'])
            self.assertEqual((done['state'], done['accepted_count'], done['run_calls']), ('completed', 100, 3))
            self.assertEqual([len(batch) for batch in sent], [100, 50, 49])
            self.assertEqual(sent[1] + sent[2], sent[0][1:])
            result = done['results'][0]
            report = owner.apply_bulk_proposals([result], 'classification', request['selection_snapshot']['catalog_generation'])
            self.assertEqual(report['applied'], [keys[0]])
            self.assertEqual(owner.store.source(keys[0])['category'], 'music')

    def test_tens_of_thousands_complete_automatically_above_legacy_call_limit(self):
        count = 25_001
        with tempfile.TemporaryDirectory(dir=os.environ['CP_TEST_ROOT']) as root:
            owner = self.provider(root, count)
            owner.store.set_match_state([source_key(str(i)) for i in range(count)], 'unmatched')
            snapshot = owner.store.resolve_selection(mode='all-filtered', filters={'review_view': 'unmatched'}, bulk=True)
            self.assertEqual(len(set(snapshot['source_keys'])), count)
            store = AIJobStore(root)
            job = store.create('F5', selection(), {'bulk_call_budget': 251, 'selection_snapshot': snapshot}, 'scale')
            sent = set()
            sizes = []
            def respond(rows):
                sizes.append(len(rows))
                self.assertTrue(sent.isdisjoint(row['id'] for row in rows))
                sent.update(row['id'] for row in rows)
                return reply([model_row(row) for row in rows])
            finished = self.runner(owner, store, respond).run(job['id'])
            self.assertEqual(finished['state'], 'completed', finished['message'])
            self.assertEqual((finished['run_calls'], finished['accepted_count']), (251, count))
            self.assertEqual(finished['cursor']['bulk_counts']['categorized'], count)
            self.assertEqual(sizes, [100] * 250 + [1])

    def test_restart_uses_saved_interpretation_before_any_new_inference(self):
        class SimulatedExit(BaseException):
            pass

        with tempfile.TemporaryDirectory(dir=os.environ['CP_TEST_ROOT']) as root:
            owner = self.provider(root, 1)
            store = AIJobStore(root)
            job = self.launch(owner, store, 1, 1)
            original = owner.bulk_source_proposal
            def interrupt(*args, **kwargs):
                if kwargs.get('interpreted'):
                    raise SimulatedExit()
                return original(*args, **kwargs)
            owner.bulk_source_proposal = interrupt
            with self.assertRaises(SimulatedExit):
                self.runner(owner, store, lambda rows: reply([model_row(rows[0])])).run(job['id'])
            owner.bulk_source_proposal = original
            reopened = AIJobStore(root, process_alive=lambda _: False)
            status = reopened.snapshot(job['id'])
            self.assertEqual((status['state'], status['run_calls'], status['accepted_count']), ('interrupted', 1, 0))
            reopened.continue_job(job['id'], status['revision'], 'resume')
            reopened.process_alive = lambda _: True
            finished = self.runner(owner, reopened, lambda _: self.fail('Repeated a recorded interpretation')).run(job['id'])
            self.assertEqual((finished['state'], finished['accepted_count'], finished['run_calls']), ('completed', 1, 1))

    def test_throttling_retries_and_plan_exhaustion_preserves_remaining_budget(self):
        with tempfile.TemporaryDirectory(dir=os.environ['CP_TEST_ROOT']) as root:
            owner = self.provider(root, 1)
            store = AIJobStore(root)
            job = self.launch(owner, store, 1, 4)
            seen = []
            def respond(rows):
                seen.append(rows)
                if len(seen) == 1:
                    raise ChatGPTError('rate_limit_exceeded', status=429, retry_after=.1)
                if len(seen) == 2:
                    self.assertEqual(store.snapshot(job['id'])['progress_phase'], 'backoff')
                    raise ChatGPTError('subscription_sharing_usage_limit_exceeded', status=429)
                return reply([model_row(rows[0])])
            runner = self.runner(owner, store, respond)
            paused = runner.run(job['id'])
            self.assertEqual((paused['state'], paused['run_calls'], paused['inference_budget']), ('paused', 2, 4))
            self.assertIn('plan usage exhausted', paused['message'])
            store.continue_job(job['id'], paused['revision'], 'resume')
            finished = runner.run(job['id'])
            self.assertEqual((finished['state'], finished['run_calls'], finished['inference_budget']), ('completed', 3, 4))
            self.assertEqual(seen, [seen[0]] * 3)

    def test_duplicate_foreign_and_invalid_unicode_rows_do_not_discard_valid_results(self):
        with tempfile.TemporaryDirectory(dir=os.environ['CP_TEST_ROOT']) as root:
            owner = self.provider(root, 5)
            store = AIJobStore(root)
            job = self.launch(owner, store, 5, 3)
            sent = []
            def respond(rows):
                sent.append([row['id'] for row in rows])
                if len(sent) != 1:
                    return reply([])
                return reply([model_row(rows[0]), model_row(rows[1]), model_row(rows[1]),
                              model_row(rows[2], title='\ud800'), model_row(rows[3], imdb_id='tt123'),
                              model_row(rows[4], id='999'), model_row(rows[4], uncertain=True)])
            finished = self.runner(owner, store, respond).run(job['id'])
            self.assertEqual(finished['state'], 'completed')
            self.assertEqual(sent, [['0', '1', '2', '3', '4'], ['1', '2', '3'], ['1', '2', '3']])
            self.assertEqual(finished['cursor']['bulk_counts'],
                {'verified': 0, 'unmatched': 0, 'categorized': 1, 'review': 1, 'failed': 3})

    def test_projection_blocks_stale_bulk_apply_before_new_generation_is_published(self):
        with tempfile.TemporaryDirectory(dir=os.environ['CP_TEST_ROOT']) as root:
            owner = self.provider(root, 1)
            store = AIJobStore(root)
            job = self.launch(owner, store, 1, 1)
            done = self.runner(owner, store, lambda rows: reply([model_row(rows[0])])).run(job['id'])
            generation = owner.store.source_generation()
            self.assertTrue(owner.store.begin_projection(generation + 1, 1))
            self.assertEqual(owner.store.source_generation(), generation)
            with self.assertRaisesRegex(ValueError, 'catalog changed'):
                owner.apply_bulk_proposals(done['results'], 'classification', generation)
            self.assertEqual(owner.store.source(source_key('0'))['category'], 'unclassified')

    def test_provider_id_and_bulk_categories_preserve_manual_locks_and_play_identity(self):
        with tempfile.TemporaryDirectory(dir=os.environ['CP_TEST_ROOT']) as root:
            owner = self.provider(root, 6, titles=[
                'Fixture Movie (2024)', 'Unknown specimen A', 'Unknown specimen B',
                'Unknown specimen C', 'Unknown specimen D', 'Unknown specimen E'],
                client=lambda: FakeTMDBClient(movies={550: tmdb_payload(),
                    781869: tmdb_payload(781869, 'Unknown specimen C', 1980)}))
            keys = [source_key(str(i)) for i in range(6)]
            generation = owner.store.source_generation()
            with owner.store.connection(immediate=True) as connection:
                connection.execute('UPDATE movie_sources SET provider_tmdb_id=550 WHERE source_key=?', (keys[0],))
            owner.store.set_match_state([keys[5]], 'unmatched', manual_lock=True)
            owner.store.apply_classification_decisions([{'source_key': keys[4], 'category': 'music', 'confidence': 1}],
                                                       manual=True)
            store = AIJobStore(root)
            job = self.launch(owner, store, 6, 1)
            def respond(rows):
                self.assertEqual([row['id'] for row in rows], ['1', '2', '3'])
                self.assertTrue(all(set(row) <= {'id', 'title', 'playlist', 'year'} for row in rows))
                return reply([model_row(row, category=category) for row, category in zip(rows, ('Sports', 'Music', 'Plays'))])
            done = self.runner(owner, store, respond).run(job['id'])
            self.assertEqual(done['state'], 'completed')
            rows = {row['source_key']: row for row in done['results']}
            self.assertEqual([rows[key]['outcome'] for key in keys],
                ['verified', 'categorized', 'categorized', 'categorized', 'categorized', 'review'])
            self.assertEqual(rows[keys[0]]['candidate_tmdb_id'], 550)
            self.assertTrue(rows[keys[0]]['evidence']['provider_id_validated'])
            self.assertTrue(all(not rows[key]['candidate_tmdb_id'] for key in keys[1:]))
            self.assertEqual(owner.store.source(keys[0])['category'], 'unclassified')
            self.assertEqual(owner.apply_bulk_proposals([rows[keys[0]]], 'match', generation)['applied'], [keys[0]])
            self.assertEqual(owner.store.movie('source:' + keys[0])['tmdb_id'], 550)
            classification = owner.apply_bulk_proposals([rows[key] for key in keys[1:]], 'classification', generation)
            self.assertEqual(classification['applied'], keys[1:4])
            self.assertEqual(classification['skipped'], keys[4:])
            self.assertEqual(owner.store.source(keys[4])['category'], 'music')
            for key in keys[1:3]:
                with self.assertRaisesRegex(ValueError, 'provider metadata'):
                    owner.manual_search('source:' + key)
            play_key = 'source:' + keys[3]
            self.assertEqual(owner.manual_search(play_key, tmdb_id='781869')['items'][0]['tmdb_id'], 781869)
            self.assertEqual(owner.manual_match(play_key, 781869), play_key)
            self.assertEqual((owner.store.movie(play_key)['category'], owner.store.movie(play_key)['tmdb_id']),
                             ('plays', 781869))
