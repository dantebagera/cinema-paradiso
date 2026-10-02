"""Hand-derived award contracts; recipient rows must never inflate film wins."""
import csv
import importlib
import io
import unittest
from datetime import date
import json
from pathlib import Path
import tempfile
import hashlib
from unittest.mock import patch
import urllib.error


def adapter():
    try:
        return importlib.import_module('services.movie_awards_sources')
    except ModuleNotFoundError:
        raise AssertionError('The approved pure awards source owner is not implemented')


def payload(fields, rows, delimiter=','):
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=fields, delimiter=delimiter)
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


OSCAR_FIELDS = ['Ceremony', 'Year', 'Class', 'CanonicalCategory', 'Category', 'Film',
                'FilmId', 'Name', 'Nominees', 'NomineeIds', 'Winner']
MODERN_FIELDS = ['eventId', 'year', 'awardName', 'categoryName', 'primaryNomineeName',
                 'primaryNomineeCode', 'secondaryNomineeName', 'secondaryNomineeCode', 'isWinner']


def oscar(category='ACTOR', films='tt0010101', people='nm0010101', **extra):
    return dict(Ceremony='1', Year='1927/28', Class='Acting', CanonicalCategory='ACTOR IN A LEADING ROLE',
                Category=category, Film='First|Second' if '|' in films else 'First',
                FilmId=films, Name='Person', Nominees='Person', NomineeIds=people, Winner='True', **extra)


def globe(category, film='tt0172495', person='nm0000001', year='2001'):
    return dict(eventId='ev0000292', year=year, awardName='Golden Globe', categoryName=category,
                primaryNomineeName="['Person']", primaryNomineeCode=repr([person]),
                secondaryNomineeName="['Gladiator']", secondaryNomineeCode=repr([film]), isWinner='True')


