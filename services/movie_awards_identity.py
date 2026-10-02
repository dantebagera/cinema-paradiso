"""Read-only verified award identity mapping; never changes CP catalog identity."""
from dataclasses import dataclass, replace
from collections import defaultdict
import html
import re
import unicodedata

from services.movie_awards_sources import ValidationReport, SourceError
import json, os, time, urllib.parse, urllib.request
from pathlib import Path


@dataclass(frozen=True)
class IdentityResolution:
    wins: tuple
    mappings: tuple[dict, ...]
    unresolved: tuple[dict, ...]
    conflicts: tuple[dict, ...]

    @property
    def complete(self):
        return not self.unresolved and not self.conflicts


def resolve_identities(wins, *, existing_mappings, find_by_imdb, search_candidates, overrides):
    mappings, aliases, reverse, conflicts, unresolved = {}, {}, {}, [], []

    def accept(mapping):
        namespace, imdb, tmdb = mapping.get('namespace'), mapping.get('imdb_id'), mapping.get('tmdb_id')
        prefix = 'tt' if namespace == 'movie' else 'nm'
        if namespace not in ('movie', 'person') or not isinstance(tmdb, int) or isinstance(tmdb, bool) or tmdb <= 0 or not re.fullmatch(prefix + r'\d+', imdb or '') or not mapping.get('evidence'):
            conflicts.append({'reason': 'invalid_mapping_evidence', 'namespace': namespace, 'imdb_id': imdb})
            return None
        key = namespace, imdb
        back = namespace, tmdb
        if (key in mappings and mappings[key]['tmdb_id'] != tmdb) or (back in reverse and reverse[back] != imdb):
            conflicts.append({'reason': 'identity_mapping_conflict', 'namespace': namespace, 'imdb_id': imdb, 'tmdb_id': tmdb})
            return None
        mappings[key] = dict(mapping)
        reverse[back] = imdb
        return mapping

    for mapping in existing_mappings:
        accept(mapping)
    for mapping in overrides:
        evidence = mapping.get('evidence', {})
        if not all(evidence.get(k) for k in ('source_url', 'revision', 'reason')):
            conflicts.append({'reason': 'override_missing_evidence', 'namespace': mapping.get('namespace'), 'title': mapping.get('title')})
            continue
        context = mapping.get('source_context', {})
        if mapping.get('source_alias') and not all(context.get(k) for k in ('source', 'ceremony', 'category')):
            conflicts.append({'reason': 'override_missing_source_context', 'namespace': mapping.get('namespace'), 'alias': mapping['source_alias']})
            continue
        accepted = accept(mapping)
        if accepted and mapping.get('source_alias'):
            alias_key = mapping['namespace'], mapping['source_alias'], context['source'], context['ceremony'], context['category']
            if alias_key in aliases and aliases[alias_key]['imdb_id'] != accepted['imdb_id']:
                conflicts.append({'reason': 'source_alias_conflict', 'namespace': mapping['namespace'], 'alias': mapping['source_alias']})
            else:
                aliases[alias_key] = accepted

    resolved = {}

    def resolve(ref):
        context = ref.evidence[0] if ref.evidence else {}
        cache_key = ref.namespace, ref.imdb_id, ref.title, context.get('source'), context.get('ceremony'), context.get('category')
        if cache_key in resolved:
            return resolved[cache_key]
        alias = aliases.get((ref.namespace, ref.title, context.get('source'), context.get('ceremony'), context.get('category')))
        if alias and (not ref.imdb_id or ref.imdb_id in (alias.get('replaces_source_imdb_id'), alias['imdb_id'])):
            mapping = alias
        else:
            mapping = mappings.get((ref.namespace, ref.imdb_id)) if ref.imdb_id else None
        if not mapping and ref.imdb_id:
            try:
                response = find_by_imdb(ref.imdb_id, ref.namespace)
                candidates = response.get('movie_results' if ref.namespace == 'movie' else 'person_results', [])
                if len(candidates) == 1:
                    candidate = candidates[0]
                    mapping = accept({'namespace': ref.namespace, 'imdb_id': ref.imdb_id, 'tmdb_id': candidate.get('id'),
                        'evidence': {'source': 'tmdb_find', 'external_source': 'imdb_id', 'imdb_id': ref.imdb_id},
                        'facts': {key: candidate[key] for key in ('title', 'original_title', 'name', 'release_date', 'poster_path', 'original_language', 'genre_ids', 'vote_average', 'vote_count') if key in candidate}})
            except Exception as exc:
                unresolved.append({'reason': 'identity_transport_failed', 'namespace': ref.namespace, 'imdb_id': ref.imdb_id,
                                   'error_type': type(exc).__name__})
        if not mapping and not ref.imdb_id:
            # Search is candidate generation only. Evidence and credit validation
            # belong to the injected identity bridge, never to a name comparison.
            try:
                candidates = search_candidates(ref)
                verified = [candidate for candidate in candidates if candidate.get('verified_external_id') is True
                            and candidate.get('verified_source_alias') is True
                            and candidate.get('verified_role_credits') is True
                            and candidate.get('namespace') == ref.namespace]
                if len(verified) == 1:
                    mapping = accept(verified[0])
            except Exception as exc:
                unresolved.append({'reason': 'identity_search_failed', 'namespace': ref.namespace, 'title': ref.title,
                                   'error_type': type(exc).__name__})
        if mapping:
            result = replace(ref, imdb_id=mapping['imdb_id'], tmdb_id=mapping['tmdb_id'])
        else:
            unresolved.append({'reason': 'unresolved_identity', 'namespace': ref.namespace, 'title': ref.title, 'imdb_id': ref.imdb_id})
            result = ref
        resolved[cache_key] = result
        return result

    output = []
    for win in wins:
        if win.scope == 'film':
            output.append(replace(win, films=tuple(resolve(ref) for ref in win.films),
                                  people=tuple(resolve(ref) for ref in win.people)))
        else:
            output.append(win)
    return IdentityResolution(tuple(output), tuple(mappings[key] for key in sorted(mappings)),
                              tuple(unresolved), tuple(conflicts))


