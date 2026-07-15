"""Authoritative, read-only verification of persisted movie identities."""

from difflib import SequenceMatcher
import os
import re
import time

from services.identity_decision import (
    DECISION_ORIGIN_LEGACY_IDENTITY_AUDIT,
    DECISION_ORIGIN_USER_MANUAL,
    IDENTITY_AUDIT_RULE_VERSION,
    compare_identity_content,
    infer_decision_origin,
)
from services.movie_identity import normalize_movie_title


IDENTITY_VERIFICATION_SCHEMA_VERSION = 1
_PUBLIC_ID_FIELDS = ("tmdb_id", "imdb_id")
_ROMAN_NUMERALS = {
    "i": "1", "ii": "2", "iii": "3", "iv": "4", "v": "5",
    "vi": "6", "vii": "7", "viii": "8", "ix": "9", "x": "10",
}


def _text(value):
    return str(value or "").strip()


def _year(value):
    match = re.search(r"\b(18|19|20|21)\d{2}\b", _text(value))
    return match.group(0) if match else ""


def _normalized_id(field, value):
    value = _text(value).lower()
    if not value:
        return ""
    prefixes = {
        "tmdb_id": ("tmdb://", "tmdb:"),
        "imdb_id": ("imdb://", "imdb:"),
    }
    for prefix in prefixes.get(field, ()):
        if value.startswith(prefix):
            return value[len(prefix):]
    return value


def _public_ids(value):
    value = dict(value or {})
    result = {
        field: _normalized_id(field, value.get(field))
        for field in _PUBLIC_ID_FIELDS
    }
    raw_guids = value.get("guids") or value.get("Guid") or []
    if isinstance(raw_guids, dict):
        raw_guids = [raw_guids]
    for item in raw_guids:
        raw = item.get("id") if isinstance(item, dict) else item
        raw = _text(raw).lower()
        for field, prefix in (("tmdb_id", "tmdb://"), ("imdb_id", "imdb://")):
            if raw.startswith(prefix) and not result[field]:
                result[field] = _normalized_id(field, raw)
    return result


def _first(*values):
    return next((_text(value) for value in values if _text(value)), "")


def _canonical_record(candidate):
    record = dict(candidate.get("raw_json") or {})
    return {
        **record,
        **{
            key: value
            for key, value in candidate.items()
            if key not in {"raw_json", "plex_json", "manual_json", "tmdb_json"}
            and value not in (None, "")
        },
    }


def _provider_title_year(name, claim):
    if name == "plex":
        return _text(claim.get("plex_title") or claim.get("title")), _year(
            claim.get("plex_year") or claim.get("year")
        )
    return _text(claim.get("title") or claim.get("name")), _year(
        claim.get("year") or claim.get("release_date")
    )


def _comparison_title(value):
    value = _text(value).replace("&", " and ").replace("_", " ")
    normalized = normalize_movie_title(value)
    return " ".join(_ROMAN_NUMERALS.get(token, token) for token in normalized.split())


def _titles_related(left, right):
    left = _comparison_title(left)
    right = _comparison_title(right)
    if not left or not right:
        return False
    if left == right or left.startswith(f"{right} ") or right.startswith(f"{left} "):
        return True
    return SequenceMatcher(None, left, right).ratio() >= 0.9


def _title_values(metadata):
    metadata = dict(metadata or {})
    values = [metadata.get("title"), metadata.get("original_title")]
    values.extend(metadata.get("alternative_titles") or [])
    values.extend(metadata.get("aliases") or [])
    result = []
    for value in values:
        if isinstance(value, dict):
            value = value.get("title") or value.get("name")
        value = _text(value)
        if value and value not in result:
            result.append(value)
    return result


def _public_id_conflicts(left, right):
    left_ids = _public_ids(left)
    right_ids = _public_ids(right)
    return [
        field
        for field in _PUBLIC_ID_FIELDS
        if left_ids[field] and right_ids[field] and left_ids[field] != right_ids[field]
    ]


def _public_id_matches(left, right):
    left_ids = _public_ids(left)
    right_ids = _public_ids(right)
    return [
        field
        for field in _PUBLIC_ID_FIELDS
        if left_ids[field] and left_ids[field] == right_ids[field]
    ]


def _tmdb_alias_verifies_consensus(tmdb, observed_title, observed_year):
    if not tmdb or not observed_title:
        return False
    tmdb_year = _year(tmdb.get("year") or tmdb.get("release_date"))
    observed_year = _year(observed_year)
    if not tmdb_year or not observed_year or abs(int(tmdb_year) - int(observed_year)) > 1:
        return False
    observed = _comparison_title(observed_title)
    return any(_comparison_title(alias) == observed for alias in _title_values(tmdb))