class MovieAwardSourcesTests(unittest.TestCase):
    def test_annual_identity_evidence_retains_link_target_and_eligibility_context(self):
        raw = ("{|\n| {{Award category|#F9EFAA|[[Academy Award for Best Actor|Best Actor]]}}\n"
               "* '''[[Person Full Name|Person]]''' - ''[[First (1928 film)|Displayed alias]]''\n|}").encode()
        win = adapter().parse_source('annual_wikitext', raw,
            {'organization': 'oscar', 'revision': 123, 'ceremony': 1, 'ceremony_year': 1929})[0]
        self.assertEqual(win.films[0].evidence[0]['wiki_target'], 'First (1928 film)')
        self.assertEqual(win.people[0].evidence[0]['wiki_target'], 'Person Full Name')
        self.assertEqual(win.evidence['winning_films'], ['Displayed alias'])
        primary = self.parse_oscar([oscar()])[0]
        self.assertEqual(primary.evidence['eligibility_year'], '1927/28')
        self.assertEqual(primary.evidence['credit_names'], ['Person'])

    def test_joint_named_directors_are_two_people_with_one_film_award(self):
        raw = ("{|\n| {{Award category|#F9EFAA|[[Academy Award for Best Director|Best Director]]}}\n"
               "* '''[[Directors duo|First Director and Second Director]]''' - ''[[First Film]]''\n|}").encode()
        win = adapter().parse_source('annual_wikitext', raw,
            {'organization': 'oscar', 'revision': 123, 'ceremony': 95, 'ceremony_year': 2023})[0]
        self.assertEqual([p.title for p in win.people], ['First Director', 'Second Director'])
        self.assertEqual([p.evidence[0]['wiki_group_target'] for p in win.people], ['Directors duo'] * 2)
        self.assertEqual(win.evidence['winning_people'], ['First Director', 'Second Director'])
        self.assertEqual(len(win.films), 1)

    def test_semicolon_honors_keep_explicit_citation_subtypes(self):
        raw = ("==Awards==\n{|\n| {{Award category|#F9EFAA|[[Academy Award for Best Picture|Best Picture]]}}\n"
               "* '''''[[First Film]]'''''\n|}\n===Non-competitive awards===\n;Special Achievement Award\n"
               "* To [[First Technician]] for alien voices in ''[[First Film]]''.\n"
               "* To [[Second Technician]] for sound effects editing of ''[[First Film]]''.\n").encode()
        meta = {'organization': 'oscar', 'revision': 1, 'ceremony': 50, 'ceremony_year': 1978,
                'ceremony_date': '1978-04-03'}
        wins = adapter().parse_source('annual_wikitext', raw, meta)
        self.assertEqual([w.award_instance for w in wins],
                         ['BEST PICTURE', 'SPECIAL ACHIEVEMENT AWARD', 'SPECIAL ACHIEVEMENT AWARD (Sound Effects Editing)'])
        program = adapter().parse_annual_program(raw, meta)
        self.assertEqual(set(program.expected_instances), {w.award_instance for w in wins})
        with self.assertRaises(adapter().SourceError):
            adapter().parse_source('annual_wikitext', raw.replace(b';Special Achievement Award', b';Unreviewed Award'), meta)

    def test_early_explicit_winners_accept_bold_lines_without_bullets(self):
        raw = ("==Winners==\n"
               "===[[Golden Globe Award for Best Actor – Motion Picture Drama|Best Actor - Drama]]===\n"
               "''' [[Actor]] - ''[[First Film]]'''''\n").encode()
        wins = adapter().parse_source('annual_wikitext', raw,
            {'organization': 'golden_globe', 'revision': 1, 'ceremony': 11, 'ceremony_year': 1954})
        self.assertEqual(len(wins), 1)
        self.assertEqual([r.title for r in wins[0].people], ['Actor'])
        self.assertEqual([r.title for r in wins[0].films], ['First Film'])

    def parse_oscar(self, rows):
        return adapter().parse_source('dlu_oscar', payload(OSCAR_FIELDS, rows, '\t'), {})

    def parse_modern(self, rows):
        return adapter().parse_source('modern_globe', payload(MODERN_FIELDS, rows), {})

    def test_gladiator_counts_two_categories_not_three_recipients(self):
        wins = self.parse_modern([globe('Best Motion Picture - Drama'),
                                 globe('Best Original Score - Motion Picture', person='nm0000002'),
                                 globe('Best Original Score - Motion Picture', person='nm0000003')])
        contribution = adapter().aggregate_ceremony(wins)
        self.assertEqual(contribution.films, {'movie:imdb:tt0172495': 2})
        self.assertEqual(contribution.person_wins, ())

    def test_les_girls_shared_actress_category(self):
        rows = [globe('Best Motion Picture - Musical or Comedy', film='tt0050631', year='1958'),
                globe('Best Performance by an Actress in a Motion Picture - Musical or Comedy',
                      film='tt0050631', person='nm0000101', year='1958'),
                globe('Best Performance by an Actress in a Motion Picture - Musical or Comedy',
                      film='tt0050631', person='nm0000102', year='1958')]
        contribution = adapter().aggregate_ceremony(self.parse_modern(rows))
        self.assertEqual(contribution.films, {'movie:imdb:tt0050631': 2})
        self.assertEqual({w.person for w in contribution.person_wins},
                         {'person:imdb:nm0000101', 'person:imdb:nm0000102'})

    def test_hindenburg_special_subtypes_remain_two(self):
        rows = []
        for category in ['SPECIAL ACHIEVEMENT AWARD (Sound Effects)', 'SPECIAL ACHIEVEMENT AWARD (Visual Effects)']:
            row = oscar(category, 'tt0073113'); row.update(Ceremony='48', Year='1975', Class='Special')
            rows.append(row)
        self.assertEqual(adapter().aggregate_ceremony(self.parse_oscar(rows)).films,
                         {'movie:imdb:tt0073113': 2})

    def test_one_person_win_multiple_films(self):
        contribution = adapter().aggregate_ceremony(self.parse_oscar([oscar(films='tt0010101|tt0010102')]))
        self.assertEqual(len(contribution.person_wins), 1)
        self.assertEqual(contribution.person_wins[0].films,
                         ('movie:imdb:tt0010101', 'movie:imdb:tt0010102'))

    def test_tv_movie_and_unrelated_event_are_excluded(self):
        tv = globe('Best Performance by an Actor in a Limited Series or a Motion Picture Made for Television')
        other = globe('Best Motion Picture - Drama'); other['eventId'] = 'ev0000003'
        contribution = adapter().aggregate_ceremony(self.parse_modern([tv, other]))
        self.assertEqual(contribution.films, {})
        self.assertEqual(contribution.person_wins, ())

    def test_unknown_category_and_malformed_arrays_fail_closed(self):
        for row in [globe('Best Brand New Film Award'),
                    dict(globe('Best Director - Motion Picture'), primaryNomineeCode="__import__('os').system('echo bad')"),
                    dict(globe('Best Director - Motion Picture'), primaryNomineeCode="['nm0000001', 7]")]:
            with self.subTest(row=row), self.assertRaises(adapter().SourceError):
                self.parse_modern([row])

    def test_ambiguous_winner_marker_is_not_false(self):
        row = oscar(); row['Winner'] = 'maybe'
        with self.assertRaises(adapter().SourceError):
            self.parse_oscar([row])

    def test_dlu_blank_nominee_marker_is_not_a_win(self):
        row = oscar(); row['Winner'] = ''
        self.assertEqual(self.parse_oscar([row]), [])

    def test_oscar_eligibility_year_disagrees_with_ceremony(self):
        row = oscar(); row.update(Ceremony='98', Year='2024')
        with self.assertRaises(adapter().SourceError):
            self.parse_oscar([row])

    def test_missing_film_on_eligible_win_cannot_be_aggregated(self):
        row = oscar(); row.update(Film='', FilmId='')
        with self.assertRaises(adapter().SourceError):
            adapter().aggregate_ceremony(self.parse_oscar([row]))

    def test_unknown_ids_remain_unresolved(self):
        wins = self.parse_oscar([oscar(films='?')])
        self.assertIsNone(wins[0].films[0].imdb_id)
        with self.assertRaises(adapter().SourceError):
            adapter().aggregate_ceremony(wins)

    def test_nominations_missing_category_and_wrong_ceremony_never_complete(self):
        module = adapter()
        expected = module.CeremonyProgram('oscar', 1, 1929, date(1929, 5, 16), ('ACTOR IN A LEADING ROLE', 'DIRECTING'),
                                           {'revision': 'independent-program-1'})
        evidence = {'as_of': '2026-10-02', 'crosscheck_agrees': True, 'revision': 'independent-winners-1'}
        nominee = oscar(); nominee['Winner'] = 'False'
        for wins in [self.parse_oscar([nominee]), self.parse_oscar([oscar()])]:
            report = module.validate_ceremony(wins, expected, evidence)
            self.assertFalse(report.complete)
            self.assertIn('missing_winners', report.diagnostics)
        wrong = oscar(); wrong['Ceremony'] = '2'; wrong['Year'] = '1928/29'
        self.assertIn('ceremony_mismatch', module.validate_ceremony(self.parse_oscar([wrong]), expected, evidence).diagnostics)

    def test_tied_winners_preserved_and_require_explicit_evidence(self):
        module = adapter()
        rows = [oscar('SHORT FILM (Live Action)', 'tt0010101'), oscar('SHORT FILM (Live Action)', 'tt0010102')]
        program = module.CeremonyProgram('oscar', 1, 1929, date(1929, 5, 16), ('SHORT FILM (Live Action)',),
                                         {'revision': 'program'})
        wins = self.parse_oscar(rows)
        evidence = {'as_of': '2026-10-02', 'revision': 'independent', 'crosscheck_agrees': True}
        self.assertFalse(module.validate_ceremony(wins, program, evidence).complete)
        evidence['ties'] = ['SHORT FILM (Live Action)']
        self.assertTrue(module.validate_ceremony(wins, program, evidence).complete)
        self.assertEqual(module.aggregate_ceremony(wins).films,
                         {'movie:imdb:tt0010101': 1, 'movie:imdb:tt0010102': 1})

    def test_source_disagreement_and_future_ceremony_stay_pending(self):
        module = adapter()
        program = module.CeremonyProgram('oscar', 1, 1929, date(1929, 5, 16), ('ACTOR IN A LEADING ROLE',), {'revision': 'program'})
        wins = self.parse_oscar([oscar()])
        self.assertFalse(module.validate_ceremony(wins, program, {'as_of': '2026-10-02', 'crosscheck_agrees': False}).complete)
        self.assertFalse(module.validate_ceremony(wins, program, {'as_of': '1929-05-15', 'crosscheck_agrees': True}).complete)

    def test_duplicate_recipient_rows_are_idempotent(self):
        wins = self.parse_oscar([oscar(), oscar()])
        contribution = adapter().aggregate_ceremony(wins)
        self.assertEqual(contribution.films, {'movie:imdb:tt0010101': 1})
        self.assertEqual(len(contribution.person_wins), 1)

    def test_historical_and_modern_category_aliases_share_one_award_instance(self):
        wins = self.parse_oscar([oscar('ACTOR'), oscar('ACTOR IN A LEADING ROLE')])
        contribution = adapter().aggregate_ceremony(wins)
        self.assertEqual(contribution.films, {'movie:imdb:tt0010101': 1})
        self.assertEqual(len(contribution.person_wins), 1)

    def test_actual_pinned_oscar_special_and_multi_film_rows(self):
        root = Path(__file__).parent / 'fixtures/movie_awards'
        wins = adapter().parse_source('dlu_oscar', (root / 'oscar_historical.tsv').read_bytes(), {})
        special = adapter().aggregate_ceremony([w for w in wins if w.ceremony == 48])
        self.assertEqual(special.films, {'movie:imdb:tt0073113': 2})
        early = adapter().aggregate_ceremony([w for w in wins if w.ceremony == 1])
        self.assertEqual(len(early.person_wins), 1)
        self.assertEqual(len(early.person_wins[0].films), 2)

    def test_actual_pinned_globe_picture_title_is_in_nominee_field(self):
        root = Path(__file__).parent / 'fixtures/movie_awards'
        wins = adapter().parse_source('historical_globe', (root / 'globe_les_girls.csv').read_bytes(), {})
        self.assertEqual(len(wins), 3)
        self.assertEqual({film.title for win in wins for film in win.films}, {'Les Girls'})
        self.assertEqual({person.title for win in wins for person in win.people}, {'Taina Elg', 'Kay Kendall'})

    def test_collective_special_honor_is_excluded_by_verified_subject_kind(self):
        row = oscar('SPECIAL AWARD', films='tt0010101')
        subject = {'imdb_id': 'tt0010101', 'kind': 'film_series',
                   'evidence': {'source_url': 'https://example.org/official-award',
                                'revision': 'verified-program'}}
        wins = adapter().parse_source('dlu_oscar', payload(OSCAR_FIELDS, [row], '\t'),
                                      {'subjects': [subject]})
        self.assertEqual(wins[0].scope, 'other')
        self.assertEqual(wins[0].evidence['exclusion_reason'], 'collective')
        self.assertEqual(adapter().aggregate_ceremony(wins).films, {})
        # A verified subject classification cannot erase a conflicting ordinary
        # film win. That discrepancy remains reviewable instead of hiding it.
        with self.assertRaises(adapter().SourceError):
            adapter().parse_source('dlu_oscar', payload(OSCAR_FIELDS, [oscar()], '\t'),
                                   {'subjects': [subject]})

    def test_unverified_subject_classification_cannot_remove_winning_movie(self):
        row = oscar('SPECIAL AWARD', films='tt0010101')
        with self.assertRaises(adapter().SourceError):
            adapter().parse_source('dlu_oscar', payload(OSCAR_FIELDS, [row], '\t'),
                                   {'subjects': [{'imdb_id': 'tt0010101', 'kind': 'film_series'}]})

    def test_pinned_2025_2026_annual_layouts_ignore_nominees_and_captions(self):
        directory = Path(__file__).parent / 'fixtures/movie_awards'
        expected = {
            '97th_Academy_Awards': ('Anora',),
            '98th_Academy_Awards': ('One Battle After Another',),
            '82nd_Golden_Globes': ('The Brutalist', 'The Brutalist'),
            '83rd_Golden_Globes': ('Hamnet', 'The Secret Agent'),
        }
        for name, films in expected.items():
            with self.subTest(name=name):
                manifest = json.loads((directory / (name + '.provenance.json')).read_text(encoding='utf-8'))
                raw = (directory / (name + '.wiki')).read_bytes()
                wins = adapter().parse_source('annual_wikitext', raw, manifest)
                self.assertEqual(tuple(f.title for w in wins for f in w.films), films)
                self.assertTrue(all(f.imdb_id is None for w in wins for f in w.films))

    def test_redirect_and_unsupported_annual_layout_fail_closed(self):
        for raw in [b'#REDIRECT [[Another page]]', b'Winners announced! [[File:Actor.jpg|Best Actor winner]]']:
            with self.assertRaises(adapter().SourceError):
                adapter().parse_source('annual_wikitext', raw, {'organization': 'oscar', 'revision': 1})

    def test_paired_globe_table_uses_full_category_target(self):
        raw = """{| class="wikitable"
! colspan="2" |Best Motion Picture
|-
! [[Golden Globe Award for Best Motion Picture – Drama|Drama]]
! [[Golden Globe Award for Best Motion Picture – Musical or Comedy|Musical or Comedy]]
|-
| valign="top" |
*'''''[[Drama winner]]'''''
** ''[[Drama nominee]]''
| valign="top" |
*''' ''[[Comedy winner]]'''''
** ''[[Comedy nominee]]''
|-
! [[Golden Globe Award for Best Actor – Motion Picture Drama|Actor]]
! [[Golden Globe Award for Best Actress – Motion Picture Drama|Actress]]
|-
| valign="top" |
*'''[[Actor winner]]'''&nbsp;– '''''[[Drama winner]]'' as [[Character]]'''
| valign="top" |
*'''[[Actress winner]]''' – '''''[[Other film]]'''''
|}
""".encode()
        wins = adapter().parse_source('annual_wikitext', raw,
            {'organization': 'golden_globe', 'revision': 1, 'ceremony': 44, 'ceremony_year': 1987})
        self.assertEqual([f.title for w in wins for f in w.films],
                         ['Drama winner', 'Comedy winner', 'Drama winner', 'Other film'])
        self.assertEqual([p.title for w in wins for p in w.people], ['Actor winner', 'Actress winner'])
        self.assertEqual(len({w.award_instance for w in wins}), 4)

    def test_earliest_globe_explicit_winners_section_is_separate_from_nominees(self):
        raw = """==Winners==
===[[Golden Globe Award for Best Motion Picture – Drama|Best Picture]]===
*''[[Winning Film]]''
===[[Golden Globe Award for Best Actor – Motion Picture Drama|Best Actor in a Leading Role]]===
*[[Winning Actor]] – ''[[Winning Film]]'' as [[Character]]
==See also==
* [[Some other Film]]
""".encode()
        wins = adapter().parse_source('annual_wikitext', raw,
            {'organization': 'golden_globe', 'revision': 1, 'ceremony': 1, 'ceremony_year': 1944})
        self.assertEqual([f.title for w in wins for f in w.films], ['Winning Film', 'Winning Film'])
        self.assertEqual([p.title for w in wins for p in w.people], ['Winning Actor'])

    def test_plain_award_header_and_no_space_bullet_preserve_historical_picture(self):
        raw = """{| class=wikitable
| {{Award category|#F9EFAA|Best Unique and Artistic Picture}}
*'''''[[Sunrise]]'' {{ndash}} [[Studio]]'''
** ''[[Nominee]]''
|}
""".encode()
        wins = adapter().parse_source('annual_wikitext', raw,
            {'organization': 'oscar', 'revision': 1, 'ceremony': 1, 'ceremony_year': 1929})
        self.assertEqual([f.title for w in wins for f in w.films], ['Sunrise'])
        self.assertEqual(wins[0].award_instance, 'UNIQUE AND ARTISTIC PICTURE')

    def test_self_closing_reference_does_not_consume_following_award_table(self):
        raw = """<ref name="previous"/>
{| class=wikitable
| {{Award category|#F9EFAA|[[Academy Award for Best Picture|Best Picture]]}}
*'''''[[Winning Film]]'''''
|}
Later prose<ref>Different full reference</ref>
""".encode()
        wins = adapter().parse_source('annual_wikitext', raw,
            {'organization': 'oscar', 'revision': 1, 'ceremony': 98, 'ceremony_year': 2026})
        self.assertEqual([f.title for w in wins for f in w.films], ['Winning Film'])

    def test_paired_plain_category_and_empty_cell_do_not_drop_other_awards(self):
        raw = """{| class=wikitable
! Best Film Promoting International Understanding
! [[Golden Globe Award for Best Original Score|Best Music, Original Score]]
|-
| valign="top" |
*''' ''[[Film One]]'''''
| valign="top" |
*''' "[[Film Two]]" – [[Composer]]'''
|-
! [[Golden Globe Award for Best Miniseries or Television Film|Best Miniseries]]
!
|-
| valign="top" |
*''' ''[[A TV Film]]'''''
| valign="top" |
|}
""".encode()
        wins = adapter().parse_source('annual_wikitext', raw,
            {'organization': 'golden_globe', 'revision': 1, 'ceremony': 20, 'ceremony_year': 1963})
        self.assertEqual([f.title for w in wins for f in w.films], ['Film One', 'Film Two'])

    def test_heading_winners_and_nominees_accepts_only_explicit_bold_winner(self):
        raw = """==Winners and Nominees==
===[[Golden Globe Award for Best Motion Picture – Drama|Best Motion Picture – Drama]]===
''' ''[[Winning Film]]'' '''
* ''[[Nominee Film]]''
==See also==
''' ''[[Unrelated Film]]'' '''
""".encode()
        wins = adapter().parse_source('annual_wikitext', raw,
            {'organization': 'golden_globe', 'revision': 1, 'ceremony': 10, 'ceremony_year': 1953})
        self.assertEqual([f.title for w in wins for f in w.films], ['Winning Film'])

    def test_unlinked_italic_film_remains_an_alias_requiring_identity_verification(self):
        raw = """{| class=wikitable
| {{Award category|#F9EFAA|[[Golden Globe Award for Best Original Score|Best Original Score – Motion Picture]]}}
*'''[[Composer]], ''Winning Film'''''
** [[Other Composer]], ''Nominated Film''
|}
""".encode()
        wins = adapter().parse_source('annual_wikitext', raw,
            {'organization': 'golden_globe', 'revision': 1, 'ceremony': 65, 'ceremony_year': 2008})
        self.assertEqual([f.title for w in wins for f in w.films], ['Winning Film'])
        self.assertIsNone(wins[0].films[0].imdb_id)

    def test_italicized_acting_recipient_is_not_an_extra_winning_film(self):
        raw = """==Film==
===[[Golden Globe Award for Best Actor – Motion Picture Drama|Best Actor - Drama]]===
'' '''[[Actor]] - [[Winning Film]]'''''
* ''[[Nominated Actor]] - [[Nominated Film]]''
==References==
""".encode()
        wins = adapter().parse_source('annual_wikitext', raw,
            {'organization': 'golden_globe', 'revision': 1, 'ceremony': 15, 'ceremony_year': 1958})
        self.assertEqual([f.title for w in wins for f in w.films], ['Winning Film'])
        self.assertEqual([p.title for w in wins for p in w.people], ['Actor'])

    def test_inline_bold_table_cell_is_winner_and_single_star_nominees_are_excluded(self):
        raw = """{| class=wikitable
! [[Golden Globe Award for Best Motion Picture – Drama|Drama]]
! [[Golden Globe Award for Best Motion Picture – Musical or Comedy|Musical or Comedy]]
|-
| valign="top" |'''''[[Drama Winner]]'''''
* ''[[Drama Nominee]]''
| valign="top" |''' ''[[Comedy Winner]]'''''
* ''[[Comedy Nominee]]''
|}
""".encode()
        wins = adapter().parse_source('annual_wikitext', raw,
            {'organization': 'golden_globe', 'revision': 1, 'ceremony': 49, 'ceremony_year': 1992})
        self.assertEqual([f.title for w in wins for f in w.films], ['Drama Winner', 'Comedy Winner'])

    def test_adapted_screenplay_source_book_is_not_a_second_winning_film(self):
        raw = """{| class=wikitable
| {{Award category|#F9EFAA|[[Academy Award for Best Adapted Screenplay|Best Writing (Adapted Screenplay)]]}}
*'''''[[Winning Film]]'' – [[Writer]], based on ''[[Source Novel]]'' by [[Author]]'''
|}
""".encode()
        wins = adapter().parse_source('annual_wikitext', raw,
            {'organization': 'oscar', 'revision': 1, 'ceremony': 98, 'ceremony_year': 2026})
        self.assertEqual([f.title for w in wins for f in w.films], ['Winning Film'])

    def test_independent_program_requires_category_even_when_winner_is_missing(self):
        raw = """{| class=wikitable
| {{Award category|#F9EFAA|[[Academy Award for Best Picture|Best Picture]]}}
*'''''[[Winning Film]]'''''
| {{Award category|#F9EFAA|[[Academy Award for Best Director|Best Directing]]}}
** [[Nominated Director]] – ''[[Nominated Film]]''
|}
""".encode()
        module = adapter()
        self.assertTrue(hasattr(module, 'parse_annual_program'), 'Independent category-program parser is missing')
        manifest = {'organization': 'oscar', 'revision': 1, 'ceremony': 98,
                    'ceremony_year': 2026, 'ceremony_date': '2026-03-15'}
        program = module.parse_annual_program(raw, manifest)
        self.assertEqual(set(program.expected_instances), {'BEST PICTURE', 'DIRECTING'})
        report = module.validate_ceremony(module.parse_source('annual_wikitext', raw, manifest), program,
            {'as_of': '2026-10-02', 'revision': 'independent', 'crosscheck_agrees': True})
        self.assertIn('missing_winners', report.diagnostics)

    def test_historical_special_sections_count_film_honors_but_not_career_honors(self):
        raw = """{| class=wikitable
| {{Award category|#F9EFAA|[[Academy Award for Best Picture|Best Picture]]}}
*'''''[[Picture Winner]]'''''
|}
===Special Achievement Award (Sound Effects)===
*''[[The Hindenburg (film)|The Hindenburg]]'' – [[Sound Recipient]].
===Special Achievement Award (Visual Effects)===
*''[[The Hindenburg (film)|The Hindenburg]]'' – [[Visual Recipient]].
===Honorary Award===
* To [[Career Recipient]] for a lifetime of contribution to cinema.
===Multiple nominations and awards===
* ''[[An Unrelated Film]]''
""".encode()
        wins = adapter().parse_source('annual_wikitext', raw,
            {'organization': 'oscar', 'revision': 1, 'ceremony': 48, 'ceremony_year': 1976})
        self.assertEqual([f.title for w in wins for f in w.films],
                         ['Picture Winner', 'The Hindenburg', 'The Hindenburg'])
        self.assertEqual(len({w.award_instance for w in wins}), 3)

    def test_annual_collective_subject_alias_does_not_create_movie_or_expected_film_category(self):
        raw = """===Special awards===
* To ''[[A Collective Series]]'' for innovation in the newsreel industry.
""".encode()
        subject = {'imdb_id': 'tt0010101', 'kind': 'film_series',
                   'source_aliases': [{'source': 'annual_wikitext', 'ceremony': 9,
                                      'category': 'Special awards', 'title': 'A Collective Series'}],
                   'evidence': {'source_url': 'https://example.org/official-program', 'revision': 'verified'}}
        manifest = {'organization': 'oscar', 'revision': 1, 'ceremony': 9, 'ceremony_year': 1937,
                    'ceremony_date': '1937-03-04', 'subjects': [subject]}
        wins = adapter().parse_source('annual_wikitext', raw, manifest)
        self.assertFalse(any(w.scope == 'film' for w in wins))
        self.assertEqual(adapter().parse_annual_program(raw, manifest).expected_instances, ())

    def test_technical_commendation_does_not_become_film_win_when_citation_names_a_film(self):
        row = oscar('AWARD OF COMMENDATION', films='tt0010101')
        self.assertEqual(adapter().aggregate_ceremony(self.parse_oscar([row])).films, {})

    def test_verified_nonfilm_alias_needs_no_invented_movie_identifier(self):
        raw = b"===Special awards===\n* To the performer for the comedy character ''[[Character Name]]''.\n"
        subject = {'kind': 'character',
                   'source_aliases': [{'source': 'annual_wikitext', 'ceremony': 10,
                                      'category': 'Special awards', 'title': 'Character Name'}],
                   'evidence': {'source_url': 'https://example.org/official-program', 'revision': 'verified'}}
        wins = adapter().parse_source('annual_wikitext', raw,
            {'organization': 'oscar', 'revision': 1, 'ceremony': 10, 'ceremony_year': 1938,
             'subjects': [subject]})
        self.assertEqual(adapter().aggregate_ceremony(wins).films, {})

    def test_independent_program_uses_presented_date_and_rejects_ceremony_mismatch(self):
        raw = """{{Infobox film awards
| number = 2
| announced_date = {{Start date|1945|02}}
| presented_date = {{Start date|1945|04|16}}
}}
==Winners==
===[[Golden Globe Award for Best Motion Picture – Drama|Best Picture]]===
*''[[Winning Film]]''
""".encode()
        manifest = {'organization': 'golden_globe', 'revision': 1, 'ceremony': 2, 'ceremony_year': 1945}
        program = adapter().parse_annual_program(raw, manifest)
        self.assertEqual(program.ceremony_date, date(1945, 4, 16))
        for changes in [{'ceremony': 3}, {'ceremony_year': 1946}, {'ceremony_date': '1945-02-01'}]:
            with self.subTest(changes=changes), self.assertRaises(adapter().SourceError):
                adapter().parse_annual_program(raw, {**manifest, **changes})

    def test_full_reference_after_ceremony_date_does_not_hide_the_date(self):
        raw = """{{Infobox film awards
| number = 5
| date = November 18, 1932<ref name="date">{{cite web|title=Official program}}</ref>
}}
{| class=wikitable
| {{Award category|#F9EFAA|[[Academy Award for Best Picture|Best Picture]]}}
*'''''[[Winning Film]]'''''
|}
""".encode()
        program = adapter().parse_annual_program(raw,
            {'organization': 'oscar', 'revision': 1, 'ceremony': 5, 'ceremony_year': 1932})
        self.assertEqual(program.ceremony_date, date(1932, 11, 18))

    def test_annual_multiline_header_reference_and_character_links_are_not_recipients(self):
        raw = """{| class="wikitable"
| {{Award category|#F9EFAA|[[Academy Award for Best Adapted Screenplay|Best Writing (Adapted Screenplay)]]<ref>Multiple sources:
{{cite web|title=Source|url=https://example.org}}
</ref>}}
* '''''[[Verified Film]]'' – [[Writer]] ‡'''
| {{Award category|#F9EFAA|[[Academy Award for Best Actor|Best Actor]]}}
* '''[[Actor]] – ''[[Other Film]]'' as [[Real Character]] ‡'''
|}
""".encode()
        wins = adapter().parse_source('annual_wikitext', raw,
                                     {'organization': 'oscar', 'revision': 1, 'ceremony': 98, 'ceremony_year': 2026})
        self.assertEqual([w.award_instance for w in wins], ['WRITING (Adapted Screenplay)', 'ACTOR IN A LEADING ROLE'])
        self.assertEqual([p.title for p in wins[1].people], ['Actor'])


