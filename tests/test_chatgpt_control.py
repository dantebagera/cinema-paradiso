from dataclasses import replace
import os
import tempfile
import unittest
from services import ai_control
from services.ai_catalog import ResultSet
from services.curation_store import UserCurationStore


class ResolvedPlanTests(unittest.TestCase):
    def test_late_stale_delete_target_blocks_all_removals_before_first_effect(self):
        from pathlib import Path
        with tempfile.TemporaryDirectory(dir=os.environ['CP_TEST_ROOT']) as root:
            first, second = Path(root) / 'first.mkv', Path(root) / 'second.mkv'
            first.write_bytes(b'first')
            second.write_bytes(b'second')
            plans = ai_control.PlanStore()
            plan = plans.put({'action': 'delete', 'items': [{'path': str(path), 'observed_size': path.stat().st_size,
                'selection_key': 'item-' + str(index)} for index, path in enumerate((first, second), 1)]})
            second.write_bytes(b'changed after preview')
            removed = []
            result = ai_control.execute_plan(plan['plan_id'], plan_store=plans, library_roots=[root],
                                            delete_file=lambda path: removed.append(path))
            self.assertEqual(result['state'], 'unsafe')
            self.assertEqual(removed, [])

    def result(self, **changes):
        result = ResultSet('set-a', 'query-hash', tuple({'tmdb_id': str(i), 'title': 'Movie ' + str(i), 'year': '2001'}
            for i in range(1, 121)), 'complete', None, 6, 6, 120, 0, 0, None)
        return replace(result, **changes)

    def test_resolved_full_set_uses_existing_selection_and_persists_only_confirmed_subset(self):
        plans = ai_control.PlanStore()
        plan = ai_control.prepare_resolved('create_list', result_set=self.result(), list_name='Fixture Studio',
            plan_store=plans, provenance={'provider': 'chatgpt', 'model': 'fixture'})
        self.assertEqual(len(plan['items']), 120)
        self.assertEqual(plan['items'][-1]['selection_key'], 'item-120')
        with tempfile.TemporaryDirectory(dir=os.environ['CP_TEST_ROOT']) as root:
            store = UserCurationStore(root)
            before_count = len(store.list_all())  # Includes CP's system lists.
            outcome = ai_control.execute_plan(plan['plan_id'], plan_store=plans,
                selected_keys=['item-2', 'item-120'], create_list=lambda name, movies: store.create_list(name, movies=movies))
            self.assertEqual(outcome['state'], 'executed')
            saved = [item for item in store.list_all() if item['id'] == outcome['created']['id']]
            self.assertEqual(len(saved), 1)
            self.assertEqual(len(store.list_all()), before_count + 1)
            self.assertEqual({movie['tmdb_id'] for movie in saved[0]['movies']}, {'2', '120'})
            duplicate = ai_control.execute_plan(plan['plan_id'], plan_store=plans,
                create_list=lambda *args: self.fail('One-shot confirmation was replayed'))
            self.assertEqual(duplicate['state'], 'unsafe')

    def test_partial_and_wrong_domain_cannot_become_all_mutation_plans(self):
        for result in [self.result(coverage='partial', reason='provider_page_failed'), self.result(domain='tv')]:
            plan = ai_control.prepare_resolved('create_list', result_set=result, list_name='Wrong',
                plan_store=ai_control.PlanStore(), provenance={'provider': 'chatgpt'})
            self.assertNotEqual(plan['state'], 'valid_plan')
            self.assertFalse(plan.get('plan_id'))  # Legacy state envelopes carry an empty ID.
