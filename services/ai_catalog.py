"""Complete GPT catalogue traversal over the existing query and domain owners."""
from copy import deepcopy
from dataclasses import dataclass
import datetime
import math
import re
from types import MappingProxyType
import uuid

from services.advanced_search import normalize_query, query_signature
from services.ai_provider import canonical_count
from services.tmdb_advanced_search import build_discover_plan, movie_matches_details, sort_movie_summaries


class AICatalogError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def movie_scope_decision(movie, *, today=None, include_shorts=False, include_upcoming=False, include_documentaries=True):
    if movie.get('media_type', 'movie') != 'movie':
        return 'excluded'
    release = str(movie.get('release_date') or '')
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', release):
        return 'unresolved'
    try:
        released = datetime.date.fromisoformat(release)
    except ValueError:
        return 'unresolved'
    if not include_upcoming and released > (today or datetime.date.today()):
        return 'excluded'
    runtime = movie.get('runtime')
    if isinstance(runtime, bool) or not isinstance(runtime, (int, float)) or not math.isfinite(runtime) or runtime <= 0:
        return 'unresolved'
    if not include_shorts and runtime < 60:
        return 'excluded'
    if not include_documentaries:
        genres = movie.get('genre_ids')
        if genres is None:
            genres = [row.get('id') for row in movie.get('genres', []) if isinstance(row, dict)]
        if not genres:
            return 'unresolved'
        if '99' in {str(identity) for identity in genres}:
            return 'excluded'
    return 'eligible'


@dataclass(frozen=True)
class ResultSet:
    id: str
    query_fingerprint: str
    movies: tuple
    coverage: str
    reason: str | None
    fetched_pages: int
    provider_total_pages: int
    provider_total_results: int
    excluded_count: int
    unresolved_count: int
    requested_count: str | None
    domain: str = 'movie'
    local_files: tuple = ()
    library_roots: tuple = ()
    download_ready: bool = False

    @property
    def can_prepare_all(self):
        return self.coverage == 'complete'