class HistoricalSeedBuildTests(unittest.TestCase):
    def build_owner(self):
        try:
            return importlib.import_module('tools.build_movie_awards_snapshot')
        except ModuleNotFoundError:
            raise AssertionError('The approved reproducible seed builder is not implemented')

    def inputs(self, root):
        raw = payload(OSCAR_FIELDS, [oscar()], '\t')
        (root / 'oscars.csv').write_bytes(raw)
        mappings = [dict(namespace='movie', imdb_id='tt0010101', tmdb_id=10, evidence={'revision': 'verified-film'}),
                    dict(namespace='person', imdb_id='nm0010101', tmdb_id=20, evidence={'revision': 'verified-person'})]
        return {'schema_version': 1, 'as_of': '2026-10-02',
                'sources': [{'source_id': 'dlu_oscar', 'path': str(root / 'oscars.csv'), 'revision': 'a' * 40,
                             'sha256': hashlib.sha256(raw).hexdigest(), 'license': 'BSD-2-Clause',
                             'redistribution_verified': True, 'first_ceremony': 1, 'last_ceremony': 1}],
                'expected_coverage': {'oscar': [1, 1]}, 'identity_mappings': mappings,
                'programs': [{'organization': 'oscar', 'ceremony': 1, 'ceremony_year': 1929,
                              'ceremony_date': '1929-05-16', 'expected_instances': ['ACTOR IN A LEADING ROLE'],
                              'evidence': {'revision': 'independent-program'},
                              'crosscheck': {'revision': 'independent-winners', 'crosscheck_agrees': True}}]}

    def test_identical_pinned_inputs_produce_identical_seed_and_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); inputs = self.inputs(root)
            owner = self.build_owner()
            one = owner.build_snapshot(inputs, overrides=[])
            two = owner.build_snapshot(inputs, overrides=[])
            self.assertTrue(one['ready'])
            self.assertEqual(one, two)
            self.assertEqual(one['seed']['ceremonies'][0]['films'], {'movie:imdb:tt0010101': 1})
            self.assertNotIn('categories', one['seed']['ceremonies'][0])

    def test_pinned_independent_winners_override_claimed_agreement_and_headers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for title, ready in [('First', True), ('Different film', False)]:
                inputs = self.inputs(root)
                raw = ("{{Infobox film awards|number=1\n|date=May 16, 1929\n}}\n{|\n"
                       "| {{Award category|#F9EFAA|[[Academy Award for Best Actor|Best Actor]]}}\n"
                       "* '''[[Person]]''' - ''[[" + title + "]]''\n|}").encode()
                (root / 'independent.wiki').write_bytes(raw)
                inputs['programs'][0]['independent_source'] = {
                    'source_id': 'annual_wikitext', 'organization': 'oscar', 'ceremony': 1,
                    'ceremony_year': 1929, 'revision': 'pinned-wiki', 'path': str(root / 'independent.wiki'),
                    'sha256': hashlib.sha256(raw).hexdigest()}
                result = self.build_owner().build_snapshot(inputs, overrides=[])
                self.assertEqual(result['ready'], ready)
                if not ready:
                    self.assertIn('conflicting_film_winners', result['audit'][0]['diagnostics'])
                else:
                    validation = result['seed']['ceremonies'][0]['validation']
                    self.assertEqual(validation['evidence']['revision'], 'pinned-wiki')
                    self.assertNotIn('independent_source', validation)

    def test_bad_independent_hash_cannot_fall_back_to_claimed_verified_program(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); inputs = self.inputs(root)
            (root / 'independent.wiki').write_bytes(b'changed')
            inputs['programs'][0]['independent_source'] = {
                'source_id': 'annual_wikitext', 'organization': 'oscar', 'ceremony': 1,
                'ceremony_year': 1929, 'revision': 'pinned-wiki', 'path': str(root / 'independent.wiki'),
                'sha256': '0' * 64}
            result = self.build_owner().build_snapshot(inputs, overrides=[])
            self.assertFalse(result['ready'])
            self.assertIn('pinned_source_hash_mismatch', result['audit'][0]['diagnostics'])

    def test_absent_program_and_identity_do_not_produce_partial_seed(self):
        with tempfile.TemporaryDirectory() as directory:
            inputs = self.inputs(Path(directory)); inputs['programs'] = []; inputs['identity_mappings'] = []
            result = self.build_owner().build_snapshot(inputs, overrides=[])
            self.assertFalse(result['ready'])
            self.assertIsNone(result['seed'])
            self.assertIn('missing_independent_program', result['audit'][0]['diagnostics'])
            self.assertGreater(result['unresolved_count'], 0)

    def test_hash_drift_missing_ceremony_and_unverified_license_block(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for change in ['hash', 'missing_year', 'license']:
                inputs = self.inputs(root)
                if change == 'hash': inputs['sources'][0]['sha256'] = '0' * 64
                if change == 'missing_year': inputs['expected_coverage']['oscar'] = [1, 2]
                if change == 'license': inputs['sources'][0]['redistribution_verified'] = False
                with self.subTest(change=change):
                    result = self.build_owner().build_snapshot(inputs, overrides=[])
                    self.assertFalse(result['ready'])
                    self.assertIsNone(result['seed'])

    def test_overlapping_primary_inputs_of_same_adapter_cannot_be_merged(self):
        with tempfile.TemporaryDirectory() as directory:
            inputs = self.inputs(Path(directory))
            inputs['sources'].append({**inputs['sources'][0], 'revision': 'b' * 40})
            result = self.build_owner().build_snapshot(inputs, overrides=[])
            self.assertFalse(result['ready'])
            self.assertIsNone(result['seed'])
            self.assertIn('overlapping_primary_sources', {x['reason'] for x in result['source_failures']})

    def test_declared_primary_group_combines_distinct_categories_but_rejects_duplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);inputs=self.inputs(root)
            fields=OSCAR_FIELDS
            rows=[{**oscar(category='DIRECTING'),'CanonicalCategory':'DIRECTING','Class':'Directing'}]
            raw=payload(fields,rows,'\t');(root/'directing.csv').write_bytes(raw)
            inputs['sources'][0]['primary_group']='complete-ceremony'
            inputs['sources'].append({**inputs['sources'][0],'path':str(root/'directing.csv'),'sha256':hashlib.sha256(raw).hexdigest(),'revision':'b'*40})
            inputs['programs'][0]['expected_instances'].append('DIRECTING')
            result=self.build_owner().build_snapshot(inputs,overrides=[])
            self.assertTrue(result['ready'])
            self.assertEqual(result['seed']['ceremonies'][0]['films'],{'movie:imdb:tt0010101':2})
            inputs['sources'].append({**inputs['sources'][1],'revision':'c'*40})
            result=self.build_owner().build_snapshot(inputs,overrides=[])
            self.assertFalse(result['ready'])
            self.assertIn('overlapping_primary_categories',{f['reason'] for f in result['source_failures']})

    def test_pinned_category_supplement_replaces_bad_block_and_hash_failure_cannot_fall_back(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); inputs = self.inputs(root)
            def annual(title, revision, name):
                raw = ("{{Infobox film awards|number=1\n|date=May 16, 1929\n}}\n{|\n"
                       "| {{Award category|#F9EFAA|[[Academy Award for Best Actor|Best Actor]]}}\n"
                       "* '''[[Person]]''' - ''[[" + title + "]]''\n|}").encode()
                (root / name).write_bytes(raw)
                return dict(source_id='annual_wikitext', organization='oscar', ceremony=1,
                    ceremony_year=1929, revision=revision, path=str(root / name), sha256=hashlib.sha256(raw).hexdigest())
            inputs['programs'][0]['independent_source'] = annual('Wrong film', 'annual-original', 'annual.wiki')
            supplement = {**annual('First', 'independent-review', 'reviewed.wiki'),
                          'replace_instances': ['ACTOR IN A LEADING ROLE']}
            inputs['programs'][0]['independent_supplements'] = [supplement]
            owner = self.build_owner(); result = owner.build_snapshot(inputs, overrides=[])
            self.assertTrue(result['ready'])
            supplement['sha256'] = '0' * 64
            result = owner.build_snapshot(inputs, overrides=[])
            self.assertFalse(result['ready'])
            self.assertIn('pinned_source_hash_mismatch', result['audit'][0]['diagnostics'])

    def test_pending_output_preserves_previously_verified_seed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); inputs = self.inputs(root)
            out = root / 'out'; out.mkdir(); (out / 'seed.json').write_bytes(b'previous verified seed')
            inputs['programs'] = []
            result = self.build_owner().build_snapshot(inputs, overrides=[])
            self.build_owner().write_build(out, result)
            self.assertEqual((out / 'seed.json').read_bytes(), b'previous verified seed')
            self.assertTrue((out / 'coverage-audit.json').exists())

    def test_reviewed_source_exclusion_does_not_publish_an_incomplete_organization(self):
        with tempfile.TemporaryDirectory() as directory:
            inputs = self.inputs(Path(directory))
            inputs['sources'][0]['excluded_ceremonies'] = [1]
            result = self.build_owner().build_snapshot(inputs, overrides=[])
            self.assertFalse(result['ready'])
            self.assertIn('missing_ceremony_source', result['audit'][0]['diagnostics'])

    def test_one_complete_organization_never_publishes_other_partial_totals(self):
        with tempfile.TemporaryDirectory() as directory:
            inputs = self.inputs(Path(directory)); inputs['expected_coverage']['golden_globe'] = [1, 83]
            result = self.build_owner().build_snapshot(inputs, overrides=[])
            self.assertTrue(result['ready'])
            self.assertEqual(result['coverage']['oscar']['status'], 'complete')
            self.assertEqual(result['coverage']['golden_globe']['status'], 'pending')
            self.assertEqual({c['organization'] for c in result['seed']['ceremonies']}, {'oscar'})

    def test_network_build_is_disabled_in_test_mode_and_live_output_is_rejected(self):
        owner = self.build_owner()
        with patch.dict('os.environ', {'CP_TEST_MODE': '1'}):
            with self.assertRaises(adapter().SourceError):
                owner._source_bytes({'url': 'https://raw.githubusercontent.com/example/input.csv'})
            with self.assertRaises(adapter().SourceError):
                owner.TMDbIdentityBridge(Path(__file__).parents[1] / 'config.json')
        with self.assertRaises(adapter().SourceError):
            owner.write_build(Path(__file__).parents[1] / 'data/awards', {'ready': False})

    def test_cli_returns_pending_without_emitting_seed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); inputs = self.inputs(root); inputs['programs'] = []
            (root / 'sources.json').write_text(json.dumps(inputs), encoding='utf-8')
            (root / 'overrides.json').write_text('{"overrides": []}', encoding='utf-8')
            with patch('sys.stdout', new_callable=io.StringIO):
                status = self.build_owner().main(['--output-root', str(root / 'out'),
                                                 '--sources-manifest', str(root / 'sources.json'),
                                                 '--identity-overrides', str(root / 'overrides.json')])
            self.assertEqual(status, 2)
            self.assertFalse((root / 'out/seed.json').exists())
            self.assertTrue((root / 'out/coverage-audit.json').exists())

    def test_rate_limit_response_keeps_exact_status_without_url_or_seed(self):
        with tempfile.TemporaryDirectory() as directory:
            inputs = self.inputs(Path(directory)); inputs['sources'][0].pop('path')
            inputs['sources'][0]['url'] = 'https://raw.githubusercontent.com/example/pinned.csv'
            error = urllib.error.HTTPError('https://example.org/private', 429, 'Too many requests', {}, None)
            with patch.dict('os.environ', {'CP_TEST_MODE': '0'}), patch('urllib.request.build_opener') as opener:
                opener.return_value.open.side_effect = error
                result = self.build_owner().build_snapshot(inputs, overrides=[])
            self.assertFalse(result['ready'])
            self.assertIsNone(result['seed'])
            self.assertEqual(result['source_failures'][0]['reason'], 'source_http_429')
            self.assertNotIn('private', json.dumps(result))

    def test_identity_credit_transport_uses_only_movie_domain_and_keeps_errors_safe(self):
        owner = self.build_owner()
        bridge = owner.TMDbIdentityBridge.__new__(owner.TMDbIdentityBridge)
        bridge._get_key = lambda:'fake-private-test-key'; bridge._cancelled=lambda:False; bridge._last_request = 0
        with patch('urllib.request.build_opener') as opener:
            opener.return_value.open.return_value.__enter__.return_value.read.return_value = b'{"cast":[{"id":20}],"crew":[]}'
            self.assertEqual(bridge.credits(10)['cast'][0]['id'],20)
            url=opener.return_value.open.call_args.args[0].full_url
            self.assertTrue(url.startswith('https://api.themoviedb.org/3/movie/10/credits?'))
            opener.return_value.open.side_effect = ValueError('fake-private-test-key in a secret URL')
            with self.assertRaises(adapter().SourceError) as error:
                bridge.credits(11)
            self.assertNotIn('fake-private',str(error.exception))