def verify_catalog_identity(candidate):
    """Verify one persisted catalog identity without changing it."""
    candidate = dict(candidate or {})
    record = _canonical_record(candidate)
    path = _first(candidate.get("path"), record.get("path"))
    state = _first(
        candidate.get("identity_status"),
        record.get("identity_status"),
        candidate.get("metadata_status"),
        record.get("metadata_status"),
    ).lower()
    state = {"needs_review": "review", "candidate": "review"}.get(state, state)
    accepted = bool(
        candidate.get("metadata_accepted")
        or record.get("metadata_accepted")
        or state == "accepted"
    )
    title = _first(
        candidate.get("identity_title"),
        record.get("identity_title"),
        record.get("accepted_title"),
    )
    year = _year(_first(
        candidate.get("identity_year"),
        record.get("identity_year"),
        record.get("accepted_year"),
    ))
    canonical = {
        "tmdb_id": _first(candidate.get("tmdb_id"), record.get("tmdb_id")),
        "imdb_id": _first(candidate.get("imdb_id"), record.get("imdb_id")),
    }
    manual = dict(candidate.get("manual_json") or {})
    tmdb = dict(candidate.get("tmdb_json") or {})
    plex = dict(candidate.get("plex_json") or {})
    fingerprint = dict(candidate.get("audit_fingerprint_json") or {})
    claims = [("manual", manual), ("tmdb", tmdb), ("plex", plex)]
    parsed_title = _text(record.get("parsed_title"))
    parsed_year = _year(record.get("parsed_year"))
    plex_title, plex_year = _provider_title_year("plex", plex)
    tmdb_title, tmdb_year = _provider_title_year("tmdb", tmdb)
    provider_content = compare_identity_content(tmdb, plex) if tmdb and plex else {
        "support": 0,
        "conflict": False,
        "reasons": [],
        "contradictions": [],
    }

    hard_conflicts = []
    drift = []
    evidence = []
    for provider, claim in claims:
        if not claim:
            continue
        for field in _public_id_conflicts(canonical, claim):
            hard_conflicts.append(f"{provider}_{field}_conflict")
        # The accepted identity, its TMDB cache, and an audit-generated manual
        # row can all originate from the same decision. Only Plex is an
        # independent persisted provider claim here.
        if provider == "plex":
            for field in _public_id_matches(canonical, claim):
                evidence.append(f"{provider}_{field}_match")
        provider_title, provider_year = _provider_title_year(provider, claim)
        if title and provider_title and normalize_movie_title(title) != normalize_movie_title(provider_title):
            drift.append(f"{provider}_title_difference")
        if year and provider_year and year != provider_year:
            drift.append(f"{provider}_year_difference")
    if provider_content["conflict"]:
        drift.append("provider_content_conflict")

    canonical_ids = _public_ids(canonical)
    decision_origin = infer_decision_origin(record, manual, fingerprint)
    manually_verified = decision_origin == DECISION_ORIGIN_USER_MANUAL
    if manually_verified:
        evidence.append("explicit_user_acceptance")
    fingerprint_current = bool(
        int(fingerprint.get("rule_version", 0) or 0) >= IDENTITY_AUDIT_RULE_VERSION
        and (
            not canonical_ids["tmdb_id"]
            or _normalized_id("tmdb_id", fingerprint.get("provider_id")) == canonical_ids["tmdb_id"]
        )
    )
    if fingerprint_current:
        evidence.append("current_provider_audit")

    local_consensus = bool(
        parsed_title
        and plex_title
        and _comparison_title(parsed_title) == _comparison_title(plex_title)
    )
    independent_disagreement = bool(
        local_consensus
        and title
        and not _titles_related(title, parsed_title)
    )
    if local_consensus and not independent_disagreement:
        evidence.append("parsed_plex_title_consensus")
    alias_verified = bool(
        independent_disagreement
        and _tmdb_alias_verifies_consensus(tmdb, parsed_title, parsed_year or plex_year)
    )
    if alias_verified:
        evidence.append("tmdb_alias_and_year_match_local_consensus")
    if (
        title
        and parsed_title
        and _titles_related(title, parsed_title)
        and year
        and parsed_year
        and abs(int(year) - int(parsed_year)) > 2
    ):
        drift.append("filename_year_difference")

    aliases_checked = bool(tmdb.get("alternative_titles_checked_at"))
    if not accepted:
        classification = "unmatched"
        reasons = [f"identity_state_{state or 'unmatched'}"]
    elif hard_conflicts:
        classification = "hard_conflict"
        reasons = hard_conflicts
    elif provider_content["conflict"]:
        classification = "unverified"
        reasons = [
            "independent_provider_content_conflict",
            *provider_content["contradictions"],
        ]
    elif independent_disagreement and not alias_verified:
        classification = "unverified"
        reasons = [
            "independent_title_consensus_unresolved"
            if aliases_checked
            else "identity_alias_evidence_missing"
        ]
    elif decision_origin == DECISION_ORIGIN_LEGACY_IDENTITY_AUDIT and not fingerprint_current:
        classification = "audit_pending"
        reasons = ["legacy_bulk_decision_requires_provider_audit"]
    elif evidence:
        classification = "verified"
        reasons = list(dict.fromkeys(evidence))
    elif canonical_ids["tmdb_id"] or canonical_ids["imdb_id"]:
        classification = "audit_pending"
        reasons = ["accepted_identity_requires_provider_audit"]
    else:
        classification = "unverified"
        reasons = ["accepted_without_stable_or_manual_evidence"]

    return {
        "path": path,
        "filename": _first(record.get("filename"), os.path.basename(path)),
        "title": title,
        "year": year,
        "tmdb_id": canonical_ids["tmdb_id"],
        "imdb_id": canonical_ids["imdb_id"],
        "accepted": accepted,
        "decision_origin": decision_origin,
        "classification": classification,
        "requires_review": classification == "hard_conflict",
        "enrichment_needed": bool(
            classification == "unverified"
            and canonical_ids["tmdb_id"]
            and not aliases_checked
        ),
        "metadata_drift": bool(drift),
        "drift_reasons": list(dict.fromkeys(drift)),
        "reasons": list(dict.fromkeys(reasons)),
        "observations": {
            "parsed": {"title": parsed_title, "year": parsed_year},
            "plex": {"title": plex_title, "year": plex_year},
            "tmdb": {"title": tmdb_title, "year": tmdb_year},
        },
    }


