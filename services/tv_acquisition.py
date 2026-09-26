"""TV search/intent composition; qBittorrent alone executes transfers."""
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
import hashlib
import json
import shutil
import threading
import time
import uuid

from services.acquisition_decision import evaluate_release, rank_releases
from services.media_file_facts import probe_media_file
from services.qbittorrent import magnet_hash, normalize_torrent_info_hash, is_allowed_prowlarr_url, TorrentValidationError
from services.quality_catalog import release_claims
from services.tv_filename_parser import parse_episode_name, resolve_episode_claim, series_identity, title_key, VIDEO_EXTENSIONS
from services.verified_import import import_verified_files, rollback_verified_files


class TVAcquisition:
    def __init__(self, repository, acquisition, prowlarr, manager, roots, *, trusted_indexers=lambda: [], search_indexers=lambda: None, submit_candidate=None, metadata=None, resolve_candidate=None, probe=probe_media_file, clock=time.time):
        self.repository, self.acquisition, self.prowlarr, self.manager = repository, acquisition, prowlarr, manager
        self.roots, self.trusted_indexers, self.submit_candidate, self.probe, self.clock = roots, trusted_indexers, submit_candidate, probe, clock
        self.search_indexers = search_indexers
        self.metadata, self.resolve_candidate = metadata, resolve_candidate
        self._lock = threading.RLock()
        self.owner = uuid.uuid4().hex

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
            rows = self.repository.episodes(series['id'], season)
            if not rows and season is not None and self.metadata:
                rows = [{**r, 'provider_id': str(r['id']), 'id': -int(r['id']), 'reconciliation_required': False}
                        for r in self.metadata.preview_season(series['tmdb_id'], int(season))['items']]
        else:
            series = self.metadata.preview(int(tmdb_id))
            rows = [{**r, 'provider_id': str(r['id']), 'id': -int(r['id']), 'reconciliation_required': False}
                    for r in self.metadata.preview_season(int(tmdb_id), int(season))['items']]
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
            rows = [r for r in rows if r['released']]
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
                'episode_ids': [r['id'] for r in rows], 'released': bool(rows) and all(r['released'] and not r.get('reconciliation_required') for r in rows)}, series, rows

    @staticmethod
    def _state(decision):
        pending = {'identity_unverified', 'hash_invalid'}
        hard = [r for r in decision['reasons'] if r['code'] not in pending]
        identity = decision['candidate'].get('identity_evidence', {})
        state = 'blocked' if hard or identity.get('state') == 'conflict' else 'identity_review' if identity.get('state') == 'review' else 'resolve' if not decision['candidate']['info_hash'] else 'eligible'
        return {**decision, 'state': state, 'selectable': state in {'eligible', 'resolve'}}

    def search(self, series_id=None, season=None, episode=None, profile_id='safe-hd', *, manual=True, tmdb_id=None, episode_numbers=None, missing_only=False, upgrade=False):
        deadline = time.monotonic() + 30
        request = dict(series_id=series_id, tmdb_id=tmdb_id, season=season, episode=episode, episode_numbers=episode_numbers, missing_only=missing_only, upgrade=upgrade)
        target, series, episodes = self.target(**request)
        profile, provider = self.acquisition.profile(profile_id), self.prowlarr()
        arguments = dict(tmdb_tv_id=series['tmdb_id'], title=series['title'], season=season, episode=episode)
        report = provider.search_tv_report(**arguments, indexer_ids=self.search_indexers()) if hasattr(provider, 'search_tv_report') else {'items': provider.search_tv(**arguments, indexer_ids=self.trusted_indexers())}
        raw, report = list(report.get('items', [])), {k: v for k, v in report.items() if k != 'items'}
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
        decisions = self._release_decisions(raw, request, target, series, episodes, all_episodes, profile, provider, manual, ambiguous)
        # Bounded episode fallback shares the season search's overall budget.
        # Only providers with an explicit budget contract can be expanded here.
        if manual and season is not None and episode is None and hasattr(provider, 'search_tv_report'):
            found = {episode for decision in decisions if decision['selectable'] for episode in decision['covered_episodes']}
            missing = [ep for ep in episodes if ep['id'] not in found]
            searches = []
            for ep in missing[:4]:
                remaining = deadline - time.monotonic()
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
            decisions = self._release_decisions(raw, request, target, series, episodes, all_episodes, profile, provider, manual, ambiguous)
        ranked = rank_releases(decisions)
        uncovered, recommended = set(target['episode_ids']), []
        for row in sorted(ranked, key=lambda d: (not d['selectable'], d['sort_key'][1:4], -len(d['covered_episodes']), d['sort_key'])):
            coverage = set(row['covered_episodes'])
            if row['selectable'] and coverage and coverage <= uncovered:
                recommended.append(row['decision_token']); uncovered -= coverage
        return {'mode': 'manual' if manual else 'automatic', 'target': target, 'decisions': ranked, 'search': report,
                'recommended': recommended, 'missing_episodes': sorted(uncovered),
                'episodes': [{'id': ep['id'], 'number': ep['episode_number'], 'code': ep.get('code') or f"S{ep['season_number']:02d}E{ep['episode_number']:02d}"} for ep in episodes]}

    def _release_decisions(self, raw, request, target, series, episodes, all_episodes, profile, provider, manual, ambiguous):
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
            magnet, download = str(row.get('magnetUrl') or ''), str(row.get('downloadUrl') or '')
            if download.startswith('magnet:'): magnet, download = download, ''
            info_hash = normalize_torrent_info_hash(row.get('infoHash')) or magnet_hash(magnet)
            identity = series_identity(row, series, ambiguous=ambiguous)
            dedup = info_hash or download or (name, row.get('indexerId'))
            if dedup in seen: continue
            seen.add(dedup)
            candidate = {'title': name, 'info_hash': info_hash, 'magnet_url': magnet, 'download_url': download,
                'indexer': row.get('indexer'), 'indexer_id': str(row.get('indexerId') or row.get('indexer') or ''),
                'size_bytes': int(row.get('size') or 0), 'seeders': int(row.get('seeders') or 0),
                'episode_ids': sorted(coverage), 'identity_verified': identity['state'] == 'matched', 'identity_evidence': identity,
                'transport_verified': bool((magnet_hash(magnet) and magnet_hash(magnet) == info_hash) or (download and is_allowed_prowlarr_url(download, provider.base_url))),
                'trusted_indexer': str(row.get('indexerId') or '') in {str(value) for value in self.trusted_indexers()},
                'availability_verified': target['released'], 'published_at': row.get('published_at') or self.clock(),
                'coverage_claim': 'season_pack' if claim['scope'] == 'season' else 'episodes',
                'selection_context': request,
                'episode_numbers': [ep['episode_number'] for ep in episodes if ep['id'] in coverage]}
            # A candidate may fulfil part of a batch. Its own intent claims only that subset.
            candidate_request = {**request, 'missing_only': False}
            if manual and request['episode'] is None and request['season'] is not None and coverage:
                candidate_request['episode_numbers'] = candidate['episode_numbers']
            own_target, _, own_episodes = self.target(**candidate_request)
            owned = [v['facts'] for ep in own_episodes for v in ep['versions'] if v['available']]
            decision = evaluate_release(candidate, own_target, profile, manual=manual, owned=owned, blocked=self.acquisition.blocked(own_target['key'], info_hash), now=self.clock())
            decision.update(request=candidate_request, search_request=request, wanted_episodes=target['episode_ids'], requested_episodes=[{'id': ep['id'], 'number': ep['episode_number'], 'provider_id': ep.get('provider_id')} for ep in own_episodes])
            decision = self._state(decision)
            self.acquisition.record_decision(decision)
            decisions.append(decision)
        return decisions

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
        target, _, episodes = self.target(**decision['request'])
        original = {(r['number'], str(r.get('provider_id'))) for r in decision.get('requested_episodes', [])}
        current = {(r['episode_number'], str(r.get('provider_id'))) for r in episodes}
        if original and original != current: raise ValueError('Episode identity changed; search again')
        if original:
            candidate['episode_ids'] = target['episode_ids']
        profile = self.acquisition.profile(decision['profile_id'])
        if profile['version'] != decision['profile_version']: raise ValueError('Profile changed; review the release again')
        owned = [v['facts'] for ep in episodes for v in ep['versions'] if v['available']]
        candidate['allow_extras'] = bool(allow_extras)
        result = evaluate_release(candidate, target, profile, manual=decision['manual'], owned=owned,
                                  blocked=self.acquisition.blocked(target['key'], candidate.get('info_hash')))
        result.update(request=decision['request'], search_request=decision.get('search_request'), wanted_episodes=decision.get('wanted_episodes', []), requested_episodes=decision.get('requested_episodes', []))
        result = self._state(result)
        self.acquisition.record_decision(result)
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
        new_target, _, new_rows = self.target(**new_request)
        original = decision.get('requested_episodes')
        if original and {(r['number'], str(r.get('provider_id'))) for r in original} != {(r['episode_number'], str(r.get('provider_id'))) for r in new_rows}:
            raise ValueError('Episode identity changed; search and review again')
        if request.get('series_id') == series_id and decision['candidate']['episode_ids'] == new_target['episode_ids']:
            return decision
        candidate = {**decision['candidate'], 'episode_ids': new_target['episode_ids']}
        result = evaluate_release(candidate, new_target, self.acquisition.profile(decision['profile_id']), manual=decision['manual'])
        result.update(request=new_request, origin_token=decision['decision_token'])
        self.acquisition.record_decision(result)
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
            if len(groups) != 1: raise ValueError('Selections must belong to the same episode search')
            wanted, covered = set(decisions[0].get('wanted_episodes', [])), set()
            for decision in decisions:
                scope = set(decision['covered_episodes'])
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

    def submit(self, token, request_key):
        if not isinstance(request_key, str) or not request_key.strip() or len(request_key) > 160:
            raise ValueError('An idempotency key is required')
        with self._lock:
            with self.acquisition.connection() as db:
                prior = db.execute('SELECT * FROM intents WHERE request_key=?', (request_key,)).fetchone()
            if prior:
                if prior['decision_token'] != token and self.acquisition.decision(prior['decision_token'], max_age=365*86400).get('origin_token') != token:
                    raise ValueError('Idempotency key belongs to a different decision')
                if prior['state'] == 'failed_terminal':
                    raise ValueError('This download failed validation; search and review again')
                job = self.manager().jobs.get(prior['info_hash'])
                if job and job.get('acquisition_id') == prior['id']:
                    return {'intent': dict(prior), 'job': job}
            decision = self.acquisition.decision(token, max_age=365*86400 if prior else 900)
            target, series, episodes = self.target(**decision['request'])
            profile = self.acquisition.profile(decision['profile_id'])
            if profile['version'] != decision['profile_version']:
                raise ValueError('Profile changed; review the release again')
            if decision.get('manual', True) and not decision['request'].get('upgrade') and any(ep.get('available') for ep in episodes):
                raise ValueError('An episode is now available locally; search again or explicitly select upgrades')
            with self.acquisition.connection() as db:
                claims = {r['target']: r['intent_id'] for r in db.execute('SELECT * FROM intent_claims')}
            if any(claims.get(f"tv:episode:{ep['id']}") not in {None, prior['id'] if prior else None} for ep in episodes):
                raise ValueError('An acquisition is already outstanding for an episode; search again for the remaining episodes')
            owned = [version['facts'] for ep in episodes for version in ep['versions'] if version['available']]
            current = evaluate_release(decision['candidate'], target, profile, manual=decision.get('manual', True), owned=owned, blocked=self.acquisition.blocked(target['key'], decision['candidate']['info_hash']))
            if not current['accepted']:
                raise ValueError('; '.join(row['message'] for row in current['reasons']))
            roots = [Path(root).resolve() for root in self.roots()]
            if not roots or not roots[0].is_dir():
                raise ValueError('Configure an existing TV library root before download')
            manager = self.manager()
            staging = manager.staging_dir.resolve()
            if staging == roots[0] or staging in roots[0].parents or roots[0] in staging.parents:
                raise ValueError('TV library and torrent staging must be separate')
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
            intent = self.acquisition.intent(request_key, decision)
            existing = manager.jobs.get(intent['info_hash'])
            if existing:
                if existing.get('acquisition_id') != intent['id']:
                    raise ValueError('Torrent already belongs to another acquisition')
                return {'intent': intent, 'job': existing}
            if not self.acquisition.lease('submit:'+target['key'], self.owner, reserved_bytes=current['estimated_bytes'], available_bytes=unreserved):
                raise ValueError('Another worker owns this target or disk reservation')
            metadata = {'media_type': 'tv', 'acquisition_id': intent['id'], 'target_key': target['key'], 'tv_request': decision['request'],
                        'submission_retry': bool(prior),
                        'profile_id': profile['id'], 'profile_version': profile['version'], 'decision_token': token,
                        'title': decision['candidate']['title'], 'expected_info_hash': intent['info_hash'], 'expected_size': current['estimated_bytes'],
                        'destination': str(roots[0] / f"{series['tmdb_id']}"), 'import_mode': 'copy' if profile['import_mode'] == 'copy' else 'hardlink_copy',
                        'seeding_policy': {key: profile[key] for key in ('seeding_mode', 'seed_ratio', 'seed_time_seconds')},
                        'retry_policy': {key: profile[key] for key in ('retry_max_attempts', 'retry_backoff_seconds')}}
            try:
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
                files = manager.client.files(torrent_hash)
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
        manager.client.pause(torrent_hash)
        manager.client.remove_without_files(torrent_hash)
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
                    if job['state'] not in {'needs_review', 'validation_failed'}:
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
                            for path in paths:
                                db.execute('UPDATE media_files SET available=0 WHERE path=?', (path,))
                    result = rollback_verified_files(manager.jobs, row['info_hash'], unpublish=unpublish)
                    self.acquisition.event(intent_id, 'rolled_back', state='cancelled')
                    return result
                if job.get('preserving_import_plan'):
                    raise ValueError('An import already started; roll back its verified publication first')
                manager.client.pause(row['info_hash'])
                result = manager.jobs.upsert(row['info_hash'], {'state': 'cancelled', 'last_error': 'Cancelled by user; torrent and files retained'})
                if operation == 'block':
                    self.acquisition.block(row['target'], row['info_hash'], 'Blocked by user')
                self.acquisition.event(intent_id, operation, state='cancelled')
                return result