class OlderGlobeWinnerLayoutTests(unittest.TestCase):
    def parse(self, text):
        return adapter().parse_source('annual_wikitext',text.encode(),{'organization':'golden_globe','ceremony':6,'ceremony_year':1949,'revision':'pinned'})

    def test_explicit_tie_on_one_line_retains_both_films(self):
        text="== Winners ==\n=== [[Golden Globe Award for Best Motion Picture - Drama|Best Picture (tie)]] ===\n*''[[First]]'' directed by [[Director One]] and ''[[Second]]'' directed by [[Director Two]]"
        text=text.replace('Best Motion Picture - Drama','Best Motion Picture \u2013 Drama')
        wins=self.parse(text)
        self.assertEqual([r.title for r in wins[0].films],['First','Second'])

    def test_whole_line_italics_select_associated_film_instead_of_new_star_person(self):
        text="== Winners and nominees ==\n=== [[Golden Globe Award for New Star of the Year \u2013 Actor|New Star of the Year - Actor]] ===\n"+"'"*3+" ''[[Richard Todd]] in [[The Hasty Heart]]"+"'"*5+"\n*''[[Another Actor]] in [[A nomination]]''"
        wins=self.parse(text)
        self.assertEqual([r.title for r in wins[0].films],['The Hasty Heart'])
        self.assertEqual(wins[0].people,())


