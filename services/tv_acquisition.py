"""TV search/intent composition; qBittorrent alone executes transfers."""
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from pathlib import Path
import hashlib
import json
import re
import shutil
import threading
import time
import uuid
from urllib.parse import urlsplit

from services.acquisition_decision import evaluate_release, rank_releases
from services.media_file_facts import probe_media_file
from services.qbittorrent import magnet_hash, normalize_torrent_info_hash, is_allowed_prowlarr_url, TorrentValidationError
from services.quality_catalog import release_claims
from services.tv_filename_parser import parse_episode_name, resolve_episode_claim, series_identity, title_key, VIDEO_EXTENSIONS
from services.verified_import import import_verified_files, rollback_verified_files, finalize_verified_move, verified_rollback_available, sha256, verified_staging_source


class TVAcquisition:
    def __init__(self, repository, acquisition, prowlarr, manager, roots, *, trusted_indexers=lambda: [], search_indexers=lambda: None, submit_candidate=None, metadata=None, resolve_candidate=None, probe=probe_media_file, clock=time.time):
        self.repository, self.acquisition, self.prowlarr, self.manager = repository, acquisition, prowlarr, manager
        self.roots, self.trusted_indexers, self.submit_candidate, self.probe, self.clock = roots, trusted_indexers, submit_candidate, probe, clock
        self.search_indexers = search_indexers
        self.metadata, self.resolve_candidate = metadata, resolve_candidate
        self._lock = threading.RLock()
        self.owner = uuid.uuid4().hex
        self.release_date = date.today
        self.monotonic = time.monotonic

    def target(self, series_id=None, season=None, episode=None, *, tmdb_id=None, episode_numbers=None, missing_only=False, upgrade=False, allow_extras=False):
        if episode is not None and season is None:
            raise ValueError('An episode target requires a season')
        if series_id is None:
            if not tmdb_id or not self.metadata or season is None:
                raise ValueError('Select a series and season')
            with self.repository.store.connection() as db:
                existing = db.execute('SELECT id FROM series WHERE tmdb_id=?', (int(tmdb_id),)).fetchone()
            if existing:
                series_id = existing[0]
        if series_id is not None:
            series = self.repository.series(int(series_id))
            if tmdb_id and int(tmdb_id) != series['tmdb_id']:
                raise ValueError('Series identity changed')
            rows = self.repository.episodes(series['id'], season, today=self.release_date())
            if not rows and season is not None and self.metadata:
                rows = [{**r, 'provider_id': str(r['id']), 'id': -int(r['id']), 'reconciliation_required': False}
                        for r in self.metadata.preview_season(series['tmdb_id'], int(season))['items']]
        else:
            series = self.metadata.preview(int(tmdb_id))
            rows = [{**r, 'provider_id': str(r['id']), 'id': -int(r['id']), 'reconciliation_required': False}
                    for r in self.metadata.preview_season(int(tmdb_id), int(season))['items']]
        from services.tv_catalog_repository import released
        rows = [{**row, 'released': released(row.get('air_date'), self.release_date())} for row in rows]
        if episode_numbers is not None:
            if season is None or not isinstance(episode_numbers, list) or len(episode_numbers) > 500:
                raise ValueError('Select up to 500 episodes within one season')
            wanted = {int(n) for n in episode_numbers}
            rows = [r for r in rows if r['episode_number'] in wanted]
            if {r['episode_number'] for r in rows} != wanted:
                raise ValueError('Selected episode numbering changed; review the selection')
        elif episode is not None:
            rows = [r for r in rows if r['episode_number'] == int(episode)]
        else:
            rows = [r for r in rows if r['released'] and r['season_number'] > 0]
        if missing_only and not upgrade:
            with self.acquisition.connection() as db:
                queued = {r[0] for r in db.execute('SELECT target FROM intent_claims')}
            rows = [r for r in rows if not r.get('available') and f"tv:episode:{r['id']}" not in queued]
        prefix = 'episode' if episode is not None else 'season' if season is not None else 'series'
        key = f"{prefix}:tmdb:tv:{series['tmdb_id']}" + (f':{int(season)}' if season is not None else '') + (f':{int(episode)}' if episode is not None else '')
        if episode_numbers is not None:
            digest = hashlib.sha256(json.dumps([(r['season_number'], r['episode_number']) for r in rows], sort_keys=True).encode()).hexdigest()[:16]
            key = f"selection:tmdb:tv:{series['tmdb_id']}:{digest}"
        return {'key': key, 'media_type': 'tv', 'series_id': series.get('id'), 'tmdb_id': series['tmdb_id'], 'season': season, 'episode': episode,
                'episode_ids': [r['id'] for r in rows], 'upgrade': bool(upgrade),
                'released': bool(rows) and all(r['released'] and not r.get('reconciliation_required') for r in rows)}, series, rows

    @staticmethod
    def _state(decision):
        pending = {'identity_unverified', 'hash_invalid'}
        hard = [r for r in decision['reasons'] if r['code'] not in pending]
        identity = decision['candidate'].get('identity_evidence', {})
        state = 'blocked' if hard or identity.get('state') == 'conflict' else 'identity_review' if identity.get('state') == 'review' else 'resolve' if not decision['candidate']['info_hash'] else 'eligible'
        return {**decision, 'state': state, 'selectable': state in {'eligible', 'resolve'}}

    @staticmethod
    def import_policy():
        return {'version': 1, 'mode': 'move', 'seeding_mode': 'none'}

    @staticmethod
    def _same_destination(left, right):
        return bool(left and right) and all(left.get(key) == right.get(key) for key in ('state', 'show_home', 'season', 'path'))

    @staticmethod
    def job_status(job):
        if job and job.get('tv_lifecycle_version') == 1:
            return {**job, 'rollback_available': verified_rollback_available(job)}
        return job

    def _record_tv_decision(self, decision, series):
        destination = self.repository.resolve_import_destination(series.get('id'), decision['request']['season'], self.roots(), metadata=series)
        decision.update(import_destination=destination, import_policy=self.import_policy())
        # Destination is part of review identity. A home change cannot reuse an old token.
        identity = decision['decision_token'] + json.dumps(destination, sort_keys=True)
        if decision.get('multi_season_scope'):
            identity += json.dumps(decision['multi_season_scope'], sort_keys=True)
        decision['decision_token'] = hashlib.sha256(identity.encode()).hexdigest()
        self.acquisition.record_decision(decision)
        return decision

    @staticmethod
    def _candidate_transport(row, provider_origin):
        values = [str(row.get(key) or '') for key in ('downloadUrl', 'magnetUrl')]
        magnet = next((value for value in values if urlsplit(value).scheme.lower() == 'magnet'), '')
        download = next((value for value in values if urlsplit(value).scheme.lower() in {'http', 'https'}), '')
        supplied, embedded = normalize_torrent_info_hash(row.get('infoHash')), magnet_hash(magnet)
        conflict = bool(supplied and embedded and supplied != embedded)
        unsupported = any(urlsplit(value).scheme.lower() in {'http', 'https'} and not is_allowed_prowlarr_url(value, provider_origin) for value in values)
        return {'magnet_url': magnet, 'download_url': download, 'info_hash': supplied or embedded,
                'transport_verified': bool(not conflict and not unsupported and (embedded or download and is_allowed_prowlarr_url(download, provider_origin)))}

    def search(self, series_id=None, season=None, episode=None, profile_id='safe-hd', *, manual=True, tmdb_id=None, episode_numbers=None, missing_only=False, upgrade=False, budget=30, query_episode=None, preserve_scope=False):
        budget = max(1, min(30, float(budget)))
        deadline = self.monotonic() + budget
        request = dict(series_id=series_id, tmdb_id=tmdb_id, season=season, episode=episode, episode_numbers=episode_numbers, missing_only=missing_only, upgrade=upgrade)
        target, series, episodes = self.target(**{**request,'missing_only':False} if preserve_scope else request)
        profile, provider = self.acquisition.profile(profile_id), self.prowlarr()
        arguments = dict(tmdb_tv_id=series['tmdb_id'], title=series['title'], season=season, episode=episode if query_episode is None else query_episode)
        trusted_ids = {str(value) for value in self.trusted_indexers()}
        indexers = self.search_indexers() if manual else sorted(trusted_ids)
        report = provider.search_tv_report(**arguments, indexer_ids=indexers, budget=budget) if hasattr(provider, 'search_tv_report') else {'items': provider.search_tv(**arguments, indexer_ids=indexers)}
        raw, report = list(report.get('items', [])), {k: v for k, v in report.items() if k != 'items'}
        if query_episode is not None: report['query_episode'] = query_episode
        all_episodes = self.repository.episodes(series['id']) if series.get('id') else []
        known = {ep['id'] for ep in all_episodes}
        all_episodes += [ep for ep in episodes if ep['id'] not in known]
        ambiguous = False
        if self.metadata:
            try:
                matches = self.metadata.request('/search/tv', query=series['title'], _timeout=5, _attempts=1).get('results', [])
                ambiguous = len({r['id'] for r in matches if title_key(r.get('name')) == title_key(series['title'])}) > 1
            except (OSError, ValueError, KeyError):
                ambiguous = True
        decisions = self._release_decisions(raw, request, target, series, episodes, all_episodes, profile, provider, manual, ambiguous, trusted_ids)
        # Bounded episode fallback shares the season search's overall budget.
        # Only providers with an explicit budget contract can be expanded here.
        if manual and season is not None and episode is None and hasattr(provider, 'search_tv_report'):
            found = {episode for decision in decisions if decision['selectable'] for episode in decision['covered_episodes']}
            missing = [ep for ep in episodes if ep['id'] not in found]
            searches = []
            for ep in missing[:4]:
                remaining = deadline - self.monotonic()
                if remaining < 1:
                    break
                try:
                    extra = provider.search_tv_report(**{**arguments, 'episode': ep['episode_number']},
                                                       indexer_ids=self.search_indexers(), budget=min(5, remaining))
                except (OSError, ValueError, RuntimeError):
                    extra = {'items': [], 'partial': True, 'notice': 'Episode sources could not complete this search.'}
                raw.extend(extra.get('items', []))
                searches.append({'episode': ep['episode_number'], **{k:v for k,v in extra.items() if k != 'items'}})
            report['episode_searches'] = searches
            if len(searches) < len(missing) or any(r.get('partial') for r in searches):
                report.update(partial=True, notice='Available results are shown. Some episode searches remain incomplete; narrow the selection or retry.')
        if report.get('episode_searches'):
            decisions = self._release_decisions(raw, request, target, series, episodes, all_episodes, profile, provider, manual, ambiguous, trusted_ids)
        ranked = rank_releases(decisions)
        plan = self.plan_releases(ranked, target['episode_ids'])
        return {'mode': 'manual' if manual else 'automatic', 'target': target, 'decisions': ranked, 'search': report,
                'import_destination': self.repository.resolve_import_destination(series.get('id'), season, self.roots(), metadata=series),
                'import_policy': self.import_policy(),
                'recommended': plan['recommended'], 'missing_episodes': plan['missing_episodes'],
                'episodes': [{'id': ep['id'], 'number': ep['episode_number'], 'code': ep.get('code') or f"S{ep['season_number']:02d}E{ep['episode_number']:02d}"} for ep in episodes]}

    @staticmethod
    def plan_releases(decisions, wanted_episode_ids):
        uncovered, recommended = set(wanted_episode_ids), []
        for row in sorted(decisions, key=lambda d: (not d['selectable'], d['sort_key'][1:4], -len(d['covered_episodes']), d['sort_key'])):
            coverage = set(row['covered_episodes'])
            if row['selectable'] and coverage and coverage <= uncovered:
                recommended.append(row['decision_token'])
                uncovered -= coverage
        return {'recommended':recommended, 'covered_episodes':sorted(set(wanted_episode_ids)-uncovered), 'missing_episodes':sorted(uncovered)}

    def search_missing_season(self, series_id, season, episode_numbers, profile_id, *, budget=30, query_episode=None):
        return self.search(series_id, season, profile_id=profile_id, episode_numbers=episode_numbers,
                           manual=False, missing_only=True, budget=budget, query_episode=query_episode,preserve_scope=True)

    def _release_decisions(self, raw, request, target, series, episodes, all_episodes, profile, provider, manual, ambiguous, trusted_ids):
        # Round-robin sources before the bound; a noisy indexer cannot monopolize review.
        sources = {}
        for row in raw: sources.setdefault(str(row.get('indexerId') or row.get('indexer') or ''), []).append(row)
        fair = []
        while any(sources.values()) and len(fair) < 300:
            for rows in sources.values():
                if rows: fair.append(rows.pop(0))
                if len(fair) == 300: break
        decisions, seen = [], set()
        for row in fair:
            name = str(row.get('title') or '')
            claim = parse_episode_name(name)
            mapping = resolve_episode_claim(claim, all_episodes)
            if claim['scope'] == 'season':
                mapping['episode_ids'] = [ep['id'] for ep in all_episodes if ep['season_number'] == claim['season_number'] and ep['released']]
            coverage = set(mapping['episode_ids']) & set(target['episode_ids'])
            transport = self._candidate_transport(row, provider.base_url)
            magnet, download, info_hash = transport['magnet_url'], transport['download_url'], transport['info_hash']
            identity = series_identity(row, series, ambiguous=ambiguous)
            dedup = info_hash or download or (name, row.get('indexerId'))
            if dedup in seen: continue
            seen.add(dedup)
            candidate = {'title': name, 'info_hash': info_hash, 'magnet_url': magnet, 'download_url': download,
                'indexer': row.get('indexer'), 'indexer_id': str(row.get('indexerId') or row.get('indexer') or ''),
                'size_bytes': int(row.get('size') or 0), 'seeders': int(row.get('seeders') or 0),
                'episode_ids': sorted(coverage), 'identity_verified': identity['state'] == 'matched', 'identity_evidence': identity,
                'transport_verified': transport['transport_verified'],
                'trusted_indexer': str(row.get('indexerId') or '') in trusted_ids,
                'availability_verified': target['released'], 'published_at': row.get('published_at') or self.clock(),
                'coverage_claim': 'season_pack' if claim['scope'] == 'season' else 'episodes',
                'selection_context': request,
                'episode_numbers': [ep['episode_number'] for ep in episodes if ep['id'] in coverage]}
            # A candidate may fulfil part of a batch. Its own intent claims only that subset.
            candidate_request = {**request, 'missing_only': False}
            if request['episode'] is None and request['season'] is not None and coverage:
                candidate_request['episode_numbers'] = candidate['episode_numbers']
            own_target, _, own_episodes = self.target(**candidate_request)
            owned = [v['facts'] for ep in own_episodes for v in ep['versions'] if v['available']]
            decision = evaluate_release(candidate, own_target, profile, manual=manual, owned=owned, blocked=self.acquisition.blocked(own_target['key'], info_hash), now=self.clock())
            decision.update(request=candidate_request, search_request=request, wanted_episodes=target['episode_ids'], requested_episodes=[{'id': ep['id'], 'number': ep['episode_number'], 'provider_id': ep.get('provider_id')} for ep in own_episodes])
            decision = self._state(decision)
            self._record_tv_decision(decision, series)
            decisions.append(decision)
        return decisions

    @staticmethod
    def episode_key(tmdb_id, season, number, provider_id):
        return json.dumps([int(tmdb_id), int(season), int(number), str(provider_id or '')], separators=(',', ':'))

    @staticmethod
    def summarize_search(review, *, selected=(), preparation_errors=(), resolution_count=0):
        decisions = review.get('decisions', [])
        def safe(value, limit=500):
            return re.sub(r'(?i)\b(?:https?://|magnet:)[^\s]+', '[link omitted]', str(value or ''))[:limit]
        candidates, reviewable = [], False
        for row in decisions:
            codes = {r['code'] for r in row.get('reasons', [])}
            identity_review = row['candidate'].get('identity_evidence', {}).get('state') == 'review'
            conflict = row['candidate'].get('identity_evidence',{}).get('state')=='conflict'
            action = ('identity' if identity_review else 'manual_quality' if 'manual_only' in codes else None) if not conflict and codes <= {'identity_unverified','source_unverified','manual_only','hash_invalid'} else None
            reviewable |= bool(action)
            candidates.append({'title':safe(row['candidate'].get('title'),250), 'indexer':safe(row['candidate'].get('indexer') or row['candidate'].get('indexer_id'),100),
                'quality':{key:row['claim'].get(key) for key in ('source','resolution')}, 'coverage':row['covered_episodes'],
                'reasons':[{'code':reason['code'],'message':safe(reason['message'])} for reason in row.get('reasons',[])], 'review_action':action})
        report = review.get('search', {})
        partial = bool(report.get('partial') or report.get('error'))
        state = 'accepted' if selected else 'preparation_failed' if preparation_errors else 'review_required' if reviewable else 'rejected_sources' if decisions else 'provider_failed' if partial else 'no_results'
        summary = ('Source selected' if selected else '; '.join(safe(error) for error in preparation_errors) if preparation_errors else
                   f'{len(decisions)} releases found; deliberate source review required' if reviewable else
                   f'{len(decisions)} releases found; none passed automatic validation' if decisions else
                   'Provider search did not complete' if partial else 'No source found')[:500]
        if partial and decisions: summary = (summary + '. Some indexers did not finish')[:500]
        candidates.sort(key=lambda row: not bool(row['review_action']))
        return {'version':1,'state':state,'result_count':len(decisions), 'automatic_eligible_count':sum(row.get('accepted',False) and not row.get('manual') for row in decisions),
                'resolution_count':resolution_count, 'review_required':reviewable and not bool(selected), 'partial':partial,
                'sources':[{key:safe(row.get(key),100) if key in {'name','state'} else row.get(key) for key in ('id','name','state','count')} for row in report.get('sources',[])],
                'candidates':candidates[:5], 'summary':summary,
                'search_scope':'episode' if report.get('query_episode',review.get('target',{}).get('episode')) is not None else 'season',
                'query_episode':report.get('query_episode',review.get('target',{}).get('episode')),
                'season':review.get('target',{}).get('season'), 'episode_ids':review.get('target',{}).get('episode_ids',[]), 'searched_episode_ids':[]}

    def _automatic_candidates(self, decisions, excluded_episode_ids=()):
        excluded = set(excluded_episode_ids)
        trusted_ids = {str(value) for value in self.trusted_indexers()}
        for decision in decisions:
            candidate = decision['candidate']
            if decision.get('manual') or excluded.intersection(decision['covered_episodes']): continue
            if {reason['code'] for reason in decision['reasons']} - {'hash_invalid'}: continue
            if not all(candidate.get(key) for key in ('identity_verified','transport_verified','availability_verified')): continue
            if str(candidate.get('indexer_id') or '') not in trusted_ids: continue
            if decision.get('import_destination', {}).get('state') != 'ready': continue
            yield decision

    def select_automatic(self, review, *, resolution_limit=5, excluded_episode_ids=(), deadline=None):
        wanted = review.get('target',{}).get('episode_ids',[])
        result = self.select_automatic_plan(review, due_episode_ids=wanted, excluded_episode_ids=excluded_episode_ids,
                                            resolution_limit=resolution_limit, deadline=deadline, single=True)
        return {'decision':next(iter(result['decisions']),None), 'state':result['diagnostics']['state'],
                'result_count':result['diagnostics']['result_count'], 'resolution_count':result['diagnostics']['resolution_count'],
                'error':'' if result['decisions'] else result['diagnostics']['summary'], 'diagnostics':result['diagnostics']}

    def select_automatic_plan(self, review, *, due_episode_ids, excluded_episode_ids=(), resolution_limit=5, deadline=None, single=False):
        wanted = set(review.get('target',{}).get('episode_ids',[]))
        due, uncovered = set(due_episode_ids), wanted-set(excluded_episode_ids)
        attempts, errors = 0, []
        selected, hashes = [], set()
        eligible = list(self._automatic_candidates(review.get('decisions',[]), excluded_episode_ids))
        eligible = [row for row in eligible if set(row['covered_episodes']) <= due or set(row['covered_episodes']) == wanted]
        while eligible:
            plan = self.plan_releases(eligible,uncovered)
            if not plan['recommended']: break
            decision = next(row for row in eligible if row['decision_token']==plan['recommended'][0])
            eligible.remove(decision)
            coverage = set(decision['covered_episodes'])
            if not coverage or not coverage <= uncovered or not (coverage <= due or coverage == wanted): continue
            if deadline is not None and self.monotonic()+30 > deadline: break
            candidate = decision['candidate']
            codes = {reason['code'] for reason in decision['reasons']}
            unresolved = 'hash_invalid' in codes
            resolving = bool(candidate.get('download_url'))
            if unresolved and not resolving: continue
            if resolving and attempts >= max(0,min(5,int(resolution_limit))): continue
            try:
                if resolving: attempts += 1
                prepared = self.prepare(decision['decision_token'])
                if prepared['accepted'] and prepared['candidate']['info_hash'] not in hashes:
                    selected.append(prepared)
                    hashes.add(prepared['candidate']['info_hash'])
                    uncovered -= set(prepared['covered_episodes'])
                    if single: break
            except (ValueError, LookupError, OSError, RuntimeError) as error:
                errors.append(str(error))
        diagnostics = self.summarize_search(review, selected=selected, preparation_errors=errors, resolution_count=attempts)
        return {'decisions':selected, 'covered_episodes':sorted(wanted-uncovered-set(excluded_episode_ids)), 'missing_episodes':sorted(uncovered), 'diagnostics':diagnostics}

    def search_seasons(self, series_id=None, *, tmdb_id=None, seasons, profile_id='safe-hd', cancelled=lambda: False):
        if not isinstance(seasons, list) or not 1 <= len(seasons) <= 150 or any(isinstance(n, bool) or not isinstance(n, int) or n <= 0 for n in seasons):
            raise ValueError('Select 1 to 150 regular seasons')
        seasons = sorted(set(seasons))
        _, series, _ = self.target(series_id, seasons[0], tmdb_id=tmdb_id)
        known = {int(row.get('season_number', row.get('number', -1))) for row in series.get('seasons', [])}
        if not known:
            known = {row['season_number'] for row in self.repository.episodes(series['id'])} if series.get('id') else set()
        if not set(seasons) <= known: raise ValueError('Selected regular seasons must belong to this show')
        scope = {'tmdb_id': series['tmdb_id'], 'seasons': seasons, 'profile_id': profile_id, 'missing_only': True}
        reviews, episodes, deadline = [], [], time.monotonic() + 90
        for number in seasons:
            target, projections = {'series_id':series.get('id'), 'tmdb_id':series['tmdb_id'], 'season':number}, []
            try:
                if cancelled() or time.monotonic() >= deadline: raise TimeoutError('Season search cancelled or work budget reached; retry remaining seasons')
                target, _, rows = self.target(series_id, number, tmdb_id=tmdb_id, missing_only=True)
                projections = [{'id': row['id'], 'key': self.episode_key(series['tmdb_id'], number, row['episode_number'], row.get('provider_id')),
                                'number': row['episode_number'], 'code': row.get('code') or f"S{number:02d}E{row['episode_number']:02d}"} for row in rows]
                review = self.search(series_id, number, tmdb_id=tmdb_id, profile_id=profile_id, manual=True, missing_only=True, upgrade=False)
            except (OSError, ValueError, RuntimeError) as error:
                review = {'target': target, 'decisions': [], 'recommended': [], 'search': {'partial': True, 'error': str(error)},
                          'import_destination': self.repository.resolve_import_destination(series.get('id'), number, self.roots(), metadata=series)}
            review['episodes'] = projections
            reviews.append(review); episodes.extend(projections)
        wanted = [row['key'] for row in episodes]
        decisions, recommended = [], []
        for review in reviews:
            for decision in review['decisions']:
                original_token = decision['decision_token']
                keys = [self.episode_key(series['tmdb_id'], decision['request']['season'], ep['number'], ep.get('provider_id')) for ep in decision['requested_episodes']]
                decision.update(multi_season_scope=scope, covered_episode_keys=keys, wanted_episode_keys=wanted)
                decision['decision_token'] = hashlib.sha256((original_token + json.dumps(scope, sort_keys=True)).encode()).hexdigest()
                self.acquisition.record_decision(decision)
                if original_token in review['recommended'] and review['import_destination']['state'] == 'ready': recommended.append(decision['decision_token'])
                decisions.append(decision)
        return {'season_reviews': reviews, 'selected_seasons': seasons, 'scope_counts': {'targets': len(episodes), 'seasons': len(seasons)},
                'search': {'partial': any(review['search'].get('partial') for review in reviews)}, 'episodes': episodes,
                'decisions': decisions, 'recommended': recommended, 'target': {'series_id': series.get('id'), 'tmdb_id': series['tmdb_id']}}

    def prepare(self, token, *, confirm_identity=False, allow_extras=False, max_age=900):
        decision = self.acquisition.decision(token, max_age=max_age)
        candidate = dict(decision['candidate'])
        evidence = candidate.get('identity_evidence', {})
        if confirm_identity and evidence.get('state') == 'review':
            candidate.update(identity_verified=True, identity_evidence={**evidence, 'state': 'matched', 'method': 'user_confirmed', 'reason': 'Series identity explicitly confirmed'})
        if candidate.get('download_url') and candidate.get('transport_verified') and candidate.get('identity_verified'):
            if not self.resolve_candidate: raise ValueError('Torrent link resolution is unavailable')
            resolved = self.resolve_candidate(candidate)
            if candidate.get('info_hash') and candidate['info_hash'] != resolved.get('info_hash'):
                raise ValueError('Resolved torrent identity differs from the selected release; search again')
            candidate.update(resolved)
        target, series, episodes = self.target(**decision['request'])
        destination = self.repository.resolve_import_destination(series.get('id'), decision['request']['season'], self.roots(), metadata=series)
        if not self._same_destination(decision.get('import_destination'), destination):
            raise ValueError('Destination changed; search and review again')
        original = {(r['number'], str(r.get('provider_id'))) for r in decision.get('requested_episodes', [])}
        current = {(r['episode_number'], str(r.get('provider_id'))) for r in episodes}
        if original and original != current: raise ValueError('Episode identity changed; search again')
        if original:
            candidate['episode_ids'] = target['episode_ids']
        profile = self.acquisition.profile(decision['profile_id'])
        candidate['trusted_indexer'] = str(candidate.get('indexer_id') or '') in {str(value) for value in self.trusted_indexers()}
        if profile['version'] != decision['profile_version']: raise ValueError('Profile changed; review the release again')
        owned = [v['facts'] for ep in episodes for v in ep['versions'] if v['available']]
        candidate['allow_extras'] = bool(allow_extras)
        result = evaluate_release(candidate, target, profile, manual=decision['manual'], owned=owned,
                                  blocked=self.acquisition.blocked(target['key'], candidate.get('info_hash')))
        result.update(request=decision['request'], search_request=decision.get('search_request'), wanted_episodes=decision.get('wanted_episodes', []), requested_episodes=decision.get('requested_episodes', []))
        for key in ('multi_season_scope', 'covered_episode_keys', 'wanted_episode_keys'):
            if key in decision: result[key] = decision[key]
        result = self._state(result)
        self._record_tv_decision(result, series)
        return result

    def _materialize(self, decision):
        if not decision['accepted']:
            raise ValueError('Resolve this release before downloading')
        request = decision['request']
        target, series, rows = self.target(**request)
        if not series.get('id') or any(row['id'] < 0 for row in rows):
            series_id = self.metadata.refresh(series['tmdb_id'], season_scope={int(request['season'])})
        else:
            series_id = series['id']
        new_request = {**request, 'series_id': series_id}
        new_target, new_series, new_rows = self.target(**new_request)
        original = decision.get('requested_episodes')
        if original and {(r['number'], str(r.get('provider_id'))) for r in original} != {(r['episode_number'], str(r.get('provider_id'))) for r in new_rows}:
            raise ValueError('Episode identity changed; search and review again')
        if request.get('series_id') == series_id and decision['candidate']['episode_ids'] == new_target['episode_ids']:
            return decision
        candidate = {**decision['candidate'], 'episode_ids': new_target['episode_ids']}
        result = evaluate_release(candidate, new_target, self.acquisition.profile(decision['profile_id']), manual=decision['manual'])
        result.update(request=new_request, origin_token=decision['decision_token'])
        for key in ('multi_season_scope', 'covered_episode_keys', 'wanted_episode_keys'):
            if key in decision: result[key] = decision[key]
        self._record_tv_decision(result, new_series)
        return result

    def submit_batch(self, tokens, request_key, *, allow_partial=False, allow_extras=False):
        if not isinstance(tokens, list) or not 1 <= len(tokens) <= 100 or len(set(tokens)) != len(tokens):
            raise ValueError('Select between 1 and 100 distinct releases')
        if not isinstance(request_key, str) or not request_key.strip() or len(request_key) > 100:
            raise ValueError('A batch request key is required')
        with self._lock:
            with self.acquisition.connection() as db:
                retry = db.execute('SELECT 1 FROM batches WHERE request_key=?', (request_key,)).fetchone() is not None
            result = self.acquisition.batch(request_key, tokens)
            previous = {r['token']: r for r in result['items']}
            decisions = [self.acquisition.decision(t, max_age=365*86400 if retry else 900) for t in tokens]
            groups = {json.dumps(d.get('search_request'), sort_keys=True) for d in decisions}
            multi = decisions[0].get('multi_season_scope')
            if multi and any(d.get('multi_season_scope') != multi for d in decisions): raise ValueError('Selections must belong to the same season review')
            if len(groups) != 1 and not multi: raise ValueError('Selections must belong to the same episode search')
            wanted, covered = set(decisions[0].get('wanted_episode_keys' if multi else 'wanted_episodes', [])), set()
            for decision in decisions:
                scope = set(decision['covered_episode_keys'] if multi else decision['covered_episodes'])
                if scope & covered: raise ValueError('Selected releases overlap; choose one release per episode')
                covered |= scope
            if wanted - covered and not allow_partial: raise ValueError('Some episodes are missing; review and choose Download available')
            pending = [d for d in decisions if previous.get(d['decision_token'], {}).get('state') != 'submitted']
            # Reserve for the whole remaining batch through the existing lease owner.
            manager = self.manager()
            manager.staging_dir.mkdir(parents=True, exist_ok=True)
            queued_bytes = sum(int(j.get('expected_size') or 0) for j in manager.jobs.all().values() if j.get('state') not in {'imported', 'cancelled', 'rolled_back'})
            free = max(0, shutil.disk_usage(manager.staging_dir).free - queued_bytes)
            estimate = sum(d['estimated_bytes'] for d in pending)
            lease_key = 'tv-batch:'+request_key
            if not self.acquisition.lease(lease_key, self.owner, ttl=600, reserved_bytes=estimate, available_bytes=free):
                raise ValueError('Insufficient space or another worker is submitting this batch')
            try:
                for token in tokens:
                    if previous.get(token, {}).get('state') == 'submitted': continue
                    try:
                        item_key = request_key+':'+token[:32]
                        with self.acquisition.connection() as db:
                            prior = db.execute('SELECT decision_token FROM intents WHERE request_key=?', (item_key,)).fetchone()
                        prepared = self.acquisition.decision(prior[0], max_age=365*86400) if prior else self.prepare(token, allow_extras=allow_extras, max_age=365*86400 if retry else 900)
                        if not prepared['accepted']: raise ValueError('; '.join(r['message'] for r in prepared['reasons']))
                        # Transfer individual reservations from the batch lease to intents/jobs.
                        estimate = max(0, estimate-prepared['estimated_bytes'])
                        self.acquisition.lease(lease_key, self.owner, ttl=600, reserved_bytes=estimate)
                        submitted = self.submit(prepared['decision_token'], item_key)
                        item = {'token': token, 'state': 'submitted', 'intent_id': submitted['intent']['id'], 'info_hash': submitted['intent']['info_hash']}
                    except (ValueError, LookupError, OSError, RuntimeError) as error:
                        item = {'token': token, 'state': 'failed', 'message': str(error)}
                    previous[token] = item
                    result['items'] = [previous[t] for t in tokens if t in previous]
                    self.acquisition.save_batch(result)
                result['complete'] = all(r['state'] == 'submitted' for r in result['items'])
                self.acquisition.save_batch(result)
                return result
            finally:
                self.acquisition.release_lease(lease_key, self.owner)

    def reserve_intent(self, token, request_key):
        if not isinstance(request_key, str) or not request_key.strip() or len(request_key) > 160:
            raise ValueError('An idempotency key is required')
        with self._lock:
            with self.acquisition.connection() as db:
                prior = db.execute('SELECT * FROM intents WHERE request_key=?', (request_key,)).fetchone()
            if prior:
                if prior['decision_token'] != token and self.acquisition.decision(prior['decision_token'], max_age=365*86400).get('origin_token') != token:
                    raise ValueError('Idempotency key belongs to a different decision')
                if prior['state'] in {'failed_terminal','cancelled'}:
                    raise ValueError('This download failed validation; search and review again')
                job = self.manager().jobs.get(prior['info_hash'])
                if job and job.get('acquisition_id') == prior['id']:
                    return {'intent': dict(prior), 'decision':self.acquisition.decision(prior['decision_token'], max_age=float('inf'))}
            decision = self.acquisition.decision(token, max_age=365*86400 if prior else 900)
            target, series, episodes = self.target(**decision['request'])
            profile = self.acquisition.profile(decision['profile_id'])
            if profile['version'] != decision['profile_version']:
                raise ValueError('Profile changed; review the release again')
            ordinary = decision.get('manual', True) or (decision.get('search_request') or {}).get('missing_only')
            if ordinary and not decision['request'].get('upgrade') and any(ep.get('available') for ep in episodes):
                raise ValueError('An episode is now available locally; search again or explicitly select upgrades')
            with self.acquisition.connection() as db:
                claims = {r['target']: r['intent_id'] for r in db.execute('SELECT * FROM intent_claims')}
            if any(claims.get(f"tv:episode:{ep['id']}") not in {None, prior['id'] if prior else None} for ep in episodes):
                raise ValueError('An acquisition is already outstanding for an episode; search again for the remaining episodes')
            owned = [version['facts'] for ep in episodes for version in ep['versions'] if version['available']]
            candidate = dict(decision['candidate'])
            if not decision.get('manual', True):
                candidate['trusted_indexer'] = str(candidate.get('indexer_id') or '') in {str(value) for value in self.trusted_indexers()}
            current = evaluate_release(candidate, target, profile, manual=decision.get('manual', True), owned=owned, blocked=self.acquisition.blocked(target['key'], decision['candidate']['info_hash']))
            if not current['accepted']:
                raise ValueError('; '.join(row['message'] for row in current['reasons']))
            roots = [Path(root).resolve() for root in self.roots()]
            if not any(root.is_dir() for root in roots):
                raise ValueError('Configure an existing TV library root before download')
            manager = self.manager()
            staging = manager.staging_dir.resolve()
            if any(staging == root or staging in root.parents or root in staging.parents for root in roots):
                raise ValueError('TV library and torrent staging must be separate')
            destination = self.repository.resolve_import_destination(series.get('id'), decision['request']['season'], roots, metadata=series)
            recorded = self.acquisition.decision(prior['decision_token'], max_age=365*86400) if prior else decision
            if not self._same_destination(recorded.get('import_destination'), destination):
                raise ValueError('Destination changed; search and review again')
            if destination['state'] != 'ready':
                raise ValueError(destination['reason'])
            staging.mkdir(parents=True, exist_ok=True)
            pending = sum(int(item.get('expected_size') or 0) for item in manager.jobs.all().values() if item.get('state') not in {'imported', 'cancelled', 'rolled_back', 'validation_failed'} and item.get('expected_info_hash') != current['candidate']['info_hash'])
            unreserved = max(0, shutil.disk_usage(staging).free - pending)
            if unreserved < current['estimated_bytes']:
                raise ValueError('Insufficient unreserved torrent staging space')
            existing = manager.jobs.get(current['candidate']['info_hash'])
            if existing and (not prior or existing.get('acquisition_id') != prior['id']):
                raise ValueError('Torrent already belongs to another acquisition')
            # Only a validated Download action may turn a provider preview into
            # tracked local rows. Ordinary search/resolve remains read-only.
            decision = self._materialize(decision)
            target, series, episodes = self.target(**decision['request'])
            materialized = self.repository.resolve_import_destination(series['id'], decision['request']['season'], roots)
            if not self._same_destination(destination, materialized):
                raise ValueError('Destination changed after metadata refresh; search and review again')
            self.repository.reserve_import_home(series['id'], materialized, roots)
            intent = self.acquisition.intent(request_key, decision)
            existing = manager.jobs.get(intent['info_hash'])
            if existing:
                if existing.get('acquisition_id') != intent['id']:
                    raise ValueError('Torrent already belongs to another acquisition')
                return {'intent': intent, 'decision':decision}
            with self.acquisition.connection() as db:
                attempted = db.execute("SELECT 1 FROM events WHERE intent_id=? AND event IN ('submission_started','submission_failed') LIMIT 1",(intent['id'],)).fetchone()
            return {'intent':intent, 'decision':decision, 'target':target, 'profile':profile, 'destination':destination,
                    'staging':staging, 'unreserved':unreserved, 'estimated_bytes':current['estimated_bytes'], 'submission_retry':bool(attempted)}

    def submit(self, token, request_key):
        with self._lock:
            reservation = self.reserve_intent(token, request_key)
            intent, decision = reservation['intent'], reservation['decision']
            manager = self.manager()
            existing = manager.jobs.get(intent['info_hash'])
            if existing and existing.get('acquisition_id') == intent['id']:
                if intent['state']=='selected':
                    self.acquisition.event(intent['id'],'submitted',{'info_hash':intent['info_hash'],'recovered':True},state='submitted')
                return {'intent':intent, 'job':existing}
            target, profile, destination, staging = (reservation[key] for key in ('target','profile','destination','staging'))
            current = {'estimated_bytes':reservation['estimated_bytes']}
            unreserved = reservation['unreserved']
            if not self.acquisition.lease('submit:'+target['key'], self.owner, reserved_bytes=current['estimated_bytes'], available_bytes=unreserved):
                raise ValueError('Another worker owns this target or disk reservation')
            metadata = {'media_type': 'tv', 'acquisition_id': intent['id'], 'target_key': target['key'], 'tv_request': decision['request'],
                        'submission_retry': reservation['submission_retry'],
                        'profile_id': profile['id'], 'profile_version': profile['version'], 'decision_token': token,
                        'title': decision['candidate']['title'], 'expected_info_hash': intent['info_hash'], 'expected_size': current['estimated_bytes'],
                        'destination': destination['path'], 'import_destination': destination,
                        'tv_download_staging_root': str(staging),
                        'tv_lifecycle_version': 1, 'import_mode': 'move',
                        'seeding_policy': {'seeding_mode': 'none'},
                        'retry_policy': {key: profile[key] for key in ('retry_max_attempts', 'retry_backoff_seconds')}}
            try:
                self.acquisition.event(intent['id'],'submission_started')
                job = self.submit_candidate(manager, decision['candidate'], metadata) if self.submit_candidate else manager.submit_magnet(decision['candidate']['magnet_url'], metadata)
                self.acquisition.event(intent['id'], 'submitted', {'info_hash': intent['info_hash']}, state='submitted')
                return {'intent': intent, 'job': job}
            except Exception as error:
                self.acquisition.event(intent['id'], 'submission_failed', {'reason': str(error)},
                                       state='failed_terminal' if isinstance(error, TorrentValidationError) else None)
                raise
            finally:
                self.acquisition.release_lease('submit:'+target['key'], self.owner)

    def validate_manifest(self, job, files):
        target, series, episodes = self.target(**job['tv_request'])
        decision = self.acquisition.decision(job['decision_token'], max_age=365*86400)
        profile = self.acquisition.profile(job['profile_id'])
        if not target['released'] or profile['version'] != job['profile_version']:
            raise TorrentValidationError('TV decision changed before manifest validation')
        mappings, covered, names, skipped = [], set(), [], []
        for file in files:
            name = str(file.get('name') or file.get('path') or '')
            if Path(name).suffix.lower() not in VIDEO_EXTENSIONS:
                continue
            claim = parse_episode_name(name)
            if claim['ignored']:
                skipped.append(name)
                continue
            identity = series_identity({'title': Path(name).name}, series)
            if identity['title'] and identity['state'] == 'conflict':
                raise TorrentValidationError('Torrent filenames identify a different series')
            result = resolve_episode_claim(claim, self.repository.episodes(series['id']))
            if result['state'] != 'accepted':
                raise TorrentValidationError('Pack contains ambiguous or unrelated episodes')
            selected = set(result['episode_ids']) & set(target['episode_ids'])
            if not selected:
                skipped.append(name)
                continue
            extras = set(result['episode_ids']) - set(target['episode_ids'])
            if extras and not decision['candidate'].get('allow_extras'):
                raise TorrentValidationError('A combined file includes unselected episodes; review and explicitly allow extras')
            names.append(name)
            covered.update(selected)
            mappings.append({'name': name, 'episode_ids': sorted(selected)})
        candidate = {**decision['candidate'], 'manifest_names': names, 'episode_ids': sorted(covered)}
        verified = evaluate_release(candidate, target, profile, manual=True, blocked=self.acquisition.blocked(target['key'], job['expected_info_hash']))
        if not verified['accepted']:
            raise TorrentValidationError('; '.join(reason['message'] for reason in verified['reasons']))
        return {'mappings': mappings, 'episode_ids': sorted(covered), 'skipped_files': skipped}

    def process_completed(self, manager, torrent_hash, job, torrent):
        if job.get('tv_lifecycle_version') == 1:
            return self.complete_normal_import(manager, torrent_hash, job, torrent)
        if job.get('state') in {'imported', 'partial_import'}:
            return self.maintain_seeding(manager, torrent_hash, job, torrent)
        if job.get('state') == 'retry_wait':
            if self.clock() < float(job.get('next_retry_at') or 0):
                return job
            job = manager.jobs.upsert(torrent_hash, {'state': 'importing', 'last_error': ''})
        if job.get('state') in {'rolled_back', 'cancelled', 'validation_failed', 'needs_review', 'seed_complete', 'partial_seed_complete'}:
            return job
        recovering = bool(job.get('preserving_import_plan') and job.get('tv_verified_mapping'))
        if not recovering and (not torrent or float(torrent.get('progress') or 0) < 1):
            return job
        try:
            if recovering:
                mapping = job['tv_verified_mapping']
                sources = [Path(row['source']) for row in job['preserving_import_plan']]
            else:
                files = manager.client.files(torrent['hash'])
                mapping = self.validate_manifest(job, files)
                source_root = Path(torrent.get('save_path') or manager.staging_dir).resolve()
                sources = [source_root / item['name'] for item in mapping['mappings']]
            facts, valid_sources, valid_mappings, failures = [], [], [], []
            claimed = release_claims(job['title'])['resolution']
            for item, path in zip(mapping['mappings'], sources):
                if manager.staging_dir.resolve() not in path.resolve().parents:
                    raise ValueError('Completed file escaped staging')
                measured = self.probe(str(path))
                measured = asdict(measured) if is_dataclass(measured) else dict(measured)
                if measured.get('probe_status') != 'ok':
                    failures.append({'name': item['name'], 'reason': 'Completed video could not be verified'})
                    continue
                actual = '2160p' if measured.get('quality_class') == '4K' else measured.get('quality_class')
                if claimed != 'unknown' and actual != claimed:
                    failures.append({'name': item['name'], 'reason': 'Measured resolution contradicts the selected release'})
                    continue
                valid_sources.append(path)
                valid_mappings.append(item)
                facts.append(measured)
            if not valid_sources:
                raise ValueError(failures[0]['reason'] if failures else 'No verified video files remain')
            verified_mapping = {'mappings': valid_mappings,
                                'episode_ids': sorted({episode_id for item in valid_mappings for episode_id in item['episode_ids']})}
            manager.jobs.upsert(torrent_hash, {'tv_verified_mapping': verified_mapping})
            imported = import_verified_files(manager.jobs, torrent_hash, valid_sources, manager.staging_dir, job['destination'], mode=job.get('import_mode', 'hardlink_copy'))
            self.repository.bind_files([{'path': plan['target'], 'episode_ids': item['episode_ids'], 'facts': measured} for item, plan, measured in zip(valid_mappings, imported['preserving_import_plan'], facts)], self.roots())
            state = 'partial_import' if failures else 'imported'
            result = manager.jobs.upsert(torrent_hash, {'state': state, 'library_scan_pending': False,
                'tv_import': {'imported_files': len(valid_sources), 'covered_episodes': verified_mapping['episode_ids'],
                              'failed_files': len(failures), 'failures': failures},
                'identity_handoff': {'state': 'tv_published'}, 'seed_started_at': self.clock(),
                'retry_attempts': int(job.get('retry_attempts') or 0)})
            event = 'partial_import' if failures else 'imported'
            self.acquisition.event(job['acquisition_id'], event,
                                   {'episode_ids': verified_mapping['episode_ids'], 'failures': failures}, state='ready')
            if failures:
                return self.maintain_seeding(manager, torrent_hash, result, torrent)
            return self.maintain_seeding(manager, torrent_hash, result, torrent)
        except OSError as error:
            policy = job.get('retry_policy') or {'retry_max_attempts': 3, 'retry_backoff_seconds': 300}
            attempts = int(job.get('retry_attempts') or 0) + 1
            maximum = int(policy.get('retry_max_attempts') or 0)
            if attempts <= maximum:
                delay = int(policy.get('retry_backoff_seconds') or 300) * (2 ** (attempts - 1))
                self.acquisition.event(job['acquisition_id'], 'import_retry_scheduled', {'reason': str(error), 'attempt': attempts, 'delay_seconds': delay}, state='import_pending')
                return manager.jobs.upsert(torrent_hash, {'state': 'retry_wait', 'last_error': str(error), 'retry_attempts': attempts, 'next_retry_at': self.clock() + delay})
            self.acquisition.block(job['target_key'], torrent_hash, 'Import retry limit reached')
            self.acquisition.event(job['acquisition_id'], 'import_failed_terminal', {'reason': str(error), 'attempts': attempts}, state='failed_terminal')
            return manager.jobs.upsert(torrent_hash, {'state': 'needs_review', 'last_error': str(error), 'retry_attempts': attempts})
        except Exception as error:
            self.acquisition.event(job['acquisition_id'], 'import_needs_review', {'reason': str(error)}, state='import_pending')
            return manager.jobs.upsert(torrent_hash, {'state': 'needs_review', 'last_error': str(error)})

    def complete_normal_import(self, manager, torrent_hash, job, torrent):
        if job.get('state') in {'imported', 'partial_import', 'cleanup_failed', 'rolled_back', 'cancelled', 'validation_failed', 'needs_review'}:
            return job
        if job.get('state') == 'retry_wait':
            if self.clock() < float(job.get('next_retry_at') or 0):
                return job
            job = manager.jobs.upsert(torrent_hash, {'state': 'importing', 'last_error': ''})
        if not job.get('tv_selected_files') and (not torrent or float(torrent.get('progress') or 0) < 1):
            return job
        try:
            target, series, _ = self.target(**job['tv_request'])
            current = self.repository.resolve_import_destination(series['id'], job['tv_request']['season'], self.roots(), publication=job)
            if not self._same_destination(current, job['import_destination']) or current['state'] != 'ready' or current['path'] != job['destination']:
                raise ValueError('Snapshotted destination changed or is no longer approved; review required')
            if self.acquisition.blocked(job['target_key'], torrent_hash):
                raise ValueError('This release is blocklisted; cleanup requires review')
            selected = job.get('tv_selected_files')
            if not selected:
                mapping = self.validate_manifest(job, manager.client.files(torrent['hash']))
                source_root = Path(torrent.get('save_path') or manager.staging_dir)
                if source_root != manager.staging_dir:
                    source_root = verified_staging_source(source_root, manager.staging_dir)
                source_root = source_root.resolve()
                if source_root != manager.staging_dir.resolve() and manager.staging_dir.resolve() not in source_root.parents:
                    raise ValueError('Completed payload escaped staging')
                selected, failures = [], []
                claimed = release_claims(job['title'])['resolution']
                for item in mapping['mappings']:
                    source = (source_root / item['name']).resolve()
                    if manager.staging_dir.resolve() not in source.parents:
                        raise ValueError('Completed file escaped staging')
                    measured = self.probe(str(source))
                    measured = asdict(measured) if is_dataclass(measured) else dict(measured)
                    actual = '2160p' if measured.get('quality_class') == '4K' else measured.get('quality_class')
                    if measured.get('probe_status') != 'ok' or (claimed != 'unknown' and actual != claimed):
                        failures.append({'name': item['name'], 'reason': 'Completed video could not be verified' if measured.get('probe_status') != 'ok' else 'Measured resolution contradicts the selected release'})
                    else:
                        selected.append({**item, 'source': str(source), 'facts': measured})
                auxiliary = []
                for name in mapping['skipped_files']:
                    if not parse_episode_name(name)['ignored']:
                        continue
                    path = source_root / name
                    source = verified_staging_source(path, manager.staging_dir)
                    if source.is_file():
                        before = source.stat()
                        digest = sha256(source)
                        after = source.stat()
                        if verified_staging_source(path, manager.staging_dir) != source:
                            raise ValueError('Auxiliary source path changed before its cleanup snapshot')
                        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                            raise ValueError('Auxiliary source changed before its cleanup snapshot')
                        auxiliary.append({'name': name, 'source': str(source), 'size': after.st_size, 'sha256': digest})
                job = manager.jobs.upsert(torrent_hash, {'tv_selected_files': selected, 'tv_auxiliary_files': auxiliary, 'tv_staging_root': str(source_root),
                    'tv_verified_mapping': {'mappings': selected, 'episode_ids': sorted({ep for row in selected for ep in row['episode_ids']})},
                    'tv_import': {'imported_files': 0, 'verified_files': len(selected), 'failed_files': len(failures), 'failures': failures,
                                  'covered_episodes': sorted({ep for row in selected for ep in row['episode_ids']})}})
                if not selected:
                    raise ValueError(failures[0]['reason'] if failures else 'No verified video files remain')
            if current.get('origin') == 'metadata':
                home, folder = Path(current['show_home']), Path(current['path'])
                if not home.exists():
                    manager.jobs.upsert(torrent_hash, {'tv_home_creation': {'state': 'planned', 'path': str(home)}})
                    home.mkdir(exist_ok=False)
                    job = manager.jobs.upsert(torrent_hash, {'tv_created_home': str(home), 'tv_home_creation': {'state': 'created', 'path': str(home)}})
                if not folder.exists():
                    manager.jobs.upsert(torrent_hash, {'tv_season_creation': {'state': 'planned', 'path': str(folder)}})
                    folder.mkdir(exist_ok=False)
                    job = manager.jobs.upsert(torrent_hash, {'tv_created_seasons': list(dict.fromkeys(job.get('tv_created_seasons', []) + [str(folder)])), 'tv_season_creation': {'state': 'created', 'path': str(folder)}})
            publication = job.get('tv_publication') or {}
            if publication.get('state') != 'committed':
                imported = import_verified_files(manager.jobs, torrent_hash, [row['source'] for row in selected],
                    manager.staging_dir, job['destination'], mode='move', upgrade=bool(job['tv_request'].get('upgrade')))
                plan = imported['preserving_import_plan']
                entries = []
                for row, item in zip(plan, selected):
                    existing = self.repository.binding_episode_ids(row['target'])
                    row.setdefault('binding_pre_existing', bool(existing))
                    manager.jobs.upsert(torrent_hash, {'preserving_import_plan': plan})
                    if existing and existing != set(item['episode_ids']):
                        raise ValueError('Destination has conflicting TV episode bindings; review required')
                    # Preserve this fact across a crash after binding but before its journal checkpoint.
                    entries.append({'path': row['target'], 'episode_ids': item['episode_ids'], 'facts': item['facts']})
                manager.jobs.upsert(torrent_hash, {'preserving_import_plan': plan, 'tv_publication': {'state': 'prepared', 'entries': entries}})
                self.repository.bind_files(entries, self.roots())
                job = manager.jobs.upsert(torrent_hash, {'tv_publication': {'state': 'committed', 'entries': entries},
                    'tv_import': {**job['tv_import'], 'imported_files': len(selected)},
                    'library_scan_pending': False, 'identity_handoff': {'state': 'tv_published'}})
            else:
                entries = publication['entries']
            for entry in entries:
                if self.repository.binding_episode_ids(entry['path']) != set(entry['episode_ids']):
                    raise ValueError('Committed TV binding changed; cleanup requires review')
            if job['tv_import']['failed_files']:
                if torrent:
                    manager.client.pause(torrent['hash'])
                self.acquisition.event(job['acquisition_id'], 'partial_import', job['tv_import'], state='ready')
                return manager.jobs.upsert(torrent_hash, {'state': 'partial_import', 'source_retained': True,
                    'rollback_available': True, 'last_error': 'Partial import; recovery sources retained'})
            # From here a rollback cannot restore a removed transfer. Recovery finishes cleanup.
            if not job.get('torrent_removed'):
                job = manager.jobs.upsert(torrent_hash, {'cleanup_started': True, 'rollback_available': False,
                                                       'torrent_removal_started': True})
                if torrent:
                    manager.client.pause(torrent['hash'])
                    manager.client.remove_without_files(torrent['hash'])
                job = manager.jobs.upsert(torrent_hash, {'torrent_removed': True})
            result = finalize_verified_move(manager.jobs, torrent_hash, manager.staging_dir)
            self.acquisition.event(job['acquisition_id'], 'imported', job['tv_import'], state='ready')
            return result
        except Exception as error:
            latest = manager.jobs.get(torrent_hash)
            if torrent and float(torrent.get('progress') or 0) >= 1 and not latest.get('torrent_removed'):
                try:
                    manager.client.pause(torrent['hash'])
                except Exception as pause_error:
                    manager.jobs.upsert(torrent_hash, {'pause_error': str(pause_error)})
            if latest.get('tv_publication', {}).get('state') == 'committed' and not latest.get('tv_import', {}).get('failed_files'):
                self.acquisition.event(job['acquisition_id'], 'cleanup_failed', {'reason': str(error)}, state='import_pending')
                return manager.jobs.upsert(torrent_hash, {'state': 'cleanup_failed', 'last_error': str(error)})
            if isinstance(error, OSError):
                policy = job.get('retry_policy') or {'retry_max_attempts': 3, 'retry_backoff_seconds': 300}
                attempts = int(job.get('retry_attempts') or 0) + 1
                if attempts <= int(policy.get('retry_max_attempts') or 0):
                    delay = int(policy.get('retry_backoff_seconds') or 300) * 2 ** (attempts - 1)
                    self.acquisition.event(job['acquisition_id'], 'import_retry_scheduled', {'reason': str(error), 'attempt': attempts}, state='import_pending')
                    return manager.jobs.upsert(torrent_hash, {'state': 'retry_wait', 'last_error': str(error), 'retry_attempts': attempts, 'next_retry_at': self.clock() + delay})
                self.acquisition.block(job['target_key'], torrent_hash, 'Import retry limit reached')
            self.acquisition.event(job['acquisition_id'], 'import_needs_review', {'reason': str(error)}, state='import_pending')
            return manager.jobs.upsert(torrent_hash, {'state': 'needs_review', 'last_error': str(error)})

    def maintain_seeding(self, manager, torrent_hash, job, torrent):
        policy = job.get('seeding_policy') or {'seeding_mode': 'forever', 'seed_ratio': 1.0, 'seed_time_seconds': 0}
        mode = policy.get('seeding_mode', 'forever')
        if mode == 'forever' or not torrent:
            return manager.jobs.upsert(torrent_hash, {'seeding_status': 'active' if torrent else 'torrent_missing'})
        ratio = float(torrent.get('ratio') or 0)
        elapsed = max(float(torrent.get('seeding_time') or 0), self.clock() - float(job.get('seed_started_at') or self.clock()))
        ratio_met = ratio >= float(policy.get('seed_ratio') or 0)
        time_met = elapsed >= int(policy.get('seed_time_seconds') or 0)
        complete = (mode == 'none' or mode == 'ratio' and ratio_met or mode == 'time' and time_met
                    or mode == 'ratio_or_time' and (ratio_met or time_met)
                    or mode == 'ratio_and_time' and ratio_met and time_met)
        if not complete:
            return manager.jobs.upsert(torrent_hash, {'seeding_status': 'active', 'seed_ratio': ratio, 'seed_time_seconds': int(elapsed)})
        manager.client.pause(torrent['hash'])
        manager.client.remove_without_files(torrent['hash'])
        self.acquisition.event(job['acquisition_id'], 'seeding_complete', {'ratio': ratio, 'seconds': int(elapsed)}, state='ready')
        state = 'partial_seed_complete' if job.get('state') == 'partial_import' else 'seed_complete'
        return manager.jobs.upsert(torrent_hash, {'state': state, 'seeding_status': 'complete', 'seed_ratio': ratio, 'seed_time_seconds': int(elapsed), 'source_retained': True})

    def manage(self, intent_id, operation):
        if operation not in {'retry', 'cancel', 'block', 'rollback'}:
            raise ValueError('Unsupported acquisition action')
        with self._lock:
            with self.acquisition.connection() as db:
                row = db.execute('SELECT * FROM intents WHERE id=?', (intent_id,)).fetchone()
            if not row:
                raise LookupError('Acquisition not found')
            manager = self.manager()
            # Serialize against the same transfer owner used by completion processing.
            with manager._completion_lock:
                job = manager.jobs.get(row['info_hash'])
                if not job or job.get('acquisition_id') != intent_id:
                    raise ValueError('No matching transfer job; search again before retrying')
                if operation == 'retry':
                    if job['state'] not in {'needs_review', 'validation_failed', 'cleanup_failed'}:
                        raise ValueError('Only a failed or review transfer can be retried')
                    if self.acquisition.blocked(row['target'], row['info_hash']):
                        raise ValueError('This release is blocklisted; search for another candidate')
                    policy = job.get('retry_policy') or {'retry_max_attempts': 3}
                    attempts = int(job.get('retry_attempts') or 0) + 1
                    if attempts > int(policy.get('retry_max_attempts') or 0):
                        raise ValueError('Retry limit reached; search for another candidate')
                    state = 'importing' if job.get('preserving_import_plan') else 'validating'
                    result = manager.jobs.upsert(row['info_hash'], {'state': state, 'last_error': '', 'validation_started_at': self.clock(), 'validation_attempts': 0, 'retry_attempts': attempts})
                    self.acquisition.event(intent_id, 'retry_requested', state='import_pending')
                    return result
                if operation == 'rollback':
                    def unpublish(paths):
                        with self.repository.store.transaction() as db:
                            if job.get('tv_lifecycle_version') == 1:
                                expected = {row['path']: set(row['episode_ids']) for row in (job.get('tv_publication') or {}).get('entries', [])}
                                for path in paths:
                                    existing = {row[0] for row in db.execute('SELECT b.episode_id FROM episode_file_bindings b '
                                        'JOIN media_files f ON f.id=b.file_id WHERE f.path=?', (path,))}
                                    if existing and existing != expected.get(path, set()):
                                        raise ValueError('TV binding changed; rollback requires review')
                            for path in paths:
                                db.execute('UPDATE media_files SET available=0 WHERE path=?', (path,))
                    result = rollback_verified_files(manager.jobs, row['info_hash'], unpublish=unpublish)
                    self.acquisition.event(intent_id, 'rolled_back', state='cancelled')
                    return result
                if job.get('preserving_import_plan'):
                    raise ValueError('An import already started; roll back its verified publication first')
                torrent = manager.torrents_by_info_hash().get(row['info_hash'])
                if torrent:
                    manager.client.pause(torrent['hash'])
                result = manager.jobs.upsert(row['info_hash'], {'state': 'cancelled', 'last_error': 'Cancelled by user; torrent and files retained'})
                if operation == 'block':
                    self.acquisition.block(row['target'], row['info_hash'], 'Blocked by user')
                self.acquisition.event(intent_id, operation, state='cancelled')
                return result
