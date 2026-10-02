"""Reproducible, fail-closed historical seed build. Run with ``python -m tools.build_movie_awards_snapshot``.

The manifest pins source bytes, primary ceremony windows, independent programs,
cross-check evidence and verified identity mappings. A failed audit never emits
or replaces a seed. Source acquisitions and output stay outside live CP data.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

from services.movie_awards_sources import (CeremonyProgram, SourceError, aggregate_ceremony,
                                          parse_annual_program, parse_source, validate_ceremony)
from services.movie_awards_identity import crosscheck_ceremony, resolve_identities, verify_linked_candidate, TMDbIdentityBridge


def canonical_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n').encode('utf-8')


class _BoundedRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urllib.parse.urlsplit(newurl)
        if parsed.scheme != 'https' or parsed.hostname not in {'raw.githubusercontent.com', 'en.wikipedia.org', 'api.themoviedb.org'}:
            raise SourceError('source_redirect_not_allowed')
        count = getattr(req, '_awards_redirects', 0) + 1
        if count > 5:
            raise SourceError('source_redirect_limit')
        result = super().redirect_request(req, fp, code, msg, headers, newurl)
        result._awards_redirects = count
        return result


def _source_bytes(source):
    limit = (2 if source.get('source_id') == 'annual_wikitext' else 40) * 1024 * 1024
    if source.get('path'):
        with Path(source['path']).open('rb') as stream:
            raw = stream.read(limit + 1)
    else:
        if os.environ.get('CP_TEST_MODE') == '1':
            raise SourceError('external_source_disabled_in_test_mode')
        url = source.get('url', '')
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != 'https' or parsed.hostname not in {'raw.githubusercontent.com', 'en.wikipedia.org'}:
            raise SourceError('source_url_not_allowed')
        req = urllib.request.Request(url, headers={'User-Agent': 'CinemaParadiso/3.0 (+https://github.com/dantebagera/cinema-paradiso) movie-awards seed audit'})
        try:
            with urllib.request.build_opener(_BoundedRedirects()).open(req, timeout=20) as response:
                raw = response.read(limit + 1)
        except urllib.error.HTTPError as exc:
            raise SourceError(f'source_http_{exc.code}') from None
    if len(raw) > limit:
        raise SourceError('source_payload_limit')
    if hashlib.sha256(raw).hexdigest() != source.get('sha256'):
        raise SourceError('pinned_source_hash_mismatch')
    if not source.get('revision'):
        raise SourceError('missing_pinned_source_revision')
    return raw


def build_snapshot(manifest, *, overrides, find_by_imdb=None, search_candidates=None):
    if manifest.get('schema_version') != 1:
        raise SourceError('unsupported_build_schema')
    as_of = date.fromisoformat(manifest['as_of']).isoformat()
    expected = manifest.get('expected_coverage', {})
    if not expected or any(org not in ('oscar', 'golden_globe') for org in expected):
        raise SourceError('missing_expected_historical_coverage')
    candidates, source_failures, source_provenance = {}, [], []
    for source_index, source in enumerate(manifest['sources']):
        source_provenance.append({k: source.get(k) for k in ('source_id', 'revision', 'sha256', 'url', 'license', 'license_url')})
        if source.get('redistribution_verified') is not True:
            source_failures.append({'source': source['source_id'], 'reason': 'redistribution_terms_unverified'})
        try:
            wins = parse_source(source['source_id'], _source_bytes(source), source)
        except (SourceError, OSError) as exc:
            source_failures.append({'source': source['source_id'], 'reason': str(exc) if isinstance(exc, SourceError) else type(exc).__name__})
            continue
        for win in wins:
            # Overlap evidence is never additive. A source owns an explicit
            # primary window; other ceremonies are used by the audit separately.
            if source['first_ceremony'] <= win.ceremony <= source['last_ceremony']:
                if win.ceremony in source.get('excluded_ceremonies', []):
                    continue
                if source.get('primary_instances') is not None and win.award_instance not in source['primary_instances']:
                    continue
                key = win.organization, win.ceremony
                bucket = candidates.setdefault(key, {'source': source.get('primary_group') or source['source_id'],
                    'source_index': source_index, 'primary_group': source.get('primary_group'), 'instances': {}, 'wins': []})
                if bucket['source_index'] != source_index:
                    if not source.get('primary_group') or source['primary_group'] != bucket['primary_group']:
                        source_failures.append({'source': source['source_id'], 'reason': 'overlapping_primary_sources',
                                                'organization': key[0], 'ceremony': key[1]})
                        continue
                    if win.award_instance in bucket['instances'] and bucket['instances'][win.award_instance] != source_index:
                        source_failures.append({'source': source['source_id'], 'reason': 'overlapping_primary_categories',
                                                'organization': key[0], 'ceremony': key[1]})
                        continue
                bucket['instances'][win.award_instance] = source_index
                bucket['wins'].append(win)
    programs = {(p['organization'], p['ceremony']): p for p in manifest.get('programs', [])}
    if len(programs) != len(manifest.get('programs', [])):
        raise SourceError('duplicate_independent_programs')
    all_wins = [win for key in sorted(candidates) for win in candidates[key]['wins']]
    resolution = resolve_identities(all_wins, existing_mappings=manifest.get('identity_mappings', []),
        find_by_imdb=find_by_imdb or (lambda *_: {}), search_candidates=search_candidates or (lambda *_: []), overrides=overrides)
    resolved = {}
    for win in resolution.wins:
        resolved.setdefault((win.organization, win.ceremony), []).append(win)
    audit, contributions = [], []
    mapping_keys = {(m['namespace'], m['imdb_id']) for m in resolution.mappings}
    for organization, bounds in sorted(expected.items()):
        first, last = bounds
        if not isinstance(first, int) or not isinstance(last, int) or first < 1 or last < first:
            raise SourceError('invalid_coverage_bounds')
        for ceremony in range(first, last + 1):
            key = organization, ceremony
            wins = resolved.get(key, [])
            diagnostics = []
            program_input = programs.get(key)
            if not wins:
                diagnostics.append('missing_ceremony_source')
            if not program_input:
                diagnostics.append('missing_independent_program')
            else:
                try:
                    independent_source = program_input.get('independent_source')
                    if independent_source:
                        raw = _source_bytes(independent_source)
                        program = parse_annual_program(raw, independent_source)
                        independent = parse_source(independent_source['source_id'], raw, independent_source)
                        expected_instances = set(program.expected_instances)
                        supplement_evidence = []
                        for supplement in program_input.get('independent_supplements', []):
                            replaced = supplement.get('replace_instances')
                            if not isinstance(replaced, list) or not replaced or any(not isinstance(item, str) or not item for item in replaced):
                                raise SourceError('missing_supplement_category_scope')
                            supplemental_bytes = _source_bytes(supplement)
                            supplemental_wins = [win for win in parse_source(supplement['source_id'], supplemental_bytes, supplement)
                                if (win.organization, win.ceremony) == key and win.award_instance in replaced]
                            if supplement['source_id'] == 'annual_wikitext':
                                supplemental_program = parse_annual_program(supplemental_bytes, supplement)
                                declared = set(supplemental_program.expected_instances) & set(replaced)
                                proof = supplemental_program.evidence
                            else:
                                proof = supplement.get('reviewed_program', {})
                                declared = set(proof.get('expected_instances', []))
                                if not declared or not declared <= set(replaced) or not all(proof.get(field) for field in ('revision', 'source_url')):
                                    raise SourceError('missing_supplement_program_evidence')
                            independent = [win for win in independent if win.award_instance not in replaced] + supplemental_wins
                            expected_instances = (expected_instances - set(replaced)) | declared
                            supplement_evidence.append({'source_id': supplement['source_id'], 'sha256': supplement['sha256'],
                                'revision': supplement['revision'], 'replaced_instances': replaced, 'program_evidence': proof})
                        if supplement_evidence:
                            program = CeremonyProgram(program.organization, program.ceremony, program.ceremony_year,
                                program.ceremony_date, tuple(sorted(expected_instances)),
                                {**program.evidence, 'supplements': supplement_evidence})
                        crosscheck = crosscheck_ceremony(wins, independent, mappings=resolution.mappings)
                        diagnostics.extend(crosscheck.diagnostics)
                        program_input = {**asdict(program), 'ceremony_date': program.ceremony_date.isoformat(),
                                         'crosscheck': crosscheck.evidence}
                    else:
                        program = CeremonyProgram(organization, ceremony, program_input['ceremony_year'],
                            date.fromisoformat(program_input['ceremony_date']), tuple(program_input['expected_instances']), program_input['evidence'])
                    evidence = {**program_input.get('crosscheck', {}), 'as_of': as_of}
                    report = validate_ceremony(wins, program, evidence)
                    diagnostics.extend(report.diagnostics)
                except (SourceError, OSError) as exc:
                    diagnostics.append(str(exc) if isinstance(exc, SourceError) else type(exc).__name__)
            unresolved_refs = []
            for win in wins:
                if win.scope != 'film':
                    continue
                if not win.films or (win.role and not win.people):
                    diagnostics.append('missing_winning_identity')
                for ref in win.films + win.people:
                    if (ref.namespace, ref.imdb_id) not in mapping_keys or not ref.tmdb_id:
                        unresolved_refs.append({'namespace': ref.namespace, 'title': ref.title, 'imdb_id': ref.imdb_id,
                                                'category': win.category})
            if unresolved_refs:
                diagnostics.append('unresolved_tmdb_identity')
            audit.append({'organization': organization, 'ceremony': ceremony, 'complete': not diagnostics,
                          'diagnostics': sorted(set(diagnostics)), 'unresolved': unresolved_refs,
                          'included_winner_rows': sum(w.scope == 'film' for w in wins),
                          'excluded': [{'category': w.category, 'reason': w.scope} for w in wins if w.scope != 'film']})
            if not diagnostics:
                contribution = asdict(aggregate_ceremony(wins))
                contribution['source_evidence'] = candidates[key]['source']
                contribution['validation'] = program_input
                contributions.append(contribution)
    source_organizations = {'dlu_oscar': 'oscar', 'historical_globe': 'golden_globe', 'modern_globe': 'golden_globe'}
    for source in manifest['sources']:
        if source.get('organization'):
            source_organizations[source['source_id']] = source['organization']
    complete_organizations = {
        org for org in expected
        if all(a['complete'] for a in audit if a['organization'] == org)
        and not any(source_organizations.get(failure['source'], org) == org for failure in source_failures)
        and not resolution.conflicts
    }
    ready = bool(complete_organizations)
    coverage = {org: {'status': 'complete' if org in complete_organizations else 'pending',
                     'first_ceremony': bounds[0], 'last_ceremony': bounds[1]}
                for org, bounds in expected.items()}
    contributions = [c for c in contributions if c['organization'] in complete_organizations]
    seed = {'schema_version': 1, 'coverage': coverage, 'ceremonies': contributions,
            'identity_mappings': resolution.mappings} if ready else None
    return {'schema_version': 1, 'ready': ready, 'as_of': as_of, 'coverage': coverage,
            'seed': seed, 'seed_sha256': hashlib.sha256(canonical_bytes(seed)).hexdigest() if ready else None,
            'sources': source_provenance, 'audit': audit, 'source_failures': source_failures,
            'unresolved_count': len(resolution.unresolved), 'unresolved': resolution.unresolved,
            'identity_conflicts': resolution.conflicts,
            'taxonomy_sha256': hashlib.sha256((Path(__file__).resolve().parents[1] / 'static/movie-awards/category-taxonomy.json').read_bytes()).hexdigest()}


def _atomic_json(path, value):
    raw = canonical_bytes(value)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=path.name + '.', suffix='.tmp', delete=False) as stream:
        temp = Path(stream.name)
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def write_build(output_root, result):
    output_root = Path(output_root).resolve()
    temp_root = Path(tempfile.gettempdir()).resolve()
    if temp_root not in output_root.parents:
        raise SourceError('output_root_must_be_inside_os_temp')
    output_root.mkdir(parents=True, exist_ok=True)
    report = {k: v for k, v in result.items() if k != 'seed'}
    _atomic_json(output_root / 'coverage-audit.json', report)
    if result['ready']:
        _atomic_json(output_root / 'seed.json', result['seed'])
        _atomic_json(output_root / 'manifest.json', report)



def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root', required=True)
    parser.add_argument('--sources-manifest', required=True)
    parser.add_argument('--identity-overrides', required=True)
    parser.add_argument('--resolve-identities', action='store_true')
    args = parser.parse_args(argv)
    output = Path(args.output_root).resolve()
    if Path(tempfile.gettempdir()).resolve() not in output.parents:
        parser.error('output-root must be inside the operating-system temporary directory')
    manifest = json.loads(Path(args.sources_manifest).read_text(encoding='utf-8'))
    overrides = json.loads(Path(args.identity_overrides).read_text(encoding='utf-8'))['overrides']
    bridge = TMDbIdentityBridge(Path(__file__).resolve().parents[1] / 'config.json') if args.resolve_identities else None
    def search(ref):
        context = ref.evidence[0] if ref.evidence else {}
        matches = [candidate for candidate in manifest.get('linked_identity_candidates', [])
                   if candidate.get('namespace') == ref.namespace and candidate.get('source_alias') == ref.title
                   and all(candidate.get('source_context', {}).get(k) == context.get(k) for k in ('source', 'ceremony', 'category'))]
        return [result for candidate in matches if (result := verify_linked_candidate(ref, identity=candidate,
                find_by_imdb=bridge.find, load_credits=bridge.credits))] if bridge else []
    result = build_snapshot(manifest, overrides=overrides, find_by_imdb=bridge.find if bridge else None,
                            search_candidates=search)
    write_build(output, result)
    print(json.dumps({'ready': result['ready'], 'ceremonies': len(result['audit']), 'unresolved': result['unresolved_count'],
                      'source_failures': result['source_failures'], 'report': str(output / 'coverage-audit.json')}))
    return 0 if result['ready'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