class HistoricalGlobeFieldContractTests(unittest.TestCase):
    def test_retired_foreign_categories_keep_film_title_separate_from_country_and_director(self):
        fields=['year_film','year_award','ceremony','category','nominee','film','win']
        for category,ceremony,title,country_and_director in [
            ('Foreign Film - English Language',6,'Hamlet (1948)','United Kingdom, Laurence Olivier'),
            ('Foreign Film - Foreign Language',14,'Before Sundown','West Germany, Gottfried Reinhardt'),
        ]:
            with self.subTest(category=category):
                raw=payload(fields,[{'year_film':str(ceremony+1942),'year_award':str(ceremony+1943),'ceremony':str(ceremony),'category':category,'nominee':country_and_director,'film':title,'win':'True'}])
                wins=adapter().parse_source('historical_globe',raw,{})
                self.assertEqual([r.title for r in wins[0].films],[title])
                self.assertEqual(wins[0].people,())

    def test_film_associated_special_uses_film_field_not_its_recipient(self):
        fields=['year_film','year_award','ceremony','category','nominee','film','win']
        raw=payload(fields,[{'year_film':'1945','year_award':'1946','ceremony':'3','category':'Promoting International Understanding','nominee':'Frank Sinatra','film':'The House I Live In','win':'True'}])
        wins=adapter().parse_source('historical_globe',raw,{})
        self.assertEqual([r.title for r in wins[0].films],['The House I Live In'])

    def test_foreign_film_title_is_nominee_even_when_film_field_contains_country_and_director(self):
        fields=['year_film','year_award','ceremony','category','nominee','film','win']
        raw=payload(fields,[{'year_film':'1949','year_award':'1950','ceremony':'7','category':'Best Motion Picture - Foreign Language','nominee':'The Bicycle Thief','film':'Italy, Vittorio De Sica','win':'True'}])
        wins=adapter().parse_source('historical_globe',raw,{})
        self.assertEqual([r.title for r in wins[0].films],['The Bicycle Thief'])


