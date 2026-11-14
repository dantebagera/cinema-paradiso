import hashlib
import unittest
from services.chatgpt_skills import load, validate_schema


class SkillTests(unittest.TestCase):
    def test_bulk_prompt_is_the_approved_100_title_benchmark_prompt(self):
        from services.chatgpt_skills import IPTV_BULK_INSTRUCTIONS, IPTV_BULK_PROTOCOL_HASH
        # Pin the exact instructions Dante approved after the real 100-title comparison.
        self.assertEqual(hashlib.sha256(IPTV_BULK_INSTRUCTIONS.encode()).hexdigest(),
                         'a281c1445f51ccbeed985352df62fc8d7a080f3a75523942a0bc6a1185abaee4')
        self.assertEqual(IPTV_BULK_PROTOCOL_HASH,
                         '435ea3756a5d453cd5c3e3041385a856c194b5e732b867fc62f6a7f0f3c7c6ef')

    def test_all_six_resources_have_distinct_pinned_instructions_and_schemas(self):
        rows = [load(feature) for feature in ('F1', 'F2', 'F3', 'F4', 'F5', 'F6')]
        self.assertEqual(len({row['id'] for row in rows}), 6)
        for row in rows:
            self.assertEqual(len(row['hash']), 64)
            self.assertEqual(row['version'], '1')
            self.assertTrue(row['instructions'])
            self.assertNotIn('status: draft', row['instructions'])
            self.assertNotIn('../REVIEW.md', row['instructions'])
        self.assertIn('supplied', rows[2]['instructions'])

    def test_output_schemas_reject_unknown_fields_and_invalid_identity_shapes(self):
        schema = load('F3')['tool_schema']
        valid = {'matches': [{'id': 'one', 'title': 'Synthetic Movie', 'year': '2001', 'alternatives': []}]}
        validate_schema(schema, valid)
        for invalid in [{**valid, 'apply': True}, {'matches': [{'id': 'one', 'title': 'Movie'}]}, {'matches': 'invalid'}]:
            with self.assertRaises(ValueError):
                validate_schema(schema, invalid)
        with self.assertRaises(ValueError):
            validate_schema(load('F5')['tool_schema'], {'tmdb_id': True})

    def test_curator_returns_scope_and_candidates_in_one_initial_result_and_candidates_only_afterwards(self):
        skill = load('F1')
        initial = skill['result_schema']
        later = skill['continuation_schema']
        self.assertIn('scope', initial['required'])
        self.assertNotIn('scope', later['properties'])
        self.assertNotIn('cp_scope', {tool['name'] for tool in skill['tools']})
        self.assertNotIn('cp_result', {tool['name'] for tool in skill['tools']})
        self.assertEqual(set(initial['properties']['recommendations']['items']['properties']), {'title', 'year'})