def _source_label(value):
    """Normalize typography, retaining every identifying word and number."""
    value = unicodedata.normalize('NFKC', html.unescape(value or '')).casefold()
    value = value.translate(str.maketrans({'\u2019': "'", '\u2018': "'", '\u201c': '"', '\u201d': '"',
                                         '\u2013': '-', '\u2014': '-'}))
    # Dotted initials keep their letters, irrespective of intervening spaces.
    value = re.sub(r'\b(?:[^\W\d_]\.\s*){2,}',
                   lambda match: re.sub(r'[.\s]', '', match[0]) + ' ', value)
    value = value.replace(' & ', ' and ')
    value = ''.join(char if char.isalnum() or char.isspace() else ' ' for char in value)
    return ' '.join(value.split())


def verify_linked_candidate(ref, *, identity, find_by_imdb, load_credits):
    """Verify a candidate anchored in a pinned winning-subject link.

    Structured identifiers generate the candidate. Correct-domain external-ID
    lookup and eligible movie credits validate it; names alone never resolve a
    person. The caller records how primary and independent winner aliases agree.
    """
    context = ref.evidence[0] if ref.evidence else {}
    proof, scope = identity.get('evidence', {}), identity.get('source_context', {})
    prefix = 'tt' if ref.namespace == 'movie' else 'nm'
    if (ref.namespace not in ('movie', 'person') or identity.get('namespace') != ref.namespace
            or not re.fullmatch(prefix + r'\d+', identity.get('imdb_id') or '')
            or not all(proof.get(k) for k in ('source_url', 'revision', 'reason'))
            or not all(scope.get(k) and scope[k] == context.get(k) for k in ('source', 'ceremony', 'category'))
            or _source_label(identity.get('source_alias')) != _source_label(ref.title)):
        return None
    results = find_by_imdb(identity['imdb_id'], ref.namespace).get(
        'movie_results' if ref.namespace == 'movie' else 'person_results', [])
    if len(results) != 1:
        return None
    candidate = results[0]
    identifier = candidate.get('id')
    if (not isinstance(identifier, int) or isinstance(identifier, bool) or identifier < 1
            or identity.get('tmdb_id') not in (None, identifier)):
        return None
    role = context.get('role')
    if ref.namespace == 'person':
        movies = identity.get('winning_movie_ids', [])
        if role not in ('actor', 'director') or not movies:
            return None
        for movie in movies:
            if not isinstance(movie, int) or isinstance(movie, bool) or movie < 1:
                return None
            credits = load_credits(movie)
            eligible = credits.get('cast', []) if role == 'actor' else [
                row for row in credits.get('crew', []) if row.get('job') == 'Director']
            if not any(row.get('id') == identifier for row in eligible):
                return None
    elif role in ('actor', 'director'):
        credits = load_credits(identifier)
        eligible = credits.get('cast', []) if role == 'actor' else [
            row for row in credits.get('crew', []) if row.get('job') == 'Director']
        people = identity.get('credit_people', [])
        if people:
            if not all(person in {row.get('id') for row in eligible} for person in people):
                return None
        else:
            names = context.get('winning_people', [])
            if not names or not all(_source_label(name) in {_source_label(row.get('name')) for row in eligible} for name in names):
                return None
    return {**identity, 'tmdb_id': identifier, 'verified_external_id': True,
            'verified_source_alias': True, 'verified_role_credits': True,
            'facts': {key: candidate[key] for key in ('title', 'original_title', 'name', 'release_date',
                       'poster_path', 'original_language', 'genre_ids', 'vote_average', 'vote_count') if key in candidate},
            'evidence': {**proof, 'external_source': 'imdb_id', 'imdb_id': identity['imdb_id'],
                         'credit_role': role, 'credit_movie_ids': identity.get('winning_movie_ids', [])}}