class AICatalog:
    def __init__(self, provider_get, *, details, person_seed=lambda plan: None,
                 filter_local=lambda rows, groups: rows, local_ready=lambda: True,
                 project=lambda row: row, sort_rows=sort_movie_summaries):
        self.provider_get, self.details, self.person_seed = provider_get, details, person_seed
        self.filter_local, self.local_ready, self.project, self.sort_rows = filter_local, local_ready, project, sort_rows

    def resolve_company(self, text, *, page=1):
        if not isinstance(text, str) or not text.strip() or isinstance(page, bool) or not isinstance(page, int) or not 1 <= page <= 500:
            raise AICatalogError('invalid_company_search')
        raw = self.provider_get('/search/company', {'query': text.strip(), 'page': page})
        total_pages = int(raw.get('total_pages') or 0)
        return {'candidates': [{'id': str(row['id']), 'label': str(row.get('name') or ''),
                    'country': str(row.get('origin_country') or '')} for row in raw.get('results', []) if row.get('id')],
                'page': page, 'total_pages': total_pages, 'total_results': int(raw.get('total_results') or 0),
                'next_page': page + 1 if page < min(total_pages, 500) else None,
                'coverage': 'partial' if page < total_pages else 'complete'}

    def resolve_people(self, text, role, *, page=1):
        if role not in ('actor', 'director', 'writer') or not isinstance(page, int) or not 1 <= page <= 500:
            raise AICatalogError('invalid_person_search')
        raw = self.provider_get('/search/person', {'query': text, 'page': page})
        total_pages = int(raw.get('total_pages') or 0)
        return {'candidates': [{'id': str(row['id']), 'label': str(row.get('name') or ''), 'role': role,
                    'known_for_department': str(row.get('known_for_department') or '')}
                    for row in raw.get('results', []) if row.get('id')],
                'page': page, 'total_pages': total_pages, 'next_page': page + 1 if page < min(total_pages, 500) else None}

    def candidate_eligibility(self, movie, query, *, context_cache=None):
        plan = build_discover_plan(query, complete_catalogue=True)
        decision = movie_matches_details(movie, plan.provider_groups)
        scope = movie_scope_decision(movie)
        if decision is False or scope == 'excluded':
            return 'excluded'
        if decision is None or scope == 'unresolved':
            return 'unresolved'
        if plan.people:
            cache = context_cache if context_cache is not None else {}
            signature = query_signature(query)
            if signature not in cache:
                seed = self.person_seed(plan)
                if seed is None:
                    raise AICatalogError('integration_missing')
                cache[signature] = {str(row.get('id') or row.get('tmdb_id')) for row in seed}
            if str(movie.get('id') or movie.get('tmdb_id')) not in cache[signature]:
                return 'excluded'
        if plan.local_groups:
            if not self.local_ready():
                raise AICatalogError('integration_missing')
            if not self.filter_local([movie], plan.local_groups):
                return 'excluded'
        return 'eligible'

    def collect(self, query, *, requested_count=None, cancel, checkpoint=lambda progress: None, scope=None, resume=None):
        query = normalize_query(query, 'discover')
        plan = build_discover_plan(query, complete_catalogue=True)
        if plan.local_groups and not self.local_ready():
            raise AICatalogError('integration_missing')
        scope = scope or {}
        if set(scope) - {'include_shorts', 'include_upcoming', 'include_documentaries'} or any(not isinstance(v, bool) for v in scope.values()):
            raise AICatalogError('invalid_movie_scope')
        target = canonical_count(requested_count) if requested_count is not None else None
        binding = {'query': query_signature(query), 'target': target, 'scope': scope}
        if resume and resume.get('binding') != binding:
            raise AICatalogError('catalogue_resume_scope_changed')
        seed = self.person_seed(plan) if plan.people else None
        rows, pages, total_pages, total_results, reason = [], 0, 0, 0, None
        first_page_ids = []
        if seed is not None:
            rows = list(seed)
            total_results = len(rows)
        else:
            if resume:
                rows = list(resume.get('source_rows', []))
                pages = resume['fetched_pages']
                total_pages, total_results = resume['provider_total_pages'], resume['provider_total_results']
                first_page_ids = resume.get('first_page_ids', [])
                try:
                    initial = self.provider_get(plan.endpoint, {**plan.provider_params,
                        **({'query': plan.title} if plan.title else {}), 'page': 1})
                except Exception:
                    raise AICatalogError('catalogue_resume_unavailable') from None
                current_ids = [str(row.get('id') or row.get('tmdb_id')) for row in initial.get('results', [])]
                if (current_ids != first_page_ids or initial.get('total_pages') != total_pages
                        or initial.get('total_results') != total_results):
                    raise AICatalogError('catalogue_resume_changed; start a new query')
            page = pages + 1
            while True:
                if pages and page > total_pages:
                    break
                if page > 500:
                    reason = 'provider_page_limit'
                    break
                if cancel.is_set():
                    raise AICatalogError('cancelled')
                params = {**plan.provider_params, 'page': page}
                if plan.title:
                    params['query'] = plan.title
                try:
                    payload = self.provider_get(plan.endpoint, params)
                    if (not isinstance(payload.get('results'), list) or payload.get('page') != page
                            or not isinstance(payload.get('total_pages'), int) or payload['total_pages'] < 0
                            or not isinstance(payload.get('total_results'), int) or payload['total_results'] < 0):
                        raise ValueError('Invalid provider page')
                    total_pages = max(total_pages, int(payload.get('total_pages') or 0))
                    total_results = max(total_results, int(payload.get('total_results') or 0))
                    if page == 1:
                        first_page_ids = [str(row.get('id') or row.get('tmdb_id')) for row in payload['results']]
                    rows.extend(payload['results'])
                    pages += 1
                except Exception:
                    reason = 'provider_page_failed'
                    break
                checkpoint({'phase': 'pages', 'binding': binding, 'source_rows': rows,
                    'first_page_ids': first_page_ids, 'fetched_pages': pages,
                    'provider_total_pages': total_pages, 'provider_total_results': total_results})
                if page >= total_pages:
                    break
                if page >= 500:
                    reason = 'provider_page_limit'
                    break
                page += 1
        accepted, excluded, unresolved, seen = [], 0, 0, set()
        for row_number, row in enumerate(rows, 1):
            if cancel.is_set():
                raise AICatalogError('cancelled')
            identity = str(row.get('id') or row.get('tmdb_id') or '')
            if not identity or identity in seen:
                continue
            seen.add(identity)
            try:
                facts = {**row, **self.details(identity)}
                matches = movie_matches_details(facts, plan.provider_groups)
                scope_result = movie_scope_decision(facts, **scope)
                if matches is False or scope_result == 'excluded':
                    excluded += 1
                elif matches is None or scope_result == 'unresolved':
                    unresolved += 1
                else:
                    accepted.append(facts)
            except Exception:
                unresolved += 1
            if len(seen) % 20 == 0 or row_number == len(rows):
                checkpoint({'phase': 'verification', 'binding': binding, 'source_rows': rows, 'first_page_ids': first_page_ids,
                        'fetched_pages': pages, 'provider_total_pages': total_pages, 'provider_total_results': total_results,
                        'verified': len(accepted), 'excluded': excluded,
                            'unresolved': unresolved, 'processed': len(seen), 'source_count': len(rows)})
        before_local = len(accepted)
        if plan.local_groups:
            accepted = list(self.filter_local(accepted, plan.local_groups))
        excluded += before_local - len(accepted)
        accepted = self.sort_rows(accepted, query['sort']['key'])
        if target is not None and (len(target), target) < (len(str(len(accepted))), str(len(accepted))):
            accepted = accepted[:int(target)]
        if seed is None and not reason and len(seen) != total_results:
            reason = 'provider_membership_changed'
        coverage = 'partial' if reason or unresolved else 'complete'
        if unresolved and not reason:
            reason = 'unresolved_records'
        return ResultSet(uuid.uuid4().hex, query_signature(query),
            tuple(MappingProxyType(deepcopy(self.project(row))) for row in accepted), coverage, reason,
            pages, total_pages, total_results, excluded, unresolved, target)
