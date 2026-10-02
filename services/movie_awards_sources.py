"""Pure movie-award adapters and validation. No network, persistence or UI work.

An award instance counts once for each winning film and eligible recipient.
Identity resolution is a separate step; unknown identifiers never become guesses.
"""
from __future__ import annotations

import ast
import csv
import hashlib
import html
import io
import json
import re
import urllib.parse
from html.parser import HTMLParser
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path


class SourceError(ValueError):
    """Candidate source cannot safely supply a complete contribution."""


@dataclass(frozen=True)
class EntityReference:
    namespace: str
    title: str
    imdb_id: str | None = None
    tmdb_id: int | None = None
    evidence: tuple = ()

    @property
    def entity_id(self):
        if self.imdb_id:
            return f'{self.namespace}:imdb:{self.imdb_id}'
        if self.tmdb_id:
            return f'{self.namespace}:tmdb:{self.tmdb_id}'
        raise SourceError(f'unresolved_identity: {self.namespace} {self.title}')


@dataclass(frozen=True)
class NormalizedWin:
    organization: str
    ceremony: int
    ceremony_year: int
    award_instance: str
    category: str
    scope: str
    role: str | None
    films: tuple[EntityReference, ...]
    people: tuple[EntityReference, ...]
    evidence: dict


@dataclass(frozen=True)
class CeremonyProgram:
    organization: str
    ceremony: int
    ceremony_year: int
    ceremony_date: date
    expected_instances: tuple[str, ...]
    evidence: dict


@dataclass(frozen=True)
class ValidationReport:
    complete: bool
    diagnostics: tuple[str, ...]
    evidence: dict


@dataclass(frozen=True)
class PersonWin:
    person: str
    role: str
    award_instance: str
    category: str
    films: tuple[str, ...]
    evidence: tuple[dict, ...]


@dataclass(frozen=True)
class CeremonyContribution:
    organization: str
    ceremony: int
    ceremony_year: int
    films: dict[str, int]
    person_wins: tuple[PersonWin, ...]


def _taxonomy(manifest):
    supplied = manifest.get('taxonomy')
    if supplied is not None:
        return supplied
    path = Path(__file__).resolve().parents[1] / 'static/movie-awards/category-taxonomy.json'
    return json.loads(path.read_text(encoding='utf-8'))['sources']


def _rule(source, category, manifest):
    rule = _taxonomy(manifest).get(source, {}).get(category)
    if not rule:
        raise SourceError(f'unknown_category: {source}: {category}')
    return rule


def _subjects(manifest):
    supplied = manifest.get('subjects')
    if supplied is None:
        path = Path(__file__).resolve().parents[1] / 'static/movie-awards/category-taxonomy.json'
        supplied = json.loads(path.read_text(encoding='utf-8')).get('subjects', [])
    result = {}
    for subject in supplied:
        identifier, kind = subject.get('imdb_id'), subject.get('kind')
        evidence = subject.get('evidence', {})
        aliases = subject.get('source_aliases', [])
        key = identifier or tuple(tuple(alias.get(k) for k in ('source', 'ceremony', 'category', 'title')) for alias in aliases)
        if ((identifier and not re.fullmatch(r'tt\d+', identifier)) or not key or
                kind not in ('film_series', 'studio', 'body_of_work', 'character', 'person_group') or
                any(not all(alias.get(k) for k in ('source', 'ceremony', 'category', 'title')) for alias in aliases) or
                not evidence.get('source_url') or not evidence.get('revision') or
                key in result):
            raise SourceError('invalid_subject_classification')
        result[key] = subject
    return result


def _winning_scope(rule, films, evidence, subjects):
    collective = []
    for film in films:
        subject = subjects.get(film.imdb_id)
        if subject is None:
            matches = [item for item in subjects.values() for alias in item.get('source_aliases', [])
                       if alias.get('title') == film.title and all(alias.get(k) == evidence.get(k)
                                                                 for k in ('source', 'ceremony', 'category'))]
            if len(matches) > 1:
                raise SourceError('subject_alias_conflict')
            subject = matches[0] if matches else None
        if subject:
            collective.append(subject)
    scope = rule['scope']
    if collective:
        if scope != 'film_if_associated' or len(collective) != len(films):
            raise SourceError('subject_category_conflict')
        evidence['subject_classifications'] = collective
        evidence['exclusion_reason'] = 'collective'
        return 'other'
    return ('film' if films else 'career') if scope == 'film_if_associated' else scope


def _winner(value, row):
    if value not in ('True', 'False'):
        raise SourceError(f'ambiguous_winner_marker: row {row}')
    return value == 'True'