def _reference_labels(ref, mapping):
    labels = {ref.title}
    for evidence in ref.evidence:
        target = evidence.get('wiki_target')
        if target:
            labels.add(target)
            # A wiki disambiguation suffix qualifies the linked subject; it is
            # not part of its film title. Matching stays inside one award.
            labels.add(re.sub(r' \((?:\d{4} )?film\)$', '', target))
    facts = (mapping or {}).get('facts', {})
    for key in ('title', 'original_title') if ref.namespace == 'movie' else ('name',):
        if facts.get(key):
            labels.add(facts[key])
    if ref.namespace == 'movie':
        for label in list(labels):
            title = re.sub(r' \((?:\d{4})(?: film)?\)$', '', label.strip())
            article = re.fullmatch(r'(.+), (The|A|An)', title, re.I)
            labels.add(f'{article[2]} {article[1]}' if article else title)
    return {_source_label(label) for label in labels if label}


def crosscheck_ceremony(primary_wins, independent_wins, *, mappings):
    """Compare complete winning sets, without turning a title into an identity.

    Independent aliases match only verified primary entities within the same
    ceremony/category. Multiple candidates, missing winners and changed eligible
    recipients all fail. Shared recipient rows collapse for the film comparison.
    """
    diagnostics, details = set(), []
    primary = [w for w in primary_wins if w.scope == 'film']
    independent = [w for w in independent_wins if w.scope == 'film']
    identities = {(w.organization, w.ceremony, w.ceremony_year) for w in primary + independent}
    if len(identities) != 1 or not primary or not independent:
        diagnostics.add('missing_or_mixed_ceremony_crosscheck')
    origins = {(w.evidence.get('source'), w.evidence.get('revision')) for w in primary_wins}
    other_origins = {(w.evidence.get('source'), w.evidence.get('revision')) for w in independent_wins}
    by_category_origins = defaultdict(set)
    by_category_records = defaultdict(set)

    def record_origin(win):
        evidence = win.evidence
        proof = evidence.get('reviewed_source') or evidence
        url, revision = proof.get('source_url'), proof.get('revision')
        return (url, str(revision)) if url and revision else None

    for win in primary_wins:
        by_category_origins[win.award_instance].add((win.evidence.get('source'), str(win.evidence.get('revision'))))
        if (record := record_origin(win)):
            by_category_records[win.award_instance].add(record)
    # A factual transcription retains its original source identity. Giving the
    # copy a different parser name or compilation hash cannot make it independent.
    self_verified = any(
        (win.evidence.get('source'), str(win.evidence.get('revision'))) in by_category_origins[win.award_instance]
        or (record_origin(win) is not None and record_origin(win) in by_category_records[win.award_instance])
        for win in independent_wins)
    if (not other_origins or any(not source or not revision for source, revision in other_origins)
            or self_verified):
        diagnostics.add('missing_independent_source')
    facts = {(m['namespace'], m['imdb_id']): m for m in mappings if m.get('evidence')}
    candidates = defaultdict(dict)
    expected_films, expected_people = set(), set()
    for win in primary:
        for ref in win.films + win.people:
            if not ref.imdb_id or not ref.tmdb_id:
                diagnostics.add('unverified_primary_identity')
                continue
            key = win.award_instance, ref.namespace
            labels = _reference_labels(ref, facts.get((ref.namespace, ref.imdb_id)))
            candidates[key].setdefault(ref.entity_id, set()).update(labels)
        films = {ref.entity_id for ref in win.films if ref.imdb_id and ref.tmdb_id}
        expected_films.update((win.award_instance, film) for film in films)
        for person in win.people:
            if person.imdb_id and person.tmdb_id:
                expected_people.update((win.award_instance, win.role, person.entity_id, film) for film in films)
    actual_films, actual_people, film_rows = set(), set(), defaultdict(list)

    def match(ref, instance):
        options = candidates.get((instance, ref.namespace), {})
        if ref.imdb_id:
            matches = {ref.entity_id} if ref.entity_id in options else set()
        else:
            aliases = _reference_labels(ref, None)
            matches = set()
            context = ref.evidence[0] if ref.evidence else {}
            for entity, labels in options.items():
                mapping = facts.get((ref.namespace, entity.rsplit(':', 1)[-1]), {})
                scope, proof = mapping.get('source_context', {}), mapping.get('evidence', {})
                labels = set(labels)
                if (mapping.get('source_alias') and all(scope.get(k) == context.get(k) for k in ('source', 'ceremony', 'category'))
                        and all(proof.get(k) for k in ('source_url', 'revision', 'reason'))):
                    labels.add(_source_label(mapping['source_alias']))
                if aliases & labels:
                    matches.add(entity)
        if len(matches) == 1:
            return next(iter(matches))
        reason = 'ambiguous_independent_identity' if matches else 'unmatched_independent_identity'
        diagnostics.add(reason)
        details.append({'reason': reason, 'namespace': ref.namespace, 'title': ref.title, 'award_instance': instance})
        return None

    for win in independent:
        films = {entity for ref in win.films if (entity := match(ref, win.award_instance))}
        film_rows[win.award_instance].append(films)
        actual_films.update((win.award_instance, film) for film in films)
        for ref in win.people:
            person = match(ref, win.award_instance)
            if person:
                actual_people.update((win.award_instance, win.role, person, film) for film in films)
    if expected_films != actual_films:
        diagnostics.add('conflicting_film_winners')
    if expected_people != actual_people:
        diagnostics.add('conflicting_person_winners')
    evidence = {'crosscheck_agrees': not diagnostics, 'revision': sorted((revision for _, revision in other_origins if revision), key=str),
                'ties': [], 'multi_film_awards': [], 'identity_diagnostics': details,
                'missing_film_winners': sorted(expected_films - actual_films),
                'extra_film_winners': sorted(actual_films - expected_films),
                'missing_person_winners': sorted(expected_people - actual_people),
                'extra_person_winners': sorted(actual_people - expected_people)}
    if len(evidence['revision']) == 1:
        evidence['revision'] = evidence['revision'][0]
    for instance, rows in film_rows.items():
        if len(set().union(*rows)) > 1:
            key = 'multi_film_awards' if any(len(row) > 1 for row in rows) else 'ties'
            evidence[key].append(instance)
    return ValidationReport(not diagnostics, tuple(sorted(diagnostics)), evidence)

