import json
import os
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from services.ai_jobs import AIJobError, AIJobService, AIJobStore
from services.chatgpt_iptv import IPTVJob
from services.ai_provider import AIProviderError
from services.chatgpt_skills import IPTV_RECOVERY_INSTRUCTIONS, IPTV_RECOVERY_PROTOCOL_HASH
from services.chatgpt_transport import ChatGPTError, ChatGPTTransport
from services.iptv_movie_store import source_key
from tests import test_iptv_chatgpt_bulk as bulk_fixtures
from tests.iptv_movie_fixtures import FakeTMDBClient, tmdb_payload


def nomination(identity, candidate_id=550):
    return {'id': str(identity), 'decision': 'match', 'candidate_id': candidate_id,
            'confidence': .99, 'evidence_fields': ['title', 'duration', 'director'], 'reason': 'Facts agree.'}


class RecoveryTests(unittest.TestCase):
    def auto_job(self, root, *, easy=False, count=1, budget=5, recovery=True):
        titles = ['Fixture Movie (2024)'] if easy else ['Crystal River (2024)'] * count
        fixture = tmdb_payload() if easy else tmdb_payload(550, 'Crystal River')
        owner = bulk_fixtures.BulkContracts.provider(self, root, len(titles), titles=titles,
            client=lambda: FakeTMDBClient(movies={550: fixture}))
        keys = [source_key(str(i)) for i in range(len(titles))]
        if not easy:
            for key in keys:
                owner.store.update_provider_detail(key, {'duration': '01:41:00', 'director': 'Director One',
                                                        'cast_names': 'Actor One'})
        store = AIJobStore(root)
        request = {'bulk_call_budget': budget, 'bulk_auto_apply': True,
            'selection_snapshot': {'source_keys': keys, 'catalog_generation': owner.store.source_generation()}}
        if recovery:
            request['bulk_recovery_protocol_hash'] = IPTV_RECOVERY_PROTOCOL_HASH
        job = store.create('F5', bulk_fixtures.selection(), request, 'auto')
        return owner, store, job, keys

    def runner(self, owner, store, recover, *, before_reserve=lambda: None, before_first=lambda: None,
               binding=lambda _: None, first_pass_valid=True):
        def factory(_selection, identity):
            def run(_selection, *, input_items, instructions, admit_request=None, reserve_request=None, **_kwargs):
                rows = json.loads(input_items[0]['content'])['rows']
                if instructions == IPTV_RECOVERY_INSTRUCTIONS:
                    before_reserve()
                    reserve_request()
                    answers = recover(rows)
                else:
                    before_first()
                    admit_request()
                    store.reserve_inference(identity)
                    answers = [bulk_fixtures.model_row(row, category='Film', uncertain=True)
                               for row in rows] if first_pass_valid else []
                return bulk_fixtures.reply(answers)
            return SimpleNamespace(run=run)
        return IPTVJob(store, lambda _: owner, factory, check_bulk_binding=binding)

    def test_first_pass_only_job_rejects_binding_change_at_admission(self):
        with tempfile.TemporaryDirectory(dir=os.environ['CP_TEST_ROOT']) as root:
            owner, store, job, _ = self.auto_job(root, recovery=False)
            changed = False
            def change():
                nonlocal changed
                changed = True
            def binding(_selection):
                if changed:
                    raise AIProviderError('bulk_configuration_changed')
            done = self.runner(owner, store, lambda _: self.fail('Unexpected recovery'),
                               before_first=change, binding=binding).run(job['id'])
            self.assertEqual((done['state'], done['run_calls'], done['message']),
                             ('failed', 0, 'bulk_configuration_changed'))

    def test_first_pass_only_job_leaves_uncertain_film_in_review(self):
        with tempfile.TemporaryDirectory(dir=os.environ['CP_TEST_ROOT']) as root:
            owner, store, job, _ = self.auto_job(root, recovery=False)
            done = self.runner(owner, store, lambda _: self.fail('Unexpected recovery')).run(job['id'])
            self.assertEqual((done['state'], done['run_calls']), ('completed', 1))
            self.assertEqual(done['results'][0]['outcome'], 'review')
            self.assertNotIn('recovery', done['cursor']['bulk_work'])
            self.assertEqual(done['cursor']['bulk_work']['first_pass_resolved'], 1)

    def test_restart_settles_admitted_request_and_never_resends_it(self):
        class ProcessStopped(BaseException):
            pass

        for crash_after_response in (False, True):
            with self.subTest(crash_after_response=crash_after_response), tempfile.TemporaryDirectory(
                    dir=os.environ['CP_TEST_ROOT']) as root:
                owner, store, job, _ = self.auto_job(root)
                original_add = store.add_results
                def stop_after_save(*args, **kwargs):
                    result = original_add(*args, **kwargs)
                    if kwargs.get('bulk_work', {}).get('recovery', {}).get('decisions'):
                        raise ProcessStopped()
                    return result
                def recover(rows):
                    if not crash_after_response:
                        raise ProcessStopped()
                    return [nomination(rows[0]['id'])]
                with patch.object(store, 'add_results', side_effect=stop_after_save):
                    with self.assertRaises(ProcessStopped):
                        self.runner(owner, store, recover).run(job['id'])
                with patch.object(store, 'process_alive', return_value=False):
                    saved = store.snapshot(job['id'])
                    self.assertEqual(saved['state'], 'interrupted')
                    self.assertEqual(saved['cursor']['bulk_work']['recovery']['admitted'], 1)
                    store.continue_job(job['id'], saved['revision'], 'resume')
                runner = self.runner(owner, store, lambda _: self.fail('Recovery resent an admitted source'))
                done = runner.run(job['id'])
                self.assertEqual((done['state'], done['run_calls'], done['accepted_count']), ('completed', 2, 1))
                row = done['results'][0]
                if crash_after_response:
                    self.assertEqual(row['apply_state'], 'applied')
                else:
                    self.assertEqual(row['evidence']['recovery']['reason'], 'recovery_interrupted')

    def test_recovery_pause_before_admission_preserves_attempt(self):
        with tempfile.TemporaryDirectory(dir=os.environ['CP_TEST_ROOT']) as root:
            owner, store, job, _ = self.auto_job(root)
            def pause():
                store.request_bulk_pause(job['id'], 0)
            paused = self.runner(owner, store, lambda _: self.fail('Paused request went out'), before_reserve=pause).run(job['id'])
            self.assertEqual((paused['state'], paused['run_calls']), ('paused', 1))
            self.assertEqual(paused['cursor']['bulk_work']['recovery']['admitted'], 0)
            store.continue_job(job['id'], paused['revision'], 'resume')
            done = self.runner(owner, store, lambda rows: [nomination(rows[0]['id'])]).run(job['id'])
            self.assertEqual((done['state'], done['run_calls'], done['results'][0]['apply_state']), ('completed', 2, 'applied'))

    def test_cancel_after_recovery_admission_records_interruption(self):
        with tempfile.TemporaryDirectory(dir=os.environ['CP_TEST_ROOT']) as root:
            owner, store, job, _ = self.auto_job(root)
            def cancel(rows):
                store.cancel(job['id'], job['revision'], run_number=0)
                return [nomination(rows[0]['id'])]
            self.runner(owner, store, cancel).run(job['id'])
            saved = store.snapshot(job['id'])
            self.assertEqual((saved['state'], saved['run_calls']), ('cancelled', 2))
            self.assertEqual(saved['results'][0]['evidence']['recovery']['reason'], 'recovery_interrupted')
            self.assertEqual(saved['cursor']['bulk_work']['recovery']['in_flight'], [])

    def test_first_pass_does_not_send_a_newly_locked_source(self):
        with tempfile.TemporaryDirectory(dir=os.environ['CP_TEST_ROOT']) as root:
            owner, store, job, keys = self.auto_job(root)
            def lock():
                with owner.store.connection(immediate=True) as connection:
                    connection.execute('UPDATE source_matches SET manual_lock=1 WHERE source_key=?', keys)
            done = self.runner(owner, store, lambda _: self.fail('Locked source reached recovery'),
                               before_first=lock).run(job['id'])
            self.assertEqual((done['state'], done['run_calls']), ('completed', 0))
            self.assertIn('Manual match lock', done['results'][0]['review_reason'])

    def test_configuration_change_stops_recovery_admission(self):
        with tempfile.TemporaryDirectory(dir=os.environ['CP_TEST_ROOT']) as root:
            owner, store, job, _ = self.auto_job(root)
            changed = False
            def change():
                nonlocal changed
                changed = True
            def binding(_selection):
                if changed:
                    raise AIProviderError('bulk_configuration_changed')
            done = self.runner(owner, store, lambda _: self.fail('Changed configuration admitted recovery'),
                               before_reserve=change, binding=binding).run(job['id'])
            self.assertEqual((done['state'], done['run_calls'], done['message']),
                             ('failed', 1, 'bulk_configuration_changed'))
            self.assertEqual(done['cursor']['bulk_work']['recovery']['admitted'], 0)

    def test_explicit_budget_and_plan_usage_are_distinct(self):
        for budget, state in ((1, 'paused_budget'), (2, 'paused')):
            with self.subTest(budget=budget), tempfile.TemporaryDirectory(dir=os.environ['CP_TEST_ROOT']) as root:
                owner, store, job, _ = self.auto_job(root, budget=budget)
                def usage(_rows):
                    raise ChatGPTError('usage_limit_reached', status=429)
                paused = self.runner(owner, store, usage).run(job['id'])
                self.assertEqual((paused['state'], paused['run_calls']), (state, budget))
                self.assertEqual(paused['cursor']['bulk_work']['recovery']['requests'], budget - 1)
                if budget == 2:
                    self.assertIn('plan usage exhausted', paused['message'])
                    store.continue_job(job['id'], paused['revision'], 'resume')
                    done = self.runner(owner, store, lambda _: self.fail('Usage-limited source was resent')).run(job['id'])
                    self.assertEqual(done['state'], 'completed')

    def test_partial_recovery_checkpoint_replaces_each_source_once(self):
        with tempfile.TemporaryDirectory(dir=os.environ['CP_TEST_ROOT']) as root:
            owner, store, job, _ = self.auto_job(root, count=2)
            done = self.runner(owner, store, lambda rows: [nomination(rows[0]['id'])]).run(job['id'])
            self.assertEqual((done['state'], done['run_calls'], done['accepted_count']), ('completed', 2, 2))
            self.assertEqual(done['cursor']['bulk_counts']['review'], 0)
            self.assertEqual(done['results'][0]['apply_state'], 'applied')
            self.assertEqual(done['results'][1]['evidence']['recovery']['reason'], 'recovery_invalid_response')

    def test_film_context_can_recover_after_bounded_first_pass_repairs(self):
        with tempfile.TemporaryDirectory(dir=os.environ['CP_TEST_ROOT']) as root:
            owner, store, job, _ = self.auto_job(root)
            done = self.runner(owner, store, lambda rows: [nomination(rows[0]['id'])],
                               first_pass_valid=False).run(job['id'])
            self.assertEqual((done['state'], done['run_calls']), ('completed', 4))
            row = done['results'][0]
            self.assertEqual(row['evidence']['recovery']['first_pass']['outcome'], 'failed')
            self.assertEqual(row['apply_state'], 'applied')

    def test_provider_change_after_response_prevents_apply_and_settles_attempt(self):
        with tempfile.TemporaryDirectory(dir=os.environ['CP_TEST_ROOT']) as root:
            owner, store, job, _ = self.auto_job(root)
            changed = False
            def recover(rows):
                nonlocal changed
                changed = True
                return [nomination(rows[0]['id'])]
            with patch.object(owner.store, 'bulk_selection_current', side_effect=lambda _: not changed):
                done = self.runner(owner, store, recover).run(job['id'])
            self.assertEqual((done['state'], done['message'], done['run_calls']), ('failed', 'iptv_selection_changed', 2))
            self.assertEqual(done['results'][0]['evidence']['recovery']['reason'], 'recovery_source_changed')

    def test_official_alias_cannot_erase_a_canonical_sequel_number(self):
        from services.iptv_tmdb import recovery_candidate_facts, verify_recovery_candidate

        movie = tmdb_payload(550, 'Cars 3', 2017)
        movie['alternative_titles'] = {'titles': [{'title': 'Cars'}]}
        provider = {'title': 'Cars (2017)', 'year': 2017, 'playlist': '', 'detail_title': 'Cars',
                    'detail_year': 2017, 'duration': '01:41:00', 'cast': 'Actor One',
                    'director': 'Director One', 'plot': movie['overview']}
        self.assertEqual(verify_recovery_candidate(provider, [recovery_candidate_facts(movie)], 550)['reason'],
                         'recovery_title_or_installment_conflict')

    def test_added_part_number_requires_exact_subtitle_and_collection_order(self):
        from services.iptv_tmdb import bounded_search_candidates, combine_provider_title_evidence
        from services.iptv_tmdb import interpreted_title_evidence, recovery_candidate_facts, verify_recovery_candidate

        provider = {'title': 'Rendel 2: Cycle of Revenge (2024)', 'year': 2024, 'playlist': '',
                    'detail_title': '', 'detail_year': 0, 'duration': '01:41:00', 'cast': 'Actor One',
                    'director': 'Director One', 'plot': ''}
        movie = tmdb_payload(551, 'Rendel: Cycle of Revenge')
        client = FakeTMDBClient(movies={551: movie}, search_results=[movie])
        client.collection = lambda _: {'parts': [tmdb_payload(550, 'Rendel', 2017), movie]}
        parsed = interpreted_title_evidence(combine_provider_title_evidence(provider['title'], 2024), {})
        candidates, _ = bounded_search_candidates(client, parsed, strict_bounds=True)
        with_proof = recovery_candidate_facts(candidates[0])
        self.assertTrue(verify_recovery_candidate(provider, [with_proof], 551)['verified'])
        self.assertFalse(verify_recovery_candidate(provider, [recovery_candidate_facts(movie)], 551)['verified'])
        wrong = {**provider, 'title': 'Rendel 3: Cycle of Revenge (2024)'}
        self.assertFalse(verify_recovery_candidate(wrong, [with_proof], 551)['verified'])

    def test_bounded_search_marks_a_discarded_same_title_rival(self):
        from services.iptv_tmdb import bounded_search_candidates, interpreted_title_evidence, parse_provider_title

        entries = [tmdb_payload(550)] + [tmdb_payload(i, 'Other ' + str(i)) for i in range(551, 555)]
        entries.append(tmdb_payload(555))
        client = FakeTMDBClient(movies={m['id']: m for m in entries}, search_results=entries)
        parsed = interpreted_title_evidence(parse_provider_title('Fixture Movie (2024)'), {})
        # Use the same parsed structure as the service's combined evidence.
        candidates, _ = bounded_search_candidates(client, parsed, strict_bounds=True)
        self.assertNotIn(555, {candidate['id'] for candidate in candidates})
        self.assertTrue(all(candidate.get('bulk_search_limited') for candidate in candidates))

    def test_apply_crash_reconciles_one_provider_receipt_on_resume_or_cancel(self):
        for cancel in (False, True):
            with self.subTest(cancel=cancel), tempfile.TemporaryDirectory(dir=os.environ['CP_TEST_ROOT']) as root:
                owner, store, job, keys = self.auto_job(root, easy=True)
                runner = self.runner(owner, store, lambda _: self.fail('Local source used recovery'))
                original = store.checkpoint_bulk_apply
                def fail_after_provider_commit(*args, **kwargs):
                    if len(args) >= 3 and args[2]:
                        raise RuntimeError('simulated crash after provider commit')
                    return original(*args, **kwargs)
                with patch.object(store, 'checkpoint_bulk_apply', side_effect=fail_after_provider_commit):
                    stopped = runner.run(job['id'])
                self.assertEqual((stopped['state'], stopped['run_calls']), ('interrupted', 0))
                apply_id = stopped['bulk_apply']['id']
                if cancel:
                    service = AIJobService(store, reconcile_bulk_cancel=runner.reconcile_cancelled_bulk)
                    done = service.cancel(job['id'], stopped['revision'])
                    self.assertEqual(done['state'], 'cancelled')
                else:
                    store.continue_job(job['id'], stopped['revision'], 'resume')
                    done = runner.run(job['id'])
                    self.assertEqual(done['state'], 'completed')
                self.assertEqual((done['bulk_apply']['id'], done['results'][0]['apply_state']), (apply_id, 'applied'))
                with owner.store.bulk_match_receipts(keys, apply_id) as receipts:
                    self.assertEqual(receipts, set(keys))
                with owner.store.connection() as connection:
                    self.assertEqual(connection.execute("SELECT count(*) FROM decision_audit WHERE domain='bulk-match'").fetchone()[0], 1)
                    self.assertEqual(tuple(connection.execute("SELECT manual_lock,state FROM source_matches").fetchone()),
                                     (0, 'matched-auto'))

    def test_resume_completes_apply_after_last_receipt_was_saved(self):
        with tempfile.TemporaryDirectory(dir=os.environ['CP_TEST_ROOT']) as root:
            owner, store, job, _ = self.auto_job(root, easy=True)
            runner = self.runner(owner, store, lambda _: self.fail('Local source used recovery'))
            original = store.checkpoint_bulk_apply
            def fail_on_finish(*args, **kwargs):
                if kwargs.get('state') == 'completed':
                    raise RuntimeError('simulated crash after last receipt')
                return original(*args, **kwargs)
            with patch.object(store, 'checkpoint_bulk_apply', side_effect=fail_on_finish):
                stopped = runner.run(job['id'])
            self.assertEqual((stopped['state'], stopped['cursor']['bulk_automatic_pending']), ('interrupted', 0))
            store.continue_job(job['id'], stopped['revision'], 'resume')
            done = runner.run(job['id'])
            self.assertEqual((done['state'], done['bulk_apply']['state']), ('completed', 'completed'))
            self.assertEqual(done['bulk_apply']['id'], stopped['bulk_apply']['id'])

    def test_apply_uses_source_revision_and_preserves_manual_lock(self):
        for lock in (False, True):
            with self.subTest(lock=lock), tempfile.TemporaryDirectory(dir=os.environ['CP_TEST_ROOT']) as root:
                owner, store, job, keys = self.auto_job(root, easy=True)
                original = owner.apply_bulk_proposals
                def change(*args, **kwargs):
                    if lock:
                        with owner.store.connection(immediate=True) as connection:
                            connection.execute('UPDATE source_matches SET manual_lock=1 WHERE source_key=?', keys)
                    else:
                        owner.store.update_provider_detail(keys[0], {'duration': '04:30:00'})
                    return original(*args, **kwargs)
                with patch.object(owner, 'apply_bulk_proposals', side_effect=change):
                    done = self.runner(owner, store, lambda _: self.fail('Unexpected inference')).run(job['id'])
                self.assertEqual((done['state'], done['run_calls']), ('completed', 0))
                self.assertEqual(done['results'][0]['apply_state'], 'locked' if lock else 'skipped')

    def test_parser_accepts_only_unique_valid_rows_and_supplied_candidates(self):
        from services.chatgpt_iptv import _recovery_decisions

        rows = [nomination(0), nomination(1, 999), nomination(2), nomination(2), nomination(3),
                {**nomination(4), 'evidence_fields': ['override']},
                {**nomination(5), 'candidate_id': True}, {**nomination(6), 'decision': 'no_candidate'}]
        allowed = {str(i): {550} for i in range(7)}
        self.assertEqual(_recovery_decisions(json.dumps({'rows': rows}), allowed),
                         {'0': rows[0], '3': rows[4]})
        self.assertEqual(_recovery_decisions('{"rows":[],"rows":[]}', allowed), {})
        self.assertEqual(_recovery_decisions('{"rows":[', allowed), {})

    def test_pilot_identity_and_mixed_metadata_guards(self):
        from services.iptv_tmdb import verify_recovery_candidate

        fixture = json.loads(Path(__file__).with_name('fixtures').joinpath('iptv_recovery_pilot.json').read_bytes())
        required = {'1', '8', '9', '13', '14', '15', '16', '18', '19', '24'}
        cautious = {row['id'] for row in fixture if row['expected_decision'] == 'review'}
        for row in fixture:
            candidates = row['candidates']
            for identity in [candidate['candidate_id'] for candidate in candidates]:
                with self.subTest(row=row['id'], candidate=identity):
                    facts = verify_recovery_candidate(row['provider'], candidates, identity,
                                                      search_limited=row['search_limit_reached'])
                    if row['id'] in cautious or identity != row['supported_candidate_id']:
                        self.assertFalse(facts['verified'], facts)
                    elif row['id'] in required:
                        self.assertTrue(facts['verified'], facts)

    def test_auto_job_recovery_updates_one_result_and_applies_with_receipt(self):
        with tempfile.TemporaryDirectory(dir=os.environ['CP_TEST_ROOT']) as root:
            owner = bulk_fixtures.BulkContracts.provider(self, root, 2,
                titles=['Fixture Movie (2024)', 'Crystal River (2024)'],
                client=lambda: FakeTMDBClient(movies={550: tmdb_payload(), 551: tmdb_payload(551, 'Crystal River')},
                    search_results=[tmdb_payload(), tmdb_payload(551, 'Crystal River')]))
            store = AIJobStore(root)
            easy, remaining = source_key('0'), source_key('1')
            owner.store.update_provider_detail(remaining, {'duration': '01:41:00', 'director': 'Director One',
                'cast_names': 'Actor One', 'plot': 'https://example.invalid/hidden?password=hidden'})
            with owner.store.connection(immediate=True) as connection:
                connection.execute("UPDATE source_classifications SET category='unclassified',confidence=0 "
                                   "WHERE source_key=?", (remaining,))
            generation = owner.store.source_generation()
            job = store.create('F5', bulk_fixtures.selection(), {'bulk_call_budget': 5,
                'bulk_recovery_protocol_hash': IPTV_RECOVERY_PROTOCOL_HASH, 'bulk_auto_apply': True,
                'selection_snapshot': {'source_keys': [easy, remaining], 'catalog_generation': generation}}, 'auto')
            requests = []

            def stream(_url, *, payload, **_kwargs):
                requests.append(payload)
                content = payload['input'][0]['content']
                self.assertNotIn('example.invalid', content)
                rows = json.loads(content)['rows']
                if len(requests) == 1:
                    answers = [bulk_fixtures.model_row(row, category='Film', year='2024', uncertain=True) for row in rows]
                else:
                    self.assertEqual([row['id'] for row in rows], ['1'])
                    self.assertEqual(rows[0]['candidates'][0]['candidate_id'], 551)
                    answers = [nomination(1, 551)]
                terminal = {'type': 'response.completed', 'response': {'status': 'completed',
                    'id': 'fixture', 'output': [{'type': 'message', 'content': [
                        {'type': 'output_text', 'text': json.dumps({'rows': answers})}]}]}}
                return iter([('data: ' + json.dumps(terminal) + '\n\n').encode()])

            def factory(_selection, identity):
                return ChatGPTTransport(lambda _: 'fixture', http=SimpleNamespace(stream=stream),
                    before_request=lambda: store.reserve_inference(identity), max_retries=0)

            done = IPTVJob(store, lambda _: owner, factory).run(job['id'])
            self.assertEqual((done['state'], done['message'], done['accepted_count'], done['run_calls']),
                             ('completed', '', 2, 2))
            self.assertEqual(len(requests), 2)
            self.assertEqual(store.snapshot(job['id'], review_view='applied')['review_counts']['applied'], 2)
            by_key = {row['source_key']: row for row in done['results']}
            self.assertEqual(by_key[remaining]['evidence']['recovery']['decision']['candidate_id'], 551)
            self.assertEqual(by_key[easy]['apply_state'], 'applied')
            self.assertEqual(owner.store.source(remaining)['category'], 'film')
