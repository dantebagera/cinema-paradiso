import importlib
import unittest
from dataclasses import replace
from tests.test_movie_awards_sources import adapter, oscar, payload, OSCAR_FIELDS


def resolver():
    try:
        return importlib.import_module('services.movie_awards_identity')
    except ModuleNotFoundError:
        raise AssertionError('The approved verified identity owner is not implemented')


class MovieAwardIdentityTests(unittest.TestCase):
    def wins(self):
        return adapter().parse_source('dlu_oscar', payload(OSCAR_FIELDS, [oscar()], '\t'), {})

    def test_correct_domain_mapping_preserves_minimal_facts(self):
        def find(imdb, namespace):
            return {'movie_results': [{'id': 10, 'title': 'Verified film', 'release_date': '1928-01-01'}]} if namespace == 'movie' else {'person_results': [{'id': 20}]}
        result = resolver().resolve_identities(self.wins(), existing_mappings=[], find_by_imdb=find,
                                              search_candidates=lambda ref: [], overrides=[])
        self.assertTrue(result.complete)
        self.assertEqual({m['tmdb_id'] for m in result.mappings}, {10, 20})
        self.assertEqual(next(m for m in result.mappings if m['namespace'] == 'movie')['facts']['title'], 'Verified film')

    def test_tv_result_and_multiple_matches_cannot_resolve_movie(self):
        for response in [{'tv_results': [{'id': 10}]}, {'movie_results': [{'id': 10}, {'id': 11}]}]:
            result = resolver().resolve_identities(self.wins(), existing_mappings=[],
                find_by_imdb=lambda imdb, namespace: response, search_candidates=lambda ref: [], overrides=[])
            self.assertFalse(result.complete)
            self.assertTrue(result.unresolved)

    def test_same_name_is_not_identity_evidence(self):
        wins = adapter().parse_source('dlu_oscar', payload(OSCAR_FIELDS, [oscar(films='?')], '\t'), {})
        result = resolver().resolve_identities(wins, existing_mappings=[], find_by_imdb=lambda *a: {},
            search_candidates=lambda ref: [{'id': 10, 'title': 'First'}], overrides=[])
        self.assertFalse(result.complete)
        self.assertFalse(any(m['namespace'] == 'movie' for m in result.mappings))

    def test_one_to_many_and_many_to_one_mapping_conflicts_block(self):
        mappings = [{'namespace': 'movie', 'imdb_id': 'tt0010101', 'tmdb_id': 10, 'evidence': {'revision': 'a'}},
                    {'namespace': 'movie', 'imdb_id': 'tt0010101', 'tmdb_id': 11, 'evidence': {'revision': 'b'}}]
        result = resolver().resolve_identities(self.wins(), existing_mappings=mappings,
            find_by_imdb=lambda *a: {}, search_candidates=lambda ref: [], overrides=[])
        self.assertFalse(result.complete)
        self.assertTrue(result.conflicts)

    def test_verified_mapping_reused_without_provider_call(self):
        mappings = [{'namespace': 'movie', 'imdb_id': 'tt0010101', 'tmdb_id': 10, 'evidence': {'revision': 'a'}},
                    {'namespace': 'person', 'imdb_id': 'nm0010101', 'tmdb_id': 20, 'evidence': {'revision': 'b'}}]
        def forbidden(*args):
            self.fail('Existing verified identities should not be fetched again')
        result = resolver().resolve_identities(self.wins(), existing_mappings=mappings,
            find_by_imdb=forbidden, search_candidates=forbidden, overrides=[])
        self.assertTrue(result.complete)

    def test_same_alias_for_two_distinct_entities_cannot_choose_last_override(self):
        overrides = [dict(namespace='movie', imdb_id='tt0010101', tmdb_id=10, source_alias='First',
                          source_context={'source': 'dlu_oscar', 'ceremony': 1, 'category': 'ACTOR'},
                          evidence={'source_url': 'https://example.org/one', 'revision': 'one', 'reason': 'verified'}),
                     dict(namespace='movie', imdb_id='tt0010102', tmdb_id=11, source_alias='First',
                          source_context={'source': 'dlu_oscar', 'ceremony': 1, 'category': 'ACTOR'},
                          evidence={'source_url': 'https://example.org/two', 'revision': 'two', 'reason': 'verified'})]
        wins = adapter().parse_source('dlu_oscar', payload(OSCAR_FIELDS, [oscar(films='?')], '\t'), {})
        result = resolver().resolve_identities(wins, existing_mappings=[], find_by_imdb=lambda *a: {},
                                               search_candidates=lambda ref: [], overrides=overrides)
        self.assertFalse(result.complete)
        self.assertTrue(result.conflicts)

    def test_override_alias_is_scoped_to_source_ceremony_and_category(self):
        first = oscar(films='?')
        second = oscar(films='?'); second.update(Ceremony='2', Year='1928/29')
        wins = adapter().parse_source('dlu_oscar', payload(OSCAR_FIELDS, [first, second], '\t'), {})
        override = dict(namespace='movie', imdb_id='tt0010101', tmdb_id=10, source_alias='First',
                        source_context={'source': 'dlu_oscar', 'ceremony': 1, 'category': 'ACTOR'},
                        evidence={'source_url': 'https://example.org/one', 'revision': 'one', 'reason': 'verified'})
        mappings = [dict(namespace='person', imdb_id='nm0010101', tmdb_id=20, evidence={'revision': 'person'})]
        result = resolver().resolve_identities(wins, existing_mappings=mappings,
            find_by_imdb=lambda *a: {}, search_candidates=lambda ref: [], overrides=[override])
        self.assertEqual(result.wins[0].films[0].tmdb_id, 10)
        self.assertIsNone(result.wins[1].films[0].tmdb_id)
        self.assertFalse(result.complete)

    def test_wrong_source_imdb_id_requires_scoped_evidence_backed_correction(self):
        wins = self.wins()
        correction = dict(namespace='movie', imdb_id='tt0084185', tmdb_id=114517, source_alias='First',
                          replaces_source_imdb_id='tt0010101',
                          source_context={'source': 'dlu_oscar', 'ceremony': 1, 'category': 'ACTOR'},
                          evidence={'source_url': 'https://example.org/winner', 'revision': 'verified', 'reason': 'incorrect source IMDb'})
        mappings = [dict(namespace='person', imdb_id='nm0010101', tmdb_id=20, evidence={'revision': 'person'})]
        result = resolver().resolve_identities(wins, existing_mappings=mappings,
            find_by_imdb=lambda *a: {'tv_results': [{'id': 123}]}, search_candidates=lambda ref: [], overrides=[correction])
        self.assertTrue(result.complete)
        self.assertEqual(result.wins[0].films[0].imdb_id, 'tt0084185')
        self.assertEqual(result.wins[0].films[0].tmdb_id, 114517)

    def test_two_imdb_ids_cannot_share_one_tmdb_identity(self):
        mappings = [dict(namespace='movie', imdb_id='tt0010101', tmdb_id=10, evidence={'revision': 'one'}),
                    dict(namespace='movie', imdb_id='tt0010102', tmdb_id=10, evidence={'revision': 'two'})]
        result = resolver().resolve_identities(self.wins(), existing_mappings=mappings,
            find_by_imdb=lambda *a: {}, search_candidates=lambda ref: [], overrides=[])
        self.assertFalse(result.complete)
        self.assertTrue(result.conflicts)



