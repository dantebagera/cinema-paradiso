"""Pure shared movie/TV policy. Inputs distinguish claims from measurements."""
import hashlib
import json
import re

from services.quality_catalog import SOURCES, RESOLUTIONS, release_claims
from services.acquisition_profiles import validate_profile


def measured_resolution_ranks(owned):
    return [RESOLUTIONS.index('2160p' if item.get('quality_class') == '4K' else item.get('quality_class'))
            for item in owned if ('2160p' if item.get('quality_class') == '4K' else item.get('quality_class')) in RESOLUTIONS[:-1]]


def below_profile_cutoff(owned, profile):
    ranks = measured_resolution_ranks(owned)
    return bool(ranks and max(ranks) < RESOLUTIONS.index(profile['cutoff']))


def evaluate_release(candidate, target, profile, *, manual=False, blocked=False, owned=(), queued=False, available_bytes=None, now=0):
    profile = validate_profile(profile)
    claim = release_claims(candidate.get('title'))
    reasons, warnings = [], []
    def reject(code, message):
        reasons.append({'code': code, 'message': message})
    key = str(target.get('key') or '')
    if not re.fullmatch(r'(?:movie:(?:tmdb|imdb):[a-z0-9]+|(?:series|season|episode):tmdb:tv:\d+(?::\d+){0,2}|selection:tmdb:tv:\d+:[a-f0-9]{16})', key) or candidate.get('identity_verified') is not True:
        reject('identity_unverified', 'Stable provider identity has not been verified for this target')
    info_hash = str(candidate.get('info_hash') or '').lower()
    if not re.fullmatch(r'[a-f0-9]{40}|[a-f0-9]{64}', info_hash):
        reject('hash_invalid', 'A valid torrent identity is required')
    if candidate.get('transport_verified') is not True:
        reject('transport_untrusted', 'The candidate transport is not verified')
    if not target.get('released'):
        reject('unreleased', 'Target has not been released or its release date is unknown')
    if blocked:
        reject('blocklisted', 'A previous failure blocks this release')
    if queued:
        reject('already_queued', 'This target already has an outstanding acquisition')
    coverage = set(candidate.get('episode_ids') or [])
    wanted = set(target.get('episode_ids') or [])
    if target.get('media_type') == 'tv' and (not wanted or not wanted.issubset(coverage)):
        reject('coverage_missing', 'Release does not cover the requested episodes')
    state = profile['states'][f"{claim['source']}:{claim['resolution']}"]
    if state == 'blocked':
        reject('quality_blocked', f"{SOURCES[claim['source']]['label']} / {claim['resolution']} is blocked by the profile")
    if state == 'manual_only' and not manual:
        reject('manual_only', 'This quality requires a deliberate manual selection')
    confidence = 'plausible'
    manifest_claims = [release_claims(name) for name in candidate.get('manifest_names', [])]
    if any(fact['source'] != 'unknown' and claim['source'] != 'unknown' and fact['source'] != claim['source'] for fact in manifest_claims):
        reject('source_contradiction', 'Listing and torrent file source labels disagree')
        confidence = 'contradictory'
    if any(fact['resolution'] != 'unknown' and claim['resolution'] != 'unknown' and fact['resolution'] != claim['resolution'] for fact in manifest_claims):
        reject('resolution_contradiction', 'Listing and torrent file resolutions disagree')
        confidence = 'contradictory'
    if confidence != 'contradictory':
        if candidate.get('trusted_indexer') and candidate.get('identity_verified') and candidate.get('availability_verified'):
            confidence = 'verified_evidence'
        elif not manual:
            reject('source_unverified', 'Automatic selection needs trusted identity and availability evidence')
        else:
            warnings.append({'code': 'source_unverified', 'message': 'Source is a release claim; dimensions cannot prove provenance'})
    size = max(0, int(candidate.get('size_bytes') or 0))
    if size < profile['minimum_bytes'] or (profile['maximum_bytes'] and size > profile['maximum_bytes']):
        reject('size_policy', 'Release size is outside the profile bounds')
    if int(candidate.get('seeders') or 0) < profile['minimum_seeders']:
        reject('seeders_low', 'Not enough seeders for this profile')
    if available_bytes is not None and size > available_bytes:
        reject('disk_space', 'Insufficient unreserved disk space')
    if not manual and now and now - float(candidate.get('published_at') or now) < max(profile['delay_seconds'], profile['minimum_age_seconds']):
        reject('delay_window', 'Waiting for the configured release delay')
    format_scores = []
    for rule in profile['formats']:
        actual = str(claim.get(rule['field'], candidate.get(rule['field'], ''))).lower()
        expected = str(rule['value']).lower()
        if (actual == expected if rule['op'] == 'equals' else expected in actual):
            format_scores.append({'name': rule.get('name') or rule['field'], 'score': rule['score']})
    score = sum(rule['score'] for rule in format_scores)
    if score < profile['minimum_score']:
        reject('format_score', 'Custom format score is below the profile minimum')
    rank = RESOLUTIONS.index(claim['resolution']) if claim['resolution'] != 'unknown' else -1
    owned_ranks = measured_resolution_ranks(owned)
    if target.get('media_type') == 'tv' and target.get('upgrade'):
        if not owned_ranks or rank < 0 or rank <= max(owned_ranks) or not candidate.get('trusted_indexer'):
            reject('not_strict_upgrade', 'Verified local quality and a trusted strictly better source are required')
    if owned_ranks and not manual:
        if target.get('media_type') == 'tv' and target.get('upgrade'):
            pass
        elif not profile['automatic_upgrades']:
            reject('upgrades_disabled', 'Automatic upgrades are disabled')
        elif max(owned_ranks) >= RESOLUTIONS.index(profile['cutoff']) or rank <= max(owned_ranks):
            reject('cutoff_satisfied', 'Existing measured files already satisfy this upgrade')
    sort_key = [bool(reasons), -(state == 'preferred'), -rank, -score, -claim['revision'], -int(candidate.get('indexer_priority') or 0), -int(candidate.get('seeders') or 0), size, info_hash, str(candidate.get('title') or '')]
    fingerprint = hashlib.sha256(json.dumps({'candidate': candidate, 'target': target, 'profile': profile, 'manual': manual, 'owned': owned, 'blocked': blocked, 'reasons': reasons}, sort_keys=True).encode()).hexdigest()
    return {'accepted': not reasons, 'manual': manual, 'target': key, 'candidate': candidate, 'claim': claim, 'source_confidence': confidence,
            'measured_facts': candidate.get('measured_facts') or {}, 'eligibility': state, 'reasons': reasons, 'warnings': warnings,
            'quality_score': rank, 'format_score': score, 'format_scores': format_scores, 'sort_key': sort_key,
            'covered_episodes': sorted(coverage), 'missing_episodes': sorted(wanted-coverage), 'estimated_bytes': size,
            'profile_id': profile['id'], 'profile_version': profile.get('version', 1), 'parser_version': 1, 'decision_token': fingerprint}


def rank_releases(decisions):
    return sorted(decisions, key=lambda decision: decision['sort_key'])


def shadow_compare(candidates, target, profile, legacy_selected=None):
    decisions = rank_releases([evaluate_release(candidate, target, profile, manual=True) for candidate in candidates])
    selected = next((row['candidate']['info_hash'] for row in decisions if row['accepted']), None)
    return {'mode': 'shadow', 'legacy_authoritative': True, 'legacy_selected': legacy_selected, 'proposed_selected': selected,
            'selection_matches': selected == legacy_selected, 'decisions': decisions}
