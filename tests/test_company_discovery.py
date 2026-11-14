import unittest
from services.advanced_search import normalize_query, AdvancedSearchValidationError
from services.tmdb_advanced_search import build_discover_plan


def studio_query():
    return {'version': 1, 'scope': 'discover', 'mode': 'advanced', 'feed': 'catalog',
            'sort': {'key': 'primary_release_date.asc', 'direction': 'asc'}, 'groups': [
                {'type': 'company', 'join': 'and', 'values': [
                    {'id': '10', 'label': 'Fixture Studios', 'country': 'US'},
                    {'id': '20', 'label': 'Other Studios', 'country': 'GB'},
                    {'id': '30', 'label': 'Excluded Studio', 'country': 'US', 'exclude': True}]}]}


class CompanyTests(unittest.TestCase):
    def test_controlled_company_and_or_exclusion_compile_in_existing_owner(self):
        query = studio_query()
        normalized = normalize_query(query, 'discover')
        plan = build_discover_plan(normalized)
        self.assertEqual(plan.provider_params['with_companies'], '10,20')
        self.assertEqual(plan.provider_params['without_companies'], '30')
        query['groups'][0]['join'] = 'or'
        self.assertEqual(build_discover_plan(query).provider_params['with_companies'], '10|20')

    def test_company_ids_country_and_contradictions_are_not_free_text_shortcuts(self):
        for change in [{'id': 'not-an-id'}, {'country': 'invented'}, {'exclude': 'yes'}]:
            query = studio_query()
            query['groups'][0]['values'][0].update(change)
            with self.assertRaises(AdvancedSearchValidationError):
                build_discover_plan(query)