def _arrays(value):
    if not value:
        return []
    if len(value) > 32768:
        raise SourceError('array_limit_exceeded')
    if not value.startswith('['):
        return [value]
    try:
        result = ast.literal_eval(value)
    except (ValueError, SyntaxError, RecursionError) as exc:
        raise SourceError('malformed_literal_array') from exc
    if not isinstance(result, list) or len(result) > 256 or any(not isinstance(x, str) for x in result):
        raise SourceError('malformed_literal_array')
    return result


def _refs(namespace, titles, ids, evidence):
    prefix = 'tt' if namespace == 'movie' else 'nm'
    # Companies receiving film awards are not eligible personal acting wins.
    result = []
    for index in range(max(len(titles), len(ids))):
        title = titles[index] if index < len(titles) else ''
        identifier = ids[index] if index < len(ids) else ''
        if identifier and identifier != '?' and not re.fullmatch(prefix + r'\d+', identifier):
            if namespace == 'person' and identifier.startswith('co'):
                continue
            raise SourceError(f'invalid_{namespace}_identifier: {identifier}')
        result.append(EntityReference(namespace, title, identifier if identifier != '?' and identifier else None,
                                      evidence=(evidence,)))
    return tuple(result)


def parse_source(source_id: str, payload: bytes, manifest: dict) -> list[NormalizedWin]:
    if len(payload) > 40 * 1024 * 1024:
        raise SourceError('payload_limit_exceeded')
    manifest = {**manifest, 'taxonomy': _taxonomy(manifest)}
    if source_id == 'annual_wikitext':
        return _parse_annual(payload, manifest)
    if source_id == 'category_html':
        return _parse_category_html(payload, manifest)
    required = {
        'dlu_oscar': {'Ceremony', 'Year', 'Category', 'Film', 'FilmId', 'NomineeIds', 'Winner'},
        'historical_globe': {'year_film', 'year_award', 'ceremony', 'category', 'nominee', 'film', 'win'},
        'modern_globe': {'eventId', 'year', 'awardName', 'categoryName', 'primaryNomineeName',
                         'primaryNomineeCode', 'secondaryNomineeName', 'secondaryNomineeCode', 'isWinner'},
    }
    if source_id not in required:
        raise SourceError(f'unsupported_source: {source_id}')
    subjects = _subjects(manifest)
    try:
        reader = csv.DictReader(io.StringIO(payload.decode('utf-8-sig')), delimiter='\t' if source_id == 'dlu_oscar' else ',')
        if not required[source_id].issubset(reader.fieldnames or []):
            raise SourceError('source_schema_mismatch')
        wins = []
        for line, row in enumerate(reader, 2):
            if None in row:
                raise SourceError(f'extra_columns: row {line}')
            if source_id == 'modern_globe' and (row['eventId'] != 'ev0000292' or row['awardName'] != 'Golden Globe'):
                continue
            category = row['Category'] if source_id == 'dlu_oscar' else row['category'] if source_id == 'historical_globe' else row['categoryName']
            rule = _rule(source_id, category, manifest)
            marker = row.get('Winner', row.get('win', row.get('isWinner')))
            # This pinned Oscar format uses blank/truncated trailing cells for
            # nominees. Only its literal True is a win; other feeds are strict.
            is_winner = False if source_id == 'dlu_oscar' and marker in ('', None) else _winner(marker, line)
            if not is_winner:
                continue
            evidence = {'source': source_id, 'row': line, 'revision': manifest.get('revision'), 'category': category}
            if manifest.get('source_origin'):
                proof = manifest.get('row_evidence', {}).get(str(line), {})
                digest = hashlib.sha256(json.dumps(row, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
                if not all(proof.get(field) for field in ('source_url', 'revision', 'reason')) or proof.get('row_sha256') != digest:
                    raise SourceError('missing_or_mismatched_reviewed_record_proof')
                evidence.update(source=manifest['source_origin'], reviewed_source=proof)
            if source_id == 'dlu_oscar':
                ceremony = int(row['Ceremony'])
                # 1=1929, 2=1930, 3=1930; the 6th ceremony honored 1932/33.
                year = ceremony + (1928 if ceremony < 3 else 1927 if ceremony < 6 else 1928)
                early_eligibility = {1: '1927/28', 2: '1928/29', 3: '1929/30', 4: '1930/31', 5: '1931/32', 6: '1932/33'}
                if row['Year'] != early_eligibility.get(ceremony, str(ceremony + 1927)):
                    raise SourceError(f'eligibility_year_mismatch: row {line}')
                organization = 'oscar'
                evidence.update(eligibility_year=row['Year'],
                                credit_names=(row.get('Nominees') or row.get('Name') or '').split('|'))
                films = _refs('movie', row['Film'].split('|') if row['Film'] else [], row['FilmId'].split('|') if row['FilmId'] else [], evidence)
                people = _refs('person', (row.get('Nominees') or row.get('Name') or '').split('|'), row['NomineeIds'].split('|') if row['NomineeIds'] else [], evidence) if rule.get('role') else ()
            elif source_id == 'historical_globe':
                ceremony, year, organization = int(row['ceremony']), int(row['year_award']), 'golden_globe'
                if year != ceremony + 1943:
                    raise SourceError(f'ceremony_year_mismatch: row {line}')
                title = row['nominee'] if rule.get('film_in_nominee') else row['film']
                evidence.update(eligibility_year=row['year_film'],
                                credit_names=[] if rule.get('film_in_nominee') else [row['nominee']])
                films = _refs('movie', [title] if title else [], [], evidence)
                people = _refs('person', [row['nominee']], [], evidence) if rule.get('role') else ()
            else:
                year, organization = int(row['year']), 'golden_globe'
                ceremony = year - 1943
                names = _arrays(row['primaryNomineeName']) + _arrays(row['secondaryNomineeName'])
                identifiers = _arrays(row['primaryNomineeCode']) + _arrays(row['secondaryNomineeCode'])
                if len(names) != len(identifiers):
                    raise SourceError(f'array_length_mismatch: row {line}')
                if any(identifier != '?' and not re.fullmatch(r'(tt|nm|co)\d+', identifier) for identifier in identifiers):
                    raise SourceError(f'invalid_nominee_identifier: row {line}')
                evidence.update(eligibility_year=str(year - 1),
                                credit_names=[n for n, i in zip(names, identifiers) if i.startswith('nm')])
                films = _refs('movie', [n for n, i in zip(names, identifiers) if i.startswith('tt') or i == '?'],
                              [i for i in identifiers if i.startswith('tt') or i == '?'], evidence)
                people = _refs('person', [n for n, i in zip(names, identifiers) if i.startswith('nm')],
                               [i for i in identifiers if i.startswith('nm')], evidence) if rule.get('role') else ()
            if ceremony < 1 or year < 1929:
                raise SourceError(f'invalid_ceremony: row {line}')
            evidence.update(organization=organization, ceremony=ceremony, ceremony_year=year, role=rule.get('role'))
            evidence.update(winning_films=[f.title for f in films], winning_people=[p.title for p in people])
            scope = _winning_scope(rule, films, evidence, subjects)
            if scope != 'film':
                films, people = (), ()
            wins.append(NormalizedWin(organization, ceremony, year, rule.get('instance', category),
                                      rule.get('category', category), scope, rule.get('role'), films, people, evidence))
        return wins
    except (UnicodeError, csv.Error, KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, SourceError):
            raise
        raise SourceError(f'malformed_source: {type(exc).__name__}') from exc


def validate_ceremony(wins: list[NormalizedWin], program: CeremonyProgram, evidence: dict) -> ValidationReport:
    diagnostics = []
    included = [w for w in wins if w.scope == 'film']
    if any((w.organization, w.ceremony, w.ceremony_year) != (program.organization, program.ceremony, program.ceremony_year) for w in wins):
        diagnostics.append('ceremony_mismatch')
    instances = {w.award_instance for w in included}
    if set(program.expected_instances) - instances:
        diagnostics.append('missing_winners')
    if instances - set(program.expected_instances):
        diagnostics.append('unexpected_award_instances')
    try:
        if date.fromisoformat(evidence.get('as_of', '')) <= program.ceremony_date:
            diagnostics.append('ceremony_not_past')
    except ValueError:
        diagnostics.append('missing_as_of_date')
    if not program.expected_instances or not program.evidence.get('revision'):
        diagnostics.append('missing_independent_program')
    if evidence.get('crosscheck_agrees') is not True or not evidence.get('revision'):
        diagnostics.append('missing_or_conflicting_crosscheck')
    by_instance = defaultdict(set)
    for win in included:
        if not win.films or (win.role and not win.people):
            diagnostics.append('missing_winning_identity')
        for ref in win.films + win.people:
            if not (ref.imdb_id or ref.tmdb_id):
                diagnostics.append('unresolved_identity')
        for ref in win.films:
            try:
                by_instance[win.award_instance].add(ref.entity_id)
            except SourceError:
                pass
    for instance, films in by_instance.items():
        if len(films) > 1 and instance not in evidence.get('ties', []) and instance not in evidence.get('multi_film_awards', []):
            diagnostics.append('missing_tie_or_multi_film_evidence')
    return ValidationReport(not diagnostics, tuple(sorted(set(diagnostics))), dict(evidence))


def aggregate_ceremony(wins: list[NormalizedWin]) -> CeremonyContribution:
    if not wins:
        raise SourceError('empty_ceremony')
    identity = {(w.organization, w.ceremony, w.ceremony_year) for w in wins}
    if len(identity) != 1:
        raise SourceError('mixed_ceremonies')
    film_instances = defaultdict(set)
    personal = {}
    for win in wins:
        if win.scope != 'film':
            continue
        if not win.films or (win.role and not win.people):
            raise SourceError('missing_winning_identity')
        films = tuple(sorted({f.entity_id for f in win.films}))
        for film in films:
            film_instances[film].add(win.award_instance)
        if win.role in ('actor', 'director'):
            for person in win.people:
                key = (person.entity_id, win.role, win.award_instance)
                entry = personal.setdefault(key, {'category': win.category, 'films': set(), 'evidence': []})
                entry['films'].update(films)
                entry['evidence'].append(win.evidence)
    organization, ceremony, year = next(iter(identity))
    return CeremonyContribution(organization, ceremony, year,
        {film: len(keys) for film, keys in sorted(film_instances.items())},
        tuple(PersonWin(person, role, instance, item['category'], tuple(sorted(item['films'])), tuple(item['evidence']))
              for (person, role, instance), item in sorted(personal.items())))


def _italic_links(line):
    """Track wiki italics; bold recipient links are not film titles."""
    italic, links, segment_start, linked_segment = False, [], 0, False
    for match in re.finditer(r"'{2,}|\[\[([^\]]+)\]\]", line):
        if match[1] is None:
            count = len(match[0])
            if count in (2, 5):
                if italic and not linked_segment:
                    title = line[segment_start:match.start()].strip()
                    if title and not any(mark in title for mark in ('[[', '{{', '<', ']]', '}}')):
                        links.append((title, segment_start))
                italic = not italic
                segment_start, linked_segment = match.end(), False
            elif count != 3:
                raise SourceError('unsupported_annual_formatting')
        elif italic:
            links.append((match[1], match.start()))
            linked_segment = True
    return links


class _CategoryTables(HTMLParser):
    """Collect cells and explicit markup; reconstruct spans separately."""
    def __init__(self):
        super().__init__()
        self.depth = 0
        self.tables = []
        self.table = self.row = self.cell = self.link = None
        self.bold = 0
        self.sup = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'table':
            self.depth += 1
            if self.depth == 1 and 'wikitable' in attrs.get('class', '').split():
                self.table = []
        if self.depth != 1 or self.table is None:
            return
        if tag == 'tr':
            self.row = []
        if tag in ('td', 'th'):
            self.cell = {'tag': tag, 'attrs': attrs, 'text': '', 'links': [], 'bold': False}
            self.bold = 0
        if self.cell is not None:
            if tag == 'sup':
                self.sup += 1
            if tag in ('b', 'strong'):
                self.bold += 1
                self.cell['bold'] = True
            if tag == 'a' and attrs.get('href', '').startswith('/wiki/'):
                self.link = {'target': urllib.parse.unquote(attrs['href'][6:]).replace('_', ' '), 'title': ''}
                self.cell['links'].append(self.link)

    def handle_endtag(self, tag):
        if self.depth == 1 and self.table is not None:
            if tag == 'sup':
                self.sup = max(0, self.sup - 1)
            if tag in ('b', 'strong'):
                self.bold = max(0, self.bold - 1)
            if tag == 'a':
                self.link = None
            if tag in ('td', 'th') and self.cell is not None:
                if self.row is None:
                    raise SourceError('category_cell_outside_row')
                self.row.append(self.cell)
                self.cell = self.link = None
            if tag == 'tr' and self.row is not None:
                self.table.append(self.row)
                self.row = None
        if tag == 'table':
            if self.depth == 1 and self.table is not None:
                self.tables.append(self.table)
                self.table = None
            self.depth -= 1

    def handle_data(self, data):
        if self.cell is not None and not self.sup:
            self.cell['text'] += data
            if self.link is not None:
                self.link['title'] += data


def _category_grid(table):
    carry = {}
    for row in table:
        expanded, upcoming, column = [], {}, 0
        for cell in row:
            while column in carry:
                remaining, inherited = carry[column]
                expanded.append(inherited)
                if remaining > 1:
                    upcoming[column] = (remaining - 1, inherited)
                column += 1
            try:
                rowspan = int(str(cell['attrs'].get('rowspan', 1)).removesuffix(','))
                colspan = int(str(cell['attrs'].get('colspan', 1)).removesuffix(','))
            except ValueError as exc:
                raise SourceError('invalid_category_span') from exc
            if not (1 <= rowspan <= 1000 and 1 <= colspan <= 20):
                raise SourceError('invalid_category_span')
            for _ in range(colspan):
                if column in carry:
                    raise SourceError('overlapping_category_span')
                expanded.append(cell)
                if rowspan > 1:
                    upcoming[column] = (rowspan - 1, cell)
                column += 1
        while column in carry:
            remaining, inherited = carry[column]
            expanded.append(inherited)
            if remaining > 1:
                upcoming[column] = (remaining - 1, inherited)
            column += 1
        if any(index >= column for index in carry):
            raise SourceError('incomplete_category_row')
        carry = upcoming
        yield expanded


def _parse_category_html(payload, manifest):
    if (manifest.get('organization') != 'golden_globe' or not manifest.get('revision')
            or not manifest.get('url') or manifest.get('year_basis') not in ('eligibility', 'ceremony')):
        raise SourceError('missing_category_provenance')
    category, rule = _annual_rule(manifest.get('award_header', ''), manifest)
    parser = _CategoryTables()
    parser.feed(payload.decode('utf-8'))
    legend_rows = [row for table in parser.tables for row in table
                   if any('indicates the winner' in cell['text'].casefold() for cell in row)]
    marker_proof = manifest.get('winner_rule_evidence', {})
    reviewed_marker = (marker_proof.get('revision') == manifest['revision']
                       and marker_proof.get('source_url') == manifest['url'])
    reviewed_blue = manifest.get('winner_rule') == 'bold_blue_cells' and reviewed_marker
    reviewed_recipients = manifest.get('winner_rule') == 'recipient_tables' and reviewed_marker
    if not legend_rows and not (reviewed_blue or reviewed_recipients):
        raise SourceError('missing_category_winner_legend')
    winner_markers = {marker for row in legend_rows for cell in row for marker in ('‡', '†')
                      if marker in cell['text']}
    wins, seen, winning = [], set(), set()
    film_columns = {manifest['film_column']: manifest.get('award_header'), **manifest.get('film_columns', {})}
    for table in parser.tables:
        headers = None
        for row in _category_grid(table):
            labels = [cell['text'].strip() for cell in row]
            if 'Year' in labels and any(column in labels for column in film_columns):
                headers = labels
                continue
            if headers is None:
                continue
            if not row or (len(row) == 1 and row[0]['attrs'].get('rowspan')):
                continue
            # A spanning category banner contains no result cells. Some pinned
            # tables omit their optional trailing reference cell; identity
            # columns must still be present at their declared positions.
            if row and all(cell is row[0] for cell in row) and int(row[0]['attrs'].get('colspan', 1)) == len(headers):
                continue
            if len(row) == len(headers) - 1 and headers[-1] == 'Ref.':
                row = row + [{'text': '', 'links': [], 'bold': False, 'attrs': {}}]
            if len(row) > len(headers) and headers[-1] in ('Nominees', 'Country') and all(cell is row[len(headers)-1] for cell in row[len(headers)-1:]):
                row = row[:len(headers)]
            if len(row) != len(headers):
                raise SourceError('ambiguous_category_columns')
            year_cell = row[headers.index('Year')]
            if any(re.fullmatch(r'No award(?: given)?\.?', cell['text'].strip(), re.I) for cell in row if cell is not year_cell):
                continue
            year_match = re.search(r'\b(19\d\d|20\d\d)\b', year_cell['text'])
            if not year_match:
                raise SourceError('missing_category_year')
            year = int(year_match[1])
            ceremony = year - (1942 if manifest['year_basis'] == 'eligibility' else 1943)
            ordinal = {int(m[1]) for link in year_cell['links']
                       if (m := re.match(r'(\d+)(?:st|nd|rd|th) Golden Globe(?:s| Awards)', link['target']))}
            if ceremony < 1 or (ordinal and ordinal != {ceremony}):
                raise SourceError('category_year_ordinal_mismatch')
            active_columns = [(column, _annual_rule(header, manifest)) for column, header in film_columns.items() if column in headers]
            recipients_table = reviewed_recipients and headers in manifest.get('winner_table_headers', [])
            for column, (category, rule) in active_columns:
                seen.add((ceremony, rule.get('instance', category)))
            # A positive source marker is required on a subject cell. Bold year
            # headings and ordinary nominated film links cannot elect a winner.
                subject_cells = ([row[headers.index(column)]] if len(active_columns) > 1 else
                                 [cell for index, cell in enumerate(row) if index != headers.index('Year')])
                if not recipients_table and not any(cell['bold'] and (any(marker in cell['text'] for marker in winner_markers) or
                       re.search(r'background(?:-color)?\s*:\s*(?:lightyellow|#faeb86|#ffffcc|#b0c4de)',
                                 cell['attrs'].get('style', ''), re.I) or
                       (column in manifest.get('film_columns', {}) and re.search(r'background(?:-color)?\s*:\s*#90ee90', cell['attrs'].get('style', ''), re.I))) for cell in subject_cells):
                    continue
                film_cell = row[headers.index(column)]
                evidence = {'source': 'category_html', 'revision': manifest['revision'],
                        'source_url': manifest['url'], 'category': category,
                        'organization': 'golden_globe', 'ceremony': ceremony,
                        'ceremony_year': ceremony + 1943, 'role': rule.get('role'),
                        'winner_marker': 'explicit_category_table_marker'}

                def references(cell, namespace):
                    links = [link for link in cell['links'] if not re.match(
                    r'(?:File|Image|Category|Template|Help|Wikipedia|Talk):', link['target'], re.I)]
                    return tuple(EntityReference(namespace, link['title'].strip() or link['target'],
                             evidence=({**evidence, 'wiki_target': link['target']},)) for link in links)

                films = references(film_cell, 'movie')
                if not films and manifest.get('allow_plain_film_titles') is True and film_cell['text'].strip() and not film_cell['links']:
                    films = (EntityReference('movie', film_cell['text'].strip(), evidence=(evidence,)),)
                if not films:
                    raise SourceError('missing_category_winning_film_link')
                person_column = manifest.get('person_column')
                if rule.get('role') and person_column not in headers:
                    raise SourceError('missing_category_recipient_column')
                people = references(row[headers.index(person_column)], 'person') if rule.get('role') else ()
                if rule.get('role') and not people:
                    raise SourceError('missing_category_winning_person_link')
                evidence['named_recipients'] = [ref.title for ref in references(row[headers.index(person_column)], 'person')] if person_column in headers else []
                evidence.update(winning_films=[film.title for film in films], winning_people=[person.title for person in people])
                films = tuple(EntityReference(f.namespace, f.title, evidence=({**f.evidence[0], **evidence},)) for f in films)
                people = tuple(EntityReference(f.namespace, f.title, evidence=({**f.evidence[0], **evidence},)) for f in people)
                wins.append(NormalizedWin('golden_globe', ceremony, ceremony + 1943,
                        rule.get('instance', category), rule.get('category', category), 'film',
                        rule.get('role'), films, people, evidence))
                winning.add((ceremony, rule.get('instance', category)))
    if not wins or seen != winning:
        raise SourceError('missing_category_positive_winner')
    return wins


def _annual_blocks(payload, manifest):
    """Explicit category tables and early Winners sections, never captions.

    Wiki links are source aliases, never TMDb identity evidence. The resolver
    must verify every selected film/person before this source can be published.
    """
    text = html.unescape(payload.decode('utf-8'))
    if text.lstrip().upper().startswith('#REDIRECT'):
        raise SourceError('unresolved_redirect')
    organization = manifest.get('organization')
    if organization not in ('oscar', 'golden_globe') or not manifest.get('revision'):
        raise SourceError('missing_annual_manifest')
    text = re.sub(r'<ref\b[^>]*?/>|<ref\b[^>]*>.*?</ref>', '', text, flags=re.S)
    tables = re.finditer(r'^\{\|.*?^\|}[^\n]*$', text, re.M | re.S)
    domains = [(heading.end(), heading[2].strip().casefold())
               for heading in re.finditer(r'^(={2,3})\s*(Film|Television(?: awards)?)\s*\1\s*$', text, re.M | re.I)]
    blocks = []
    for table_match in tables:
        domain = next((label for end, label in reversed(domains) if end < table_match.start()), None)
        if organization == 'golden_globe' and domain and domain.startswith('television'):
            continue
        table = table_match[0]
        headers = list(re.finditer(r'\{\{Award\s*[Cc]ategory\|[^|\n]+\|(.+?)\}\}', table, re.S))
        for index, match in enumerate(headers):
            body = table[match.end():headers[index + 1].start() if index + 1 < len(headers) else len(table)]
            blocks.append((match[1], body, False))
        if headers:
            continue
        if (('[[Golden Globe Award for ' not in table and not (organization == 'golden_globe' and domain == 'film')) or
                not re.search(r"^\*(?!\*)\s*'''|^\|[^\n]*\|\s*'''|^'''", table, re.M)):
            continue
        # Older Golden Globe tables have two separate category header cells,
        # followed by two data cells. A full award target disambiguates labels
        # such as "Actor" or "Drama" without borrowing the other column.
        active, parent = [], ''
        for row in re.split(r'\n\|-.*\n', table):
            header_cells = re.split(r'\n!|!!', '\n' + row)[1:]
            if header_cells:
                categories = []
                for cell in header_cells:
                    links = re.findall(r'\[\[(Golden Globe Award for [^\]]+)\]\]', cell)
                    label = re.sub(r'\{\{anchor\|[^{}]+\}\}', '', cell, flags=re.I)
                    label = re.sub(r'^[^\[\n]*\|', '', label).strip()
                    qualified = parent + ' :: ' + label
                    if not links and qualified in _taxonomy(manifest).get('annual_' + organization, {}):
                        label = qualified
                    categories.append(links[0] if links else label)
                if len(header_cells) == 1 and re.search(r'colspan\s*=\s*"?2', header_cells[0]):
                    parent = categories[0]
                active = categories
                continue
            data_cells = re.split(r'\n\|(?![-}])|\|\|', '\n' + row)[1:]
            if active and data_cells:
                if len(data_cells) != len(active):
                    raise SourceError('ambiguous_annual_columns')
                for header, body in zip(active, data_cells):
                    body = re.sub(r'^\s*(?:[a-zA-Z]+\s*=\s*(?:"[^"]*"|[^\s|]+)\s*)+\|\s*', '', body)
                    if header or re.search(r'^\*(?!\*)\s*\S', body, re.M):
                        blocks.append((header, body, False))
                active = []
    if not blocks and organization == 'golden_globe':
        sections = list(re.finditer(r'^==\s*(Winners?(?: and [Nn]ominees)?|Film)\s*==\s*\n(.*?)(?=^==[^=]|\Z)', text, re.M | re.S))
        for section in sections:
            headers = list(re.finditer(r'^(={3,5})\s*(.*?)\s*\1\s*$', section[2], re.M))
            for index, match in enumerate(headers):
                body = section[2][match.end():headers[index + 1].start() if index + 1 < len(headers) else len(section[2])]
                if not re.search(r"^(?:\*(?!\*)\s*|''\s+)?'''|^\*(?!\*)\s*\S", body, re.M):
                    continue
                blocks.append((match[2], body, section[1] in ('Winner', 'Winners')))
    if organization == 'oscar':
        headers = list(re.finditer(r'^(={2,5})\s*(.*?)\s*\1\s*$', text, re.M))
        rules = _taxonomy(manifest).get('annual_oscar', {})
        for index, match in enumerate(headers):
            label = re.sub(r'\[\[([^\]]+)\]\]', lambda m: m[1].split('|')[-1], match[2])
            if rules.get(label, {}).get('section_winners'):
                body = text[match.end():headers[index + 1].start() if index + 1 < len(headers) else len(text)]
                blocks.append((label, body, True))
        # A definition-list heading is another explicit award heading used by
        # older ceremony records. Ignore bibliography headings such as Notes.
        headings = list(re.finditer(r'^;\s*(.+)$', text, re.M))
        for index, match in enumerate(headings):
            if 'award' not in match[1].casefold():
                continue
            label = match[1].strip()
            _annual_rule(label, manifest)  # Unknown awards keep the source pending.
            body = text[match.end():headings[index + 1].start() if index + 1 < len(headings) else len(text)]
            body = re.split(r'^={2,5}[^=]', body, maxsplit=1, flags=re.M)[0]
            blocks.append((label, body, True))
    if not blocks:
        raise SourceError('unsupported_annual_layout')
    return blocks


def _annual_rule(header, manifest):
    links = re.findall(r'\[\[([^\]]+)\]\]', header)
    link = links[0] if links else header
    target = link.split('|')[0]
    category = (re.sub(r'\[\[([^\]]+)\]\]', lambda m: m[1].split('|')[-1], header).strip()
                if links else link.split('|')[-1])
    rules = _taxonomy(manifest).get('annual_' + manifest['organization'], {})
    rule = (rules.get(category) or rules.get(target)) if manifest['organization'] == 'golden_globe' else None
    return category, rule or _rule('annual_' + manifest['organization'], category, manifest)


def _parse_annual(payload, manifest):
    return _annual_wins(_annual_blocks(payload, manifest), manifest)


def parse_annual_program(payload, manifest):
    """Read expected categories from headers, independently of primary wins."""
    manifest = {**manifest, 'taxonomy': _taxonomy(manifest)}
    blocks = _annual_blocks(payload, manifest)
    film_wins = [w for w in _annual_wins(blocks, manifest) if w.scope == 'film']
    expected = set()
    for block in blocks:
        category, rule = _annual_rule(block[0], manifest)
        if rule['scope'] == 'film':
            expected.add(rule.get('instance', category))
        elif rule['scope'] == 'film_if_associated':
            expected.update(w.award_instance for w in film_wins if w.evidence['category'] == category)
    text = payload.decode('utf-8')
    number = re.search(r'^\s*\|\s*number\s*=\s*(\d+)\s*$', text, re.M)
    if number and int(number[1]) != int(manifest['ceremony']):
        raise SourceError('annual_ceremony_number_mismatch')
    date_field = re.search(r'^\s*\|\s*presented_date\s*=([^\n]*)', text, re.M)
    date_field = date_field or re.search(r'^\s*\|\s*date\s*=([^\n]*)', text, re.M)
    ceremony_date = None
    if date_field:
        value = re.sub(r'<ref\b[^>]*?/>|<ref\b[^>]*>.*?</ref>', '', date_field[1]).strip()
        template = re.fullmatch(r'\{\{[Ss]tart[ _]date(?: and age)?\|(?:df=yes\|)?(\d{4})\|(\d{1,2})\|(\d{1,2})(?:\|df=yes)?\}\}', value)
        try:
            ceremony_date = (date(*map(int, template.groups())) if template else
                             datetime.strptime(value, '%B %d, %Y').date())
        except ValueError as exc:
            raise SourceError('unsupported_annual_ceremony_date') from exc
    try:
        declared = date.fromisoformat(manifest['ceremony_date']) if manifest.get('ceremony_date') else None
    except (TypeError, ValueError) as exc:
        raise SourceError('invalid_declared_ceremony_date') from exc
    if ceremony_date and declared and ceremony_date != declared:
        raise SourceError('annual_ceremony_date_mismatch')
    ceremony_date = ceremony_date or declared
    if not ceremony_date:
        raise SourceError('missing_annual_ceremony_date')
    if ceremony_date.year != int(manifest['ceremony_year']):
        raise SourceError('annual_ceremony_year_mismatch')
    return CeremonyProgram(manifest['organization'], int(manifest['ceremony']), int(manifest['ceremony_year']),
                           ceremony_date, tuple(sorted(expected)),
                           {'source': 'annual_wikitext', 'revision': manifest['revision'],
                            'source_url': manifest.get('url')})


def _annual_wins(blocks, manifest):
    organization = manifest['organization']
    subjects = _subjects(manifest)
    wins = []
    for header, body, explicit_winners in blocks:
        category, rule = _annual_rule(header, manifest)
        if rule['scope'] not in ('film', 'film_if_associated'):
            continue
        for line in body.splitlines():
            if not (re.match(r"^\*(?!\*)\s*" + ('.' if explicit_winners else "'''"), line) or
                    line.startswith("'''")):
                if not (not explicit_winners and re.match(r"^''\s+'''", line)):
                    continue
            instance = rule.get('instance', category)
            citation_matches = [item['instance'] for item in rule.get('citation_instances', [])
                                if item['phrase'].casefold() in line.casefold()]
            if len(citation_matches) > 1:
                raise SourceError('ambiguous_award_citation_subtype')
            if citation_matches:
                instance = citation_matches[0]
            italic_links = _italic_links(line)
            # Some early records italicize the whole recipient/film line. An
            # explicit association preposition identifies the film portion.
            association = re.search(r'\s+(?:in|for)\s+(?=\[\[)', line)
            if rule.get('film_in_nominee') is False and not rule.get('role') and association:
                italic_links = [(m[1], m.start()) for m in re.finditer(r'\[\[([^\]]+)\]\]', line)
                                if m.start() >= association.end()]
            if rule.get('role') and italic_links:
                first_link = re.search(r'\[\[([^\]]+)\]\]', line)
                if first_link and italic_links[0][1] == first_link.start():
                    italic_links = italic_links[1:]
            if not italic_links and rule.get('quoted_film_title'):
                italic_links = [(m[1], m.start()) for m in re.finditer(r'"\[\[([^\]]+)\]\]"', line)]
            if rule.get('film_selection') == 'first' and '(tie)' not in header.casefold():
                italic_links = italic_links[:1]
            film_links = [link for link, _ in italic_links]
            if not film_links:
                if rule['scope'] == 'film_if_associated':
                    continue
                raise SourceError(f'unsupported_annual_winner: {category}')
            film_titles = [link.split('|')[-1] for link in film_links]
            # Eligible acting/directing rows put the recipient before the film.
            # Character links after "as" are not award recipients.
            recipient_text = line[:italic_links[0][1]]
            links = re.findall(r'\[\[([^\]]+)\]\]', recipient_text)
            recipients = []
            for link in links if rule.get('role') else ():
                if link in film_links:
                    continue
                display, target = link.split('|')[-1], link.split('|')[0]
                names = re.split(r'\s+and\s+|,\s*', display)
                named_group = len(names) > 1 and all(len(name.split()) >= 2 for name in names)
                if named_group:
                    recipients.extend((name, target, True) for name in names if name)
                else:
                    recipients.append((display, target, False))
            evidence = {'source': 'annual_wikitext', 'revision': manifest['revision'], 'category': category,
                        'winner_marker': 'explicit_winners_section' if explicit_winners else 'bold_category_bullet'}
            evidence.update(organization=organization, ceremony=int(manifest['ceremony']),
                            ceremony_year=int(manifest['ceremony_year']), role=rule.get('role'),
                            winning_films=film_titles,
                            winning_people=[name for name, _, _ in recipients],
                            credit_names=[link.split('|')[-1] for link in links if link not in film_links])
            films = tuple(EntityReference('movie', title, evidence=({**evidence, 'wiki_target': link.split('|')[0]},))
                          for title, link in zip(film_titles, film_links))
            people = tuple(EntityReference('person', name,
                           evidence=({**evidence, 'wiki_group_target' if group else 'wiki_target': target},))
                           for name, target, group in recipients)
            scope = _winning_scope(rule, films, evidence, subjects)
            if scope != 'film':
                films, people = (), ()
            wins.append(NormalizedWin(organization, int(manifest['ceremony']), int(manifest['ceremony_year']),
                instance, rule.get('category', category), scope, rule.get('role'), films, people, evidence))
    return wins