class IndependentWinnerVerificationTests(unittest.TestCase):
    def primary(self):
        win = adapter().parse_source('dlu_oscar', payload(OSCAR_FIELDS, [oscar()], '\t'), {})[0]
        return replace(win, films=(replace(win.films[0], tmdb_id=10),),
                       people=(replace(win.people[0], tmdb_id=20),))

    def independent(self, title='First', person='Person', **context):
        primary = self.primary()
        evidence = {'source': 'annual_wikitext', 'revision': 'independent-pinned',
                    'ceremony': 1, 'category': 'Best Actor', **context}
        return replace(primary, films=(adapter().EntityReference('movie', title, evidence=(evidence,)),),
                       people=(adapter().EntityReference('person', person, evidence=(evidence,)),),
                       evidence=evidence)

    def verify(self, primary=None, independent=None, mappings=()):
        return resolver().crosscheck_ceremony(primary or [self.primary()], independent or [self.independent()],
                                            mappings=mappings)

    def test_exact_winners_match_without_provider_calls_and_preserve_evidence(self):
        report = self.verify()
        self.assertTrue(report.complete)
        self.assertTrue(report.evidence['crosscheck_agrees'])
        self.assertEqual(report.evidence['revision'], 'independent-pinned')

    def test_renamed_display_title_uses_pinned_wiki_target_within_award(self):
        report = self.verify(independent=[self.independent('Displayed alias', wiki_target='First (1928 film)')])
        self.assertTrue(report.complete)

    def test_verified_original_title_and_person_name_support_source_aliases(self):
        mappings = [dict(namespace='movie', imdb_id='tt0010101', tmdb_id=10,
                         facts={'original_title': 'Premier'}, evidence={'revision': 'verified'}),
                    dict(namespace='person', imdb_id='nm0010101', tmdb_id=20,
                         facts={'name': 'Full Person Name'}, evidence={'revision': 'verified'})]
        self.assertTrue(self.verify(independent=[self.independent('Premier', 'Full Person Name')],
                                    mappings=mappings).complete)

    def test_evidence_backed_title_alias_cannot_escape_its_source_context(self):
        mapping = dict(namespace='movie', imdb_id='tt0010101', tmdb_id=10, source_alias='Abbreviated',
                       source_context={'source': 'annual_wikitext', 'ceremony': 1, 'category': 'Best Actor'},
                       evidence={'revision': 'pinned', 'source_url': 'https://example.org/source',
                                 'reason': 'Winner title and eligible-year/credits evidence agree'})
        self.assertTrue(self.verify(independent=[self.independent('Abbreviated')], mappings=[mapping]).complete)
        mapping['source_context']['ceremony'] = 2
        self.assertFalse(self.verify(independent=[self.independent('Abbreviated')], mappings=[mapping]).complete)

    def test_different_recipient_and_ambiguous_same_title_both_block(self):
        self.assertFalse(self.verify(independent=[self.independent(person='Wrong person')]).complete)
        extra = replace(self.primary(), films=(replace(self.primary().films[0], imdb_id='tt0020202', tmdb_id=11),))
        report = self.verify(primary=[self.primary(), extra])
        self.assertFalse(report.complete)
        self.assertIn('ambiguous_independent_identity', report.diagnostics)

    def test_missing_winner_in_one_award_and_same_source_cannot_pass(self):
        extra = replace(self.primary(), award_instance='ACTRESS IN A LEADING ROLE', category='ACTRESS IN A LEADING ROLE')
        self.assertFalse(self.verify(primary=[self.primary(), extra]).complete)
        self.assertFalse(self.verify(independent=[self.primary()]).complete)

    def test_each_category_requires_its_own_independent_origin(self):
        one=replace(self.primary(),evidence={'source':'dlu_oscar','revision':'primary-pinned'});two=replace(one,award_instance='DIRECTING',category='DIRECTING',evidence={'source':'annual_wikitext','revision':'independent-pinned'})
        other_one=self.independent();other_two=replace(self.independent(),award_instance='DIRECTING',category='DIRECTING',evidence=one.evidence)
        self.assertTrue(self.verify(primary=[one,two],independent=[other_one,other_two]).complete)
        self.assertFalse(self.verify(primary=[one,two],independent=[one,other_two]).complete)
        same=replace(self.independent(),evidence={'source':'dlu_oscar','revision':123})
        origin=replace(one,evidence={'source':'dlu_oscar','revision':'123'})
        self.assertFalse(self.verify(primary=[origin],independent=[same]).complete)

    def test_curated_copy_cannot_verify_the_original_category_under_another_adapter(self):
        url='https://en.wikipedia.org/w/index.php?oldid=123'
        primary=replace(self.primary(),evidence={'source':'reviewed_wikipedia_facts','revision':'compilation-hash',
            'reviewed_source':{'source_url':url,'revision':'123','reason':'Exact transcribed winning record'}})
        independent=replace(self.independent(),evidence={'source':'annual_wikitext','revision':123,'source_url':url})
        report=self.verify(primary=[primary],independent=[independent])
        self.assertFalse(report.complete)
        self.assertIn('missing_independent_source',report.diagnostics)
        independent=replace(independent,evidence={'source':'reviewed_official_facts','revision':'official-hash',
            'reviewed_source':{'source_url':'https://goldenglobes.com/film/first/','revision':'official-hash'}})
        self.assertTrue(self.verify(primary=[primary],independent=[independent]).complete)

    def test_shared_recipients_do_not_inflate_verified_film_awards(self):
        other = replace(self.primary(), people=(replace(self.primary().people[0], title='Other', imdb_id='nm0020202', tmdb_id=21),))
        independent_other = replace(self.independent(), people=(adapter().EntityReference('person', 'Other'),))
        self.assertTrue(self.verify(primary=[self.primary(), other],
                                    independent=[self.independent(), independent_other]).complete)

    def test_punctuation_variants_match_but_words_cannot_disappear(self):
        primary = replace(self.primary(), films=(replace(self.primary().films[0], title='Harlan County U.S.A.'),),
                          people=(replace(self.primary().people[0], title='J.K. Simmons'),))
        self.assertTrue(self.verify(primary=[primary], independent=[self.independent('Harlan County, USA', 'J. K. Simmons')]).complete)
        self.assertFalse(self.verify(primary=[primary], independent=[self.independent('Harlan USA', 'J. K. Simmons')]).complete)

    def test_ties_and_multi_film_win_require_independent_film_evidence(self):
        primary = self.primary()
        film = replace(primary.films[0], title='Second', imdb_id='tt0020202', tmdb_id=11)
        multi = replace(primary, films=primary.films + (film,))
        independent = replace(self.independent(), films=self.independent().films + (adapter().EntityReference('movie', 'Second'),))
        report = self.verify(primary=[multi], independent=[independent])
        self.assertTrue(report.complete)
        self.assertEqual(report.evidence['multi_film_awards'], ['ACTOR IN A LEADING ROLE'])
        second = replace(self.independent(), films=(adapter().EntityReference('movie', 'Second'),))
        report = self.verify(primary=[multi], independent=[self.independent(), second])
        self.assertTrue(report.complete)
        self.assertEqual(report.evidence['ties'], ['ACTOR IN A LEADING ROLE'])

    def test_bibliographic_title_with_trailing_space_matches_only_the_same_film(self):
        win=self.primary()
        primary=replace(win,films=(replace(win.films[0],title='Disaster Artist, The '),))
        self.assertTrue(self.verify(primary=[primary],independent=[self.independent('The Disaster Artist')]).complete)
        self.assertFalse(self.verify(primary=[primary],independent=[self.independent('The Disaster Movie')]).complete)