class AnnualTableDomainContractTests(unittest.TestCase):
    def test_plain_paired_film_subcategories_keep_their_distinct_winners(self):
        raw="""==Winners and nominees==
===Film===
{| class=wikitable
! colspan="2" |Best Motion Picture
|-
! style="width:50%;" |Drama
! style="width:50%;" |Musical or Comedy
|-
| valign="top" |
*'''''[[Winning Drama]]'''''
| valign="top" |
*'''''[[Winning Comedy]]'''''
|}
""".encode()
        wins=adapter().parse_source('annual_wikitext',raw,{'organization':'golden_globe','ceremony':64,'ceremony_year':2007,'revision':1})
        self.assertEqual([(w.award_instance,[f.title for f in w.films]) for w in wins], [('Best Motion Picture - Drama',['Winning Drama']),('Best Motion Picture - Musical or Comedy',['Winning Comedy'])])

    def test_anchor_decoration_cannot_truncate_plain_category_label(self):
        raw="""==Winners and nominees==
===Film===
{| class=wikitable
! {{anchor|Score}}Best Original Score – Motion Picture
|-
| valign="top" |
*'''''[[Winning Film]]''''' – [[Composer]]
|}
""".encode()
        wins=adapter().parse_source('annual_wikitext',raw,{'organization':'golden_globe','ceremony':64,'ceremony_year':2007,'revision':1})
        self.assertEqual([(w.award_instance,[f.title for f in w.films]) for w in wins], [('Best Original Score - Motion Picture',['Winning Film'])])

    def test_plain_category_header_in_explicit_film_section_retains_bold_winner_only(self):
        raw="""==Winners and nominees==
===Film===
{| class=wikitable
! Best Original Score – Motion Picture
|-
| valign="top" |
*'''''[[Winning Film]]''''' – [[Composer]]
*''[[Nominated Film]]'' – [[Other Composer]]
|}
""".encode()
        wins=adapter().parse_source('annual_wikitext',raw,{'organization':'golden_globe','ceremony':64,'ceremony_year':2007,'revision':1})
        self.assertEqual([(w.award_instance,[f.title for f in w.films]) for w in wins], [('Best Original Score - Motion Picture',['Winning Film'])])

    def test_television_section_cannot_become_movie_wins_through_incorrect_film_links(self):
        raw="""==Winners and nominees==
===Film===
{| class=wikitable
! [[Golden Globe Award for Best Motion Picture – Drama|Drama]]
|-
| valign="top" |
*'''''[[Winning Film]]'''''
|}
===Television===
{| class=wikitable
! [[Golden Globe Award for Best Motion Picture – Drama|Drama]]
|-
| valign="top" |
*'''''[[Winning TV Series]]'''''
|}
""".encode()
        wins=adapter().parse_source('annual_wikitext',raw,{'organization':'golden_globe','ceremony':39,'ceremony_year':1982,'revision':1})
        self.assertEqual([f.title for w in wins for f in w.films],['Winning Film'])


