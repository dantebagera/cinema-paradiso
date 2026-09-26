"""Movie acquisition orchestration extracted without changing compatibility decisions.

Ports inject existing identity, provider and curation owners. Shared quality policy
is shadow-evaluated separately until parity permits an explicit cutover.
"""
import concurrent.futures
import re
import time
from services.acquisition_profiles import default_profile
from services.acquisition_decision import shadow_compare
from services.qbittorrent import magnet_hash


class MovieAcquisition:
    def __init__(self, ports):
        self.ports = ports

    def search_movie(self, indexer_ids, movie, limit=100, categories='2000', timeout=30, deadline_seconds=None, *, enriched=False, accept_result=None, stop_after_first=False):
        movie = dict(movie or {}) if enriched else self.ports._movie_with_source_title_aliases(movie)
        deadline_at = None
        if deadline_seconds:
            deadline_at = time.monotonic() + max(1, int(deadline_seconds))
        merged = []
        seen = set()
        for query_item in self.ports._movie_release_query_plan(movie):
            query = query_item['query']
            if merged and query_item['kind'] == 'alias':
                break
            query_timeout = self.ports._remaining_timeout(deadline_at, timeout)
            if query_timeout <= 0:
                break
            try:
                results = self.ports._prowlarr_search(indexer_ids=indexer_ids, query=query, limit=limit, categories=categories, timeout=query_timeout)
            except Exception as error:
                if self.ports._is_timeout_error(error):
                    continue
                raise
            for result in results:
                if not self.ports._prowlarr_result_matches_movie(result, movie):
                    continue
                if not self.ports._yts_result_matches_movie_identity(result, movie):
                    continue
                if accept_result is not None and (not accept_result(result)):
                    continue
                key = self.ports._prowlarr_result_key(result)
                if key in seen:
                    continue
                seen.add(key)
                merged.append(result)
                if stop_after_first:
                    return merged
                if len(merged) >= limit:
                    return merged
        return merged

    def variants(self, results):
        variants = []
        for r in results or []:
            t = r.get('title', '')
            if self.ports._TV_RE.search(t):
                continue
            tl = t.lower()
            res = 'Unknown'
            if '2160p' in tl or '4k' in tl or 'uhd' in tl:
                res = '4K'
            elif '1080p' in tl or re.search('[.\\-_ \\[(]1080[.\\-_ \\])]', tl):
                res = '1080p'
            elif '720p' in tl or re.search('[.\\-_ \\[(]720[.\\-_ \\])]', tl):
                res = '720p'
            elif '480p' in tl or re.search('[.\\-_ \\[(]480[.\\-_ \\])]', tl):
                res = '480p'
            size = r.get('size', 0)
            seeders = r.get('seeders', 0)
            links = self.ports._prowlarr_result_links(r)
            entry = {'resolution': res, 'seeders': seeders, 'magnet_url': links['magnet_url'], 'download_url': links['download_url'], 'info_hash': links['info_hash'], 'info_url': r.get('infoUrl', ''), 'indexer': r.get('indexer', ''), 'size_human': self.ports.format_size(size) if size else '?', 'size_bytes': size, 'title': t}
            variants.append(entry)
        return self.ports._sort_source_variants(variants)

    def sort_variants(self, variants):
        rows = list(variants or [])
        has_hd = any((row.get('resolution') in ('4K', '1080p') for row in rows))
        if has_hd:
            rows.sort(key=lambda row: (0 if row.get('resolution') == '4K' else 1 if row.get('resolution') == '1080p' else 2, -int(row.get('seeders') or 0)))
        else:
            rows.sort(key=lambda row: -int(row.get('seeders') or 0))
        return rows

    def proper_release(self, title):
        if not title or self.ports._BAD_RELEASE_RE.search(title):
            return None
        source = self.ports.get_rip_source(title)
        resolution = self.ports.get_resolution(title)
        if source not in self.ports._GOOD_RELEASE_SOURCES or self.ports.get_resolution_rank_str(resolution) < 3:
            return None
        return {'source': source, 'resolution': resolution}

    def check_followed(self):
        scan_started = time.perf_counter()
        store = self.ports._curation_store()
        current = self.ports._backfill_followed_release_dates(store, store.followed_all())
        removed_owned = []
        newly_available = []
        now = time.time()
        owned_matches = self.ports._find_owned_movies(current)
        rss_candidates = []
        scan_updates = []
        skipped = {'available': 0, 'unreleased': 0, 'not_due': 0, 'unverified_identity': 0}
        for item, owned in zip(current, owned_matches):
            if owned:
                removed_owned.append({**item, 'status': 'owned', 'owned': owned, 'updated_at': now, 'last_checked': now})
                continue
            try:
                enriched = self.ports._movie_with_source_title_aliases(item, allow_alias_fetch=False)
            except Exception:
                enriched = dict(item)
            if enriched.get('imdb_id') and enriched.get('imdb_id') != item.get('imdb_id'):
                scan_updates.append(self.ports._followed_scan_update(item, {'imdb_id': enriched['imdb_id']}))
            if not self.ports._movie_imdb_id(enriched):
                skipped['unverified_identity'] += 1
                continue
            if str(item.get('status') or 'watching') == 'available':
                if not self.ports._followed_release_has_mismatched_yts_identity(enriched):
                    skipped['available'] += 1
                    continue
                enriched = {**enriched, 'status': 'watching', 'best_release': {}, 'next_check_at': 0}
            rss_candidates.append(enriched)
        store.apply_followed_scan(removals=removed_owned)
        rss_candidates.sort(key=self.ports._followed_release_priority)
        context = self.ports._followed_release_search_context() if rss_candidates else {'ready': False, 'indexers': []}
        pending = list(rss_candidates)
        rss_matches = 0
        prowlarr_searches = 0
        failed_searches = 0
        trusted_yts = any((self.ports._is_yts_indexer_name(indexer.get('name')) for indexer in context.get('indexers', [])))
        if pending and trusted_yts:
            rss_rows = self.ports._fetch_yts_rss_latest(limit=100, timeout=self.ports.FOLLOWED_RELEASE_RSS_TIMEOUT_SECONDS)
            unmatched = []
            for item in pending:
                release = self.ports._followed_rss_release(item, rss_rows)
                if not release:
                    unmatched.append(item)
                    continue
                patch = self.ports._followed_release_available_patch(release, now)
                scan_updates.append(self.ports._followed_scan_update(item, patch))
                newly_available.append({**item, **patch})
                rss_matches += 1
            pending = unmatched
        pending = self.ports._backfill_followed_release_dates(store, pending)
        eligible = []
        for item in pending:
            eligibility = self.ports._followed_release_eligibility(item, now)
            if eligibility['eligible']:
                eligible.append(item)
                continue
            skipped[eligibility['reason']] += 1
            if eligibility['patch']:
                scan_updates.append(self.ports._followed_scan_update(item, eligibility['patch']))
        eligible.sort(key=self.ports._followed_release_priority)
        if eligible and context.get('ready'):
            worker_count = max(1, min(self.ports.FOLLOWED_RELEASE_WORKERS, len(eligible)))
            with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as executor:
                futures = {executor.submit(self.ports._probe_followed_release, item, context): item for item in eligible}
                for future in concurrent.futures.as_completed(futures):
                    item = futures[future]
                    prowlarr_searches += 1
                    try:
                        result = future.result()
                    except Exception:
                        result = {'searched': False, 'release': None}
                    if not result.get('searched'):
                        scan_updates.append(self.ports._followed_scan_update(item, self.ports._followed_release_failure_patch(now)))
                        failed_searches += 1
                        continue
                    release = result.get('release')
                    if release:
                        patch = self.ports._followed_release_available_patch(release, now)
                        newly_available.append({**item, **patch})
                    else:
                        patch = self.ports._followed_release_miss_patch(item, now)
                    scan_updates.append(self.ports._followed_scan_update(item, patch))
        elif eligible:
            failed_searches = len(eligible)
            scan_updates.extend((self.ports._followed_scan_update(item, self.ports._followed_release_failure_patch(now)) for item in eligible))
        merged = self.ports._sort_followed_releases(store.apply_followed_scan(updates=scan_updates))
        return {'movies': merged, 'removed_owned': removed_owned, 'newly_available': newly_available, 'checked_at': now, 'scan_stats': {'total': len(current), 'rss_candidates': len(rss_candidates), 'eligible': len(eligible), 'rss_matches': rss_matches, 'prowlarr_searches': prowlarr_searches, 'failed_searches': failed_searches, 'skipped': skipped, 'duration_ms': round((time.perf_counter() - scan_started) * 1000, 1)}}

    def best_variant(self, variants, quality, trusted_ids):
        wanted = self.ports._normalize_download_quality(quality)
        trusted = {str(value) for value in trusted_ids or []}
        candidates = []
        for variant in variants or []:
            indexer_id = str(variant.get('indexer_id') or variant.get('indexer') or '')
            if trusted and indexer_id not in trusted:
                continue
            if self.ports._download_variant_quality(variant.get('resolution')) != wanted:
                continue
            candidates.append(variant)
        candidates.sort(key=lambda item: (int(item.get('seeders') or 0), int(item.get('size') or item.get('size_bytes') or 0)), reverse=True)
        return candidates[0] if candidates else None

    def variants_by_quality(self, variants, trusted_ids):
        return {quality: self.ports._best_download_variant(variants, quality, trusted_ids) for quality in ('1080p', '4K')}

    def review(self, movie, quality, trusted_ids):
        payload = self.ports._normalize_curated_movie(movie)
        profile_id = str((movie or {}).get('profile_id') or '').strip()
        if profile_id:
            payload['profile_id'] = profile_id
        selection_key = str((movie or {}).get('selection_key') or '').strip()
        if selection_key:
            payload['selection_key'] = selection_key
        if not self.ports._download_job_has_stable_identity(payload):
            return {**payload, 'quality': quality, 'upgrade': False, 'selected': False, 'status': 'identity_required', 'variant': None, 'variants_by_quality': {'1080p': None, '4K': None}, 'reason': 'A TMDB or IMDb identity is required before download'}
        upgrade = self.ports._curated_movie_is_owned(payload)
        try:
            variants = self.ports._ai_control_source_search(payload, {'trusted_indexers': trusted_ids})
        except Exception as error:
            variants = []
            payload['source_error'] = str(error)
        variants_by_quality = self.ports._source_review_variants_by_quality(variants, trusted_ids)
        variant = variants_by_quality.get(quality)
        target = {'key': f"movie:tmdb:{payload['tmdb_id']}" if payload.get('tmdb_id') else f"movie:imdb:{payload.get('imdb_id')}", 'media_type': 'movie', 'released': True}
        candidates = [{**row, 'info_hash': row.get('info_hash') or magnet_hash(row.get('magnet_url')),
                       'identity_verified': True, 'transport_verified': bool(row.get('magnet_url') or row.get('download_url')),
                       'trusted_indexer': str(row.get('indexer_id') or row.get('indexer') or '') in {str(value) for value in trusted_ids},
                       'availability_verified': False} for row in variants]
        profile = ((self.ports.acquisition_profile(profile_id) if profile_id else self.ports.acquisition_profile())
                   if hasattr(self.ports, 'acquisition_profile') else default_profile(compatibility=True, quality=quality))
        payload['acquisition_review'] = shadow_compare(candidates, target, profile, (variant or {}).get('info_hash') or magnet_hash((variant or {}).get('magnet_url')) or None)
        return {**payload, 'quality': quality, 'upgrade': upgrade, 'selected': bool(variant), 'status': 'ready' if variant else 'blocked', 'variant': variant, 'variants_by_quality': variants_by_quality, 'reason': '' if variant else payload.get('source_error') or f'No trusted {quality} source found'}