def build_identity_verification_audit(candidates, generation=0, sample_limit=50):
    """Build a bounded verification report from persisted catalog candidates."""
    rows = [
        verify_catalog_identity(candidate)
        for candidate in candidates or []
        if _first(candidate.get("path"), (candidate.get("raw_json") or {}).get("path"))
    ]
    groups = {
        "verified": [row for row in rows if row["classification"] == "verified"],
        "unverified": [row for row in rows if row["classification"] == "unverified"],
        "audit_pending": [row for row in rows if row["classification"] == "audit_pending"],
        "hard_conflicts": [row for row in rows if row["classification"] == "hard_conflict"],
        "unmatched": [row for row in rows if row["classification"] == "unmatched"],
        "metadata_drift": [row for row in rows if row["metadata_drift"]],
    }
    limit = max(0, int(sample_limit or 0))

    def bounded(items):
        return {
            "count": len(items),
            "items": items[:limit],
            "truncated": len(items) > limit,
        }

    return {
        "schema_version": IDENTITY_VERIFICATION_SCHEMA_VERSION,
        "mode": "read_only_verification",
        "mutates_metadata": False,
        "source": "catalog",
        "generation": int(generation or 0),
        "generated_at": time.time(),
        "summary": {
            "total_files": len(rows),
            "accepted": sum(1 for row in rows if row["accepted"]),
            "verified": len(groups["verified"]),
            "unverified": len(groups["unverified"]),
            "audit_pending": len(groups["audit_pending"]),
            "hard_conflicts": len(groups["hard_conflicts"]),
            "unmatched": len(groups["unmatched"]),
            "metadata_drift": len(groups["metadata_drift"]),
            "review_required": len(groups["hard_conflicts"]),
            "enrichment_needed": sum(row["enrichment_needed"] for row in groups["unverified"]),
        },
        "policy": {
            "hard_conflict": "Contradictory TMDB or IMDb IDs on an accepted identity.",
            "metadata_drift": "Provider title or year differs without contradictory public IDs.",
            "unverified": "Accepted identity lacks durable evidence or unresolved filename and Plex consensus disagrees.",
            "audit_pending": "Legacy bulk decisions are checked against the provider before entering manual review.",
            "review_required": "Only hard public-ID conflicts are conclusive identity conflicts.",
        },
        "review": bounded(groups["hard_conflicts"]),
        "unmatched": bounded(groups["unmatched"]),
        "samples": {
            "unverified": bounded(groups["unverified"]),
            "audit_pending": bounded(groups["audit_pending"]),
            "metadata_drift": bounded(groups["metadata_drift"]),
        },
    }