class CategoryWinnerTableTests(unittest.TestCase):
    def metadata(self):
        return {'organization':'golden_globe','revision':123,'url':'https://en.wikipedia.org/w/index.php?oldid=123',
                'award_header':'Golden Globe Award for New Star of the Year – Actress',
                'year_basis':'eligibility','film_column':'Film','person_column':None}

    def parse(self, rows, meta=None):
        raw=('''<table class="wikitable"><tr><td>‡</td><td><b>Indicates the winner</b></td></tr></table>
<table class="wikitable"><tr><th>Year</th><th>Actress</th><th>Role</th><th>Film</th></tr>'''+rows+'</table>').encode()
        return adapter().parse_source('category_html',raw,meta or self.metadata())

    def test_tied_winners_keep_inherited_ceremony_and_do_not_admit_nominees(self):
        rows='''<tr><th rowspan="3"><a href="/wiki/14th_Golden_Globes">1956 (14th)</a></th><td><b>One ‡</b></td><td>Role</td><td><b><a href="/wiki/First_(film)">First</a></b></td></tr>
<tr><td><b>Two ‡</b></td><td>Role</td><td><b><a href="/wiki/Second_(film)">Second</a></b></td></tr>
<tr><td>Nominee</td><td>Role</td><td><a href="/wiki/Nominated_(film)">Nominated</a></td></tr>'''
        wins=self.parse(rows)
        self.assertEqual([(w.ceremony,[f.title for f in w.films]) for w in wins],[(14,['First']),(14,['Second'])])
        self.assertTrue(all(w.people==() for w in wins))

    def test_rowspan_multi_film_win_preserves_every_film_without_role_leak(self):
        rows='''<tr><th rowspan="2"><a href="/wiki/11th_Golden_Globes">1953 (11th)</a></th><td rowspan="2"><b>One ‡</b></td><td>Role One</td><td><b><a href="/wiki/First_(film)">First</a></b></td></tr>
<tr><td>Role Two</td><td><b><a href="/wiki/Second_(film)">Second</a></b></td></tr>'''
        wins=self.parse(rows)
        self.assertEqual({f.title for w in wins for f in w.films},{'First','Second'})
        self.assertTrue(all(w.role is None and not w.people for w in wins))

    def test_missing_positive_winner_cannot_become_complete_empty_data(self):
        rows='''<tr><th><a href="/wiki/14th_Golden_Globes">1956 (14th)</a></th><td>Nominee</td><td>Role</td><td><a href="/wiki/First_(film)">First</a></td></tr>'''
        with self.assertRaises(adapter().SourceError):self.parse(rows)

    def test_academy_marker_on_a_globe_nominee_is_not_a_globe_win(self):
        rows='''<tr><th rowspan="2"><a href="/wiki/14th_Golden_Globes">1956 (14th)</a></th><td><b>Winner ‡</b></td><td>Role</td><td><b><a href="/wiki/First_(film)">First</a></b></td></tr>
<tr><td><b>Oscar winner †</b></td><td>Role</td><td><a href="/wiki/Nominated_(film)">Nominated</a></td></tr>'''
        self.assertEqual([f.title for w in self.parse(rows) for f in w.films],['First'])

    def test_reviewed_blue_winner_cells_keep_acting_identity_separate_from_nominees(self):
        metadata={**self.metadata(),'award_header':'Golden Globe Award for Best Actress in a Motion Picture – Drama',
                  'person_column':'Actress','winner_rule':'bold_blue_cells',
                  'winner_rule_evidence':{'revision':123,'source_url':self.metadata()['url']}}
        raw='''<table class="wikitable"><tr><th>Year</th><th>Actress</th><th>Role</th><th>Film</th></tr>
<tr><th rowspan="2">1956</th><td style="background:#B0C4DE;"><b><a href="/wiki/Ingrid_Bergman">Ingrid Bergman</a></b></td><td>Role</td><td style="background:#B0C4DE;"><b><a href="/wiki/Anastasia_(1956_film)">Anastasia</a></b></td></tr>
<tr><td><a href="/wiki/Nominee">Nominee</a></td><td>Role</td><td><a href="/wiki/Other_(film)">Other</a></td></tr></table>'''.encode()
        wins=adapter().parse_source('category_html',raw,metadata)
        self.assertEqual([(w.ceremony,w.role,[p.title for p in w.people],[f.title for f in w.films]) for w in wins],[(14,'actor',['Ingrid Bergman'],['Anastasia'])])

    def test_missing_reviewed_marker_proof_is_rejected(self):
        metadata={**self.metadata(),'winner_rule':'bold_blue_cells'}
        with self.assertRaises(adapter().SourceError):adapter().parse_source('category_html',b'<table class="wikitable"></table>',metadata)

    def test_colon_in_movie_title_is_not_a_wiki_namespace(self):
        rows='''<tr><th>1956</th><td><b>Winner ‡</b></td><td>Role</td><td><b><a href="/wiki/Film:_The_Sequel">Film: The Sequel</a></b><a href="/wiki/File:Poster.jpg">Poster</a></td></tr>'''
        self.assertEqual([f.title for w in self.parse(rows) for f in w.films],['Film: The Sequel'])

    def test_rendered_numeric_span_with_trailing_comma_preserves_ties(self):
        rows='''<tr><th rowspan="2,">1956</th><td><b>One ‡</b></td><td>Role</td><td><b><a href="/wiki/First_(film)">First</a></b></td></tr>
<tr><td><b>Two ‡</b></td><td>Role</td><td><b><a href="/wiki/Second_(film)">Second</a></b></td></tr>'''
        self.assertEqual([w.ceremony for w in self.parse(rows)],[14,14])

    def test_year_and_ordinal_disagreement_and_missing_legend_are_rejected(self):
        rows='''<tr><th><a href="/wiki/14th_Golden_Globes">1950 (14th)</a></th><td><b>One ‡</b></td><td>Role</td><td><b><a href="/wiki/First_(film)">First</a></b></td></tr>'''
        with self.assertRaises(adapter().SourceError):self.parse(rows)
        with self.assertRaises(adapter().SourceError):adapter().parse_source('category_html',b'<table class="wikitable"><tr><th>Year</th><th>Film</th></tr><tr><td>1956</td><td><b>First</b></td></tr></table>',self.metadata())