class TMDbIdentityBridge:
    """Bounded bootstrap/runtime identity reads; credentials never leave their owner."""
    def __init__(self, config_path=None, *, get_key=None, cancelled=None):
        if os.environ.get('CP_TEST_MODE') == '1':
            raise SourceError('external_identity_disabled_in_test_mode')
        self._get_key = get_key or (lambda: json.loads(Path(config_path).read_text(encoding='utf-8')).get('tmdb_key',''))
        self._cancelled = cancelled or (lambda:False)
        self._last_request = 0.0

    def find(self, imdb_id, namespace):
        return self._request('find/' + urllib.parse.quote(imdb_id), {'external_source': 'imdb_id'})

    def credits(self, movie_id):
        if not isinstance(movie_id, int) or isinstance(movie_id, bool) or movie_id < 1:
            raise SourceError('invalid_credit_movie_id')
        return self._request('movie/' + str(movie_id) + '/credits')

    def _request(self, resource, parameters=None):
        if self._cancelled():
            raise SourceError('awards_refresh_cancelled')
        key = str(self._get_key() or '').strip()
        if not key:
            raise SourceError('tmdb_credentials_unavailable')
        elapsed = time.monotonic() - self._last_request
        if elapsed < .25:
            time.sleep(.25 - elapsed)
        self._last_request = time.monotonic()
        url = 'https://api.themoviedb.org/3/' + resource + '?' + urllib.parse.urlencode({**(parameters or {}), 'api_key': key})
        req = urllib.request.Request(url, headers={'User-Agent': 'CinemaParadiso/3.0 movie-awards identity build'})
        # Refuse redirects entirely: the credential remains on its owning host.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                raise SourceError('identity_redirect_refused')
        try:
            with urllib.request.build_opener(NoRedirect()).open(req, timeout=20) as response:
                raw = response.read(2 * 1024 * 1024 + 1)
            if len(raw) > 2 * 1024 * 1024:
                raise SourceError('identity_payload_limit')
            return json.loads(raw)
        except Exception as exc:
            # HTTP exception strings include request URLs; never retain those.
            raise SourceError('identity_transport_' + type(exc).__name__) from None