class LinkedIdentityVerificationTests(unittest.TestCase):
    def candidate(self, namespace='movie', **extra):
        return dict(namespace=namespace, imdb_id='tt0010101' if namespace=='movie' else 'nm0010101',
                    tmdb_id=10 if namespace=='movie' else 20, source_alias='First' if namespace=='movie' else 'Person',
                    source_context={'source':'historical_globe','ceremony':1,'category':'Best Actor'},
                    evidence={'source_url':'https://en.wikipedia.org/w/index.php?oldid=123',
                              'revision':'123','reason':'Named independent winning subject link and structured external identifiers agree'},
                    winning_movie_ids=[10], **extra)

    def reference(self, namespace='movie', role='actor'):
        return adapter().EntityReference(namespace, 'First' if namespace=='movie' else 'Person', evidence=({
            'source':'historical_globe','ceremony':1,'category':'Best Actor','role':role,
            'winning_people':['Person'],'winning_films':['First']},))

    def verify(self, ref=None, candidate=None, credits=None, response=None):
        return resolver().verify_linked_candidate(ref or self.reference(), identity=candidate or self.candidate(),
             find_by_imdb=lambda *args: response or {'movie_results':[{'id':10,'title':'First'}], 'person_results':[{'id':20,'name':'Person'}]},
             load_credits=lambda movie_id: credits if credits is not None else {'cast':[{'id':20,'name':'Person'}], 'crew':[]})

    def test_explicit_source_link_external_id_and_acting_credit_resolve_movie(self):
        result=self.verify()
        self.assertEqual(result['tmdb_id'],10)
        self.assertTrue(result['verified_external_id'])
        self.assertTrue(result['verified_role_credits'])

    def test_person_requires_membership_in_every_winning_film_in_correct_role(self):
        self.assertEqual(self.verify(self.reference('person'),self.candidate('person'))['tmdb_id'],20)
        self.assertIsNone(self.verify(self.reference('person','director'),self.candidate('person')))
        calls=[]
        def credits(movie_id):
            calls.append(movie_id)
            return {'cast':[{'id':20}] if movie_id==10 else [],'crew':[]}
        candidate=self.candidate('person');candidate['winning_movie_ids']=[10,11]
        self.assertIsNone(resolver().verify_linked_candidate(self.reference('person'), identity=candidate,
             find_by_imdb=lambda *a:{'person_results':[{'id':20}]},load_credits=credits))
        self.assertEqual(calls,[10,11])

    def test_matching_title_wrong_credits_or_external_domain_are_rejected(self):
        self.assertIsNone(self.verify(credits={'cast':[{'id':99,'name':'Wrong actor'}]}))
        self.assertIsNone(self.verify(response={'tv_results':[{'id':10}]}))
        candidate=self.candidate();candidate['imdb_id']='nm0010101'
        self.assertIsNone(self.verify(candidate=candidate))

    def test_structured_tmdb_disagreement_unpinned_or_other_context_stay_unresolved(self):
        for key,value in [('tmdb_id',11),('source_context',{'source':'historical_globe','ceremony':2,'category':'Best Actor'}),('evidence',{})]:
            candidate=self.candidate();candidate[key]=value
            self.assertIsNone(self.verify(candidate=candidate))

    def test_nonpersonal_film_category_requires_explicit_source_identity_proof(self):
        result=self.verify(self.reference(role=None),credits={})
        self.assertEqual(result['imdb_id'],'tt0010101')
        candidate=self.candidate();candidate['source_alias']='Other film'
        self.assertIsNone(self.verify(self.reference(role=None),candidate=candidate))



class SourceTitleTypographyTests(unittest.TestCase):
    def test_bibliographic_articles_and_release_year_are_contextual_aliases(self):
        labels=resolver()._reference_labels(adapter().EntityReference('movie','Star Is Born, A (1954)'),None)
        other=resolver()._reference_labels(adapter().EntityReference('movie','A Star Is Born',evidence=({'wiki_target':'A Star Is Born (1954 film)'},)),None)
        self.assertTrue(labels & other)
        self.assertFalse(labels & resolver()._reference_labels(adapter().EntityReference('movie','A Different Star Is Born'),None))