class CategoryHistoricalShapeTests(unittest.TestCase):
    metadata = CategoryWinnerTableTests.metadata
    def test_missing_trailing_reference_cell_cannot_displace_film(self):
        m={**self.metadata(),'award_header':'Golden Globe Award for Best Actress in a Motion Picture – Drama','person_column':'Actress'}
        raw='<table class="wikitable"><tr><td>‡ Indicates the winner</td></tr></table><table class="wikitable"><tr><th>Year</th><th>Actress</th><th>Film</th><th>Ref.</th></tr><tr><td>1956</td><td><b><a href="/wiki/Ingrid_Bergman">Ingrid Bergman</a> ‡</b></td><td><a href="/wiki/Anastasia_(1956_film)">Anastasia</a></td></tr></table>'
        self.assertEqual([f.title for w in adapter().parse_source('category_html',raw.encode(),m) for f in w.films],['Anastasia'])

    def test_year_footnote_and_category_banner_preserve_winner(self):
        raw='<table class="wikitable"><tr><td>‡ Indicates the winner</td></tr></table><table class="wikitable"><tr><th>Year<sup>1</sup></th><th>Film</th></tr><tr><th colspan="2">Historical category</th></tr><tr><td>1956</td><td><b><a href="/wiki/Anastasia_(1956_film)">Anastasia</a> ‡</b></td></tr></table>'
        self.assertEqual([w.ceremony for w in adapter().parse_source('category_html',raw.encode(),self.metadata())],[14])

    def test_parallel_picture_categories_keep_distinct_awards_and_nominees_out(self):
        m={**self.metadata(),'award_header':'Golden Globe Award for Best Motion Picture – Musical or Comedy','film_columns':{'Comedy':'Best Film - Comedy','Musical':'Best Film - Musical'},'winner_rule':'bold_blue_cells','winner_rule_evidence':{'revision':123,'source_url':self.metadata()['url']}}
        raw='<table class="wikitable"><tr><th>Year</th><th>Comedy</th><th>Musical</th></tr><tr><td rowspan="2">1958</td><td style="background:#B0C4DE"><b><a href="/wiki/Auntie_Mame_(film)">Auntie Mame</a></b></td><td style="background:#90EE90"><b><a href="/wiki/Gigi_(1958_film)">Gigi</a></b></td></tr><tr><td><a href="/wiki/Nominee">Nominee</a></td><td><a href="/wiki/Nominee_Two">Nominee Two</a></td></tr></table>'
        wins=adapter().parse_source('category_html',raw.encode(),m)
        self.assertEqual([(w.award_instance,[f.title for f in w.films]) for w in wins],[('Picture - Comedy',['Auntie Mame']),('Picture - Musical',['Gigi'])])

    def test_explicit_no_award_range_is_not_a_missing_positive_winner(self):
        rows='<tr><td>1953–1958</td><td colspan="3">No award given.</td></tr><tr><td>1959</td><td><b>Winner ‡</b></td><td>Role</td><td><a href="/wiki/Film">Film</a></td></tr>'
        self.assertEqual([w.ceremony for w in CategoryWinnerTableTests.parse(self,rows)],[17])

    def test_non_identity_terminal_colspan_does_not_displace_movie(self):
        m={**self.metadata(),'award_header':'Golden Globe Award for Best Original Song'}
        raw='<table class="wikitable"><tr><td>‡ Indicates the winner</td></tr></table><table class="wikitable"><tr><th>Year</th><th>Film</th><th>Song</th><th>Nominees</th></tr><tr><td>1969</td><td><b><a href="/wiki/Winning">Winning</a> ‡</b></td><td>Song</td><td colspan="2">Composers</td></tr><tr></tr></table>'
        self.assertEqual([f.title for w in adapter().parse_source('category_html',raw.encode(),m) for f in w.films],['Winning'])

    def test_reviewed_recipients_table_retains_films_and_ignores_explicit_no_award(self):
        m={**self.metadata(),'award_header':'Golden Globe Award for New Star of the Year – Actor','winner_rule':'recipient_tables','winner_table_headers':[['Year','Recipient(s)','Film']],'winner_rule_evidence':{'revision':123,'source_url':self.metadata()['url']}}
        raw='<table class="wikitable"><tr><th>Year</th><th>Recipient(s)</th><th>Film</th></tr><tr><td>1947</td><td>Richard Widmark</td><td><a href="/wiki/Kiss_of_Death_(1947_film)">Kiss of Death</a></td></tr><tr><td>1948</td><td colspan="2">No award</td></tr></table>'
        wins=adapter().parse_source('category_html',raw.encode(),m)
        self.assertEqual([(w.ceremony,w.people,[f.title for f in w.films]) for w in wins],[(5,(),['Kiss of Death'])])
        with self.assertRaises(adapter().SourceError):adapter().parse_source('category_html',raw.encode(),{**m,'winner_table_headers':[['Year','Actor','Film']]})

    def test_nonpersonal_recipient_is_retained_as_provenance_without_personal_win(self):
        m={**self.metadata(),'person_column':'Actress'}
        rows='<tr><td>1956</td><td><b><a href="/wiki/Taina_Elg">Taina Elg</a> ‡</b></td><td>Role</td><td><a href="/wiki/Les_Girls">Les Girls</a></td></tr>'
        win=CategoryWinnerTableTests.parse(self,rows,m)[0]
        self.assertEqual(win.people,())
        self.assertIsNone(win.role)
        self.assertEqual(win.evidence['named_recipients'],['Taina Elg'])

    def test_explicit_unlinked_winning_title_remains_unresolved_until_identity_proof(self):
        m={**self.metadata(),'allow_plain_film_titles':True}
        rows='<tr><th>1956</th><td><b>Winner ‡</b></td><td>Role</td><td>Unlinked Film</td></tr>'
        wins=CategoryWinnerTableTests.parse(self,rows,m)
        self.assertEqual([(f.title,f.imdb_id,f.tmdb_id) for w in wins for f in w.films],[('Unlinked Film',None,None)])


class HistoricalSupplementFieldTests(unittest.TestCase):
    def test_curated_csv_requires_record_proof_bound_to_its_exact_fields(self):
        fields=['year_film','year_award','ceremony','category','nominee','film','win']
        row=dict(year_film='1958',year_award='1959',ceremony='16',category='Samuel Goldwyn International Award',nominee='India, V. Shantaram',film='Do Ankhen Barah Haath (Two Eyes, Twelve Hands)',win='True')
        raw=payload(fields,[row]);meta={'source_origin':'reviewed_winner_facts','revision':'curation-1'}
        with self.assertRaises(adapter().SourceError):adapter().parse_source('historical_globe',raw,meta)
        proof={'source_url':'https://example.org/pinned','revision':'observed-hash','reason':'Reviewed positive winner and named film',
               'row_sha256':hashlib.sha256(json.dumps(row,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()}
        meta['row_evidence']={'2':proof}
        wins=adapter().parse_source('historical_globe',raw,meta)
        self.assertEqual(wins[0].evidence['source'],'reviewed_winner_facts')
        self.assertEqual(wins[0].evidence['reviewed_source'],proof)
        proof['row_sha256']='0'*64
        with self.assertRaises(adapter().SourceError):adapter().parse_source('historical_globe',raw,meta)

    def test_samuel_goldwyn_country_and_director_are_not_the_winning_movie(self):
        fields=['year_film','year_award','ceremony','category','nominee','film','win']
        raw=payload(fields,[dict(year_film='1958',year_award='1959',ceremony='16',category='Samuel Goldwyn International Award',nominee='India, V. Shantaram',film='Do Ankhen Barah Haath (Two Eyes, Twelve Hands)',win='True')])
        wins=adapter().parse_source('historical_globe',raw,{})
        self.assertEqual([f.title for w in wins for f in w.films],['Do Ankhen Barah Haath (Two Eyes, Twelve Hands)'])

    def test_special_citation_selects_associated_film_after_recipient(self):
        raw="== Winners ==\n=== Special Achievement Award ===\n"+"'"*3+" ''[[Walt Disney]]'' for artistic merit in [[The Living Desert]]"+"'"*3
        wins=adapter().parse_source('annual_wikitext',raw.encode(),{'organization':'golden_globe','ceremony':11,'ceremony_year':1954,'revision':123})
        self.assertEqual([f.title for w in wins for f in w.films],['The Living Desert'])

    def test_picture_display_categories_remain_distinct_despite_shared_award_link(self):
        text="== Winners ==\n=== [[Golden Globe Award for Best Motion Picture – Musical or Comedy|Best Motion Picture - Comedy]] ===\n"+"'"*5+"[[The Apartment]]"+"'"*5+"\n=== [[Golden Globe Award for Best Motion Picture – Musical or Comedy|Best Motion Picture - Musical]] ===\n"+"'"*5+"[[Song Without End]]"+"'"*5
        wins=adapter().parse_source('annual_wikitext',text.encode(),{'organization':'golden_globe','ceremony':18,'ceremony_year':1961,'revision':123})
        self.assertEqual([(w.award_instance,[f.title for f in w.films]) for w in wins],[('Picture - Comedy',['The Apartment']),('Picture - Musical',['Song Without End'])])


class RetiredOutdoorAndSpecialContractTests(unittest.TestCase):
    def test_outdoor_drama_counts_named_film_without_director_personal_win(self):
        fields=['year_film','year_award','ceremony','category','nominee','film','win']
        raw=payload(fields,[dict(year_film='1955',year_award='1956',ceremony='13',category='Best Outdoor Drama',nominee='Wichita',film='',win='True')])
        win=adapter().parse_source('historical_globe',raw,{})[0]
        self.assertEqual((win.award_instance,win.scope,win.role,[f.title for f in win.films],win.people),('Best Motion Picture - Outdoor Drama','film',None,['Wichita'],()))

    def test_special_career_honor_has_no_film_or_personal_credit(self):
        fields=['year_film','year_award','ceremony','category','nominee','film','win']
        raw=payload(fields,[dict(year_film='1958',year_award='1959',ceremony='16',category='Special Achievement Award',nominee='Shirley MacLaine',film='',win='True')])
        win=adapter().parse_source('historical_globe',raw,{})[0]
        self.assertEqual((win.scope,win.films,win.people),('career',(),()))
