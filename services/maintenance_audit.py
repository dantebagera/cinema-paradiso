"""Catalog-backed maintenance projections for the local movie archive."""

import os
import time

from services.identity_verification import verify_catalog_identity
from services.movie_identity import group_identity_records


RESOLUTION_RANK = {"4K": 4, "1080p": 3, "720p": 2, "480p": 1, "Unknown": 0}
RIP_RANK = {
    "BD Remux": 9, "Remux": 8, "Blu-ray": 7, "BDRip": 6,
    "WEB-DL": 5, "WEBRip": 4, "HDRip": 3, "HDTV": 2,
    "DVDRip": 1, "DVDScr": 0, "CAMRip": -1, "HDCAM": -2, "Unknown": -3,
}
_BULK_PLEX_GROUP_LIMIT = 4


def format_size(size):
    size = int(size or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


def _text(value):
    return str(value or "").strip()


def _identity_state(candidate, record):
    state = _text(candidate.get("identity_status") or record.get("identity_status") or candidate.get("metadata_status") or record.get("metadata_status")).lower()
    return {"needs_review": "review", "candidate": "review"}.get(state, state or "unmatched")


def _metadata_hint(item):
    if item["metadata_status"] == "conflict":
        return "Accepted identity has contradictory public IDs. Review the exact movie before changing it."
    if item["metadata_status"] == "unverified":
        if item.get("enrichment_needed"):
            return "Filename and Plex agree on another title. Check TMDB aliases before deciding whether the accepted identity is wrong."
        return "Filename and Plex still disagree with the accepted identity after alias verification."
    if item["metadata_status"] == "review":
        return "A possible identity exists but still needs human approval."
    if item["fixable_path"]:
        return "The file is nested too deeply for a conventional movie-library layout."
    if not item["suggested_title"]:
        return "The filename cannot provide a usable movie identity."
    return "No accepted movie identity is stored for this file."


def _item_from_candidate(candidate):
    record = dict(candidate.get("raw_json") or {})
    plex = dict(candidate.get("plex_json") or {})
    manual = dict(candidate.get("manual_json") or {})
    tmdb = dict(candidate.get("tmdb_json") or {})
    path = _text(candidate.get("path") or record.get("path"))
    filename = _text(record.get("filename")) or os.path.basename(path)
    title = _text(
        candidate.get("identity_title")
        or record.get("identity_title")
        or record.get("accepted_title")
        or manual.get("title")
        or plex.get("plex_title")
        or tmdb.get("title")
        or record.get("parsed_title")
    )
    year = _text(
        candidate.get("identity_year")
        or record.get("identity_year")
        or record.get("accepted_year")
        or manual.get("year")
        or plex.get("plex_year")
        or tmdb.get("year")
        or record.get("parsed_year")
    )
    library_root = _text(candidate.get("library_root") or record.get("library_root"))
    try:
        depth = len(os.path.relpath(path, library_root).split(os.sep)) - 1 if library_root else 0
    except ValueError:
        depth = 0
    verification = verify_catalog_identity(candidate)
    identity_state = _identity_state(candidate, record)
    identity_conflict = verification["classification"] == "hard_conflict"
    metadata_accepted = bool(candidate.get("metadata_accepted") or record.get("metadata_accepted") or identity_state == "accepted")
    metadata_status = (
        "conflict"
        if identity_conflict
        else "unverified"
        if metadata_accepted and verification["classification"] == "unverified"
        else "accepted"
        if metadata_accepted
        else identity_state
    )
    observations = verification.get("observations") or {}
    observed = observations.get("parsed") or observations.get("plex") or {}
    item = {
        "path": path,
        "filename": filename,
        "library_root": library_root,
        "title": title,
        "year": year,
        "suggested_title": _text(observed.get("title")) or title,
        "suggested_year": _text(observed.get("year")) or year,
        "accepted_title": title,
        "accepted_year": year,
        "parsed_title": _text(record.get("parsed_title")),
        "parsed_year": _text(record.get("parsed_year")),
        "resolution": _text(candidate.get("resolution") or record.get("resolution")) or "Unknown",
        "rip_source": _text(candidate.get("rip_source") or record.get("rip_source")) or "Unknown",
        "size": int(candidate.get("size") or record.get("size") or 0),
        "tmdb_id": _text(candidate.get("tmdb_id") or record.get("tmdb_id") or manual.get("tmdb_id") or plex.get("tmdb_id")),
        "imdb_id": _text(candidate.get("imdb_id") or record.get("imdb_id") or manual.get("imdb_id") or plex.get("imdb_id")),
        "plex_guid": _text(candidate.get("plex_guid") or record.get("plex_guid") or manual.get("plex_guid") or plex.get("plex_guid")),
        "plex_title": _text(plex.get("plex_title")),
        "plex_year": _text(plex.get("plex_year")),
        "plex_matched": bool(plex),
        "rating_key": _text(candidate.get("plex_rating_key") or record.get("plex_rating_key") or plex.get("rating_key")),
        "metadata_status": metadata_status,
        "metadata_accepted": metadata_accepted,
        "identity_status": identity_state,
        "identity_conflict": identity_conflict,
        "identity_verified": verification["classification"] == "verified",
        "verification_status": verification["classification"],
        "verification_reasons": verification.get("reasons", []),
        "metadata_drift": bool(verification.get("metadata_drift")),
        "drift_reasons": verification.get("drift_reasons", []),
        "observations": observations,
        "enrichment_needed": bool(verification.get("enrichment_needed")),
        "depth": depth,
        "fixable_path": depth > 1,
    }
    item["size_human"] = format_size(item["size"])
    item["file_size"] = item["size_human"]
    item["resolution_rank"] = RESOLUTION_RANK.get(item["resolution"], 0)
    item["rip_rank"] = RIP_RANK.get(item["rip_source"], -3)
    item["metadata_hint"] = _metadata_hint(item)
    return item


def _split_bulk_plex_groups(groups):
    split = []
    for group in groups:
        if len(group) <= _BULK_PLEX_GROUP_LIMIT or not any(item.get("plex_title") for item in group):
            split.append(group)
            continue
        buckets = {}
        for item in group:
            title = _text(item.get("parsed_title"))
            year = _text(item.get("parsed_year"))
            if title:
                buckets.setdefault((title.lower(), year), []).append(item)
        split.extend(buckets.values())
    return split


def _recommendation(best, candidate):
    if candidate["resolution_rank"] < best["resolution_rank"]:
        return "recommended", f"Lower resolution than {best['filename']}"
    if candidate["resolution_rank"] == best["resolution_rank"] and candidate["rip_rank"] < best["rip_rank"]:
        largest = max(best["size"], candidate["size"])
        difference = abs(best["size"] - candidate["size"]) / largest if largest else 0
        if difference < 0.05:
            return "recommended", f"Inferior source with comparable file size to {best['filename']}"
    return "review", "Keep or remove only after comparing the editions."


def _duplicate_groups(items):
    groups = []
    grouped_items = _split_bulk_plex_groups(group_identity_records([item for item in items if item["identity_verified"]]))
    for files in grouped_items:
        if len(files) < 2:
            continue
        ranked = sorted(files, key=lambda item: (item["resolution_rank"], item["rip_rank"], item["size"]), reverse=True)
        best = ranked[0]
        output_files = []
        for index, file in enumerate(ranked):
            row = dict(file)
            if index == 0:
                row.update({"role": "keep", "recommendation": "keep", "reason": "Best current copy by configured baseline."})
            else:
                recommendation, reason = _recommendation(best, row)
                row.update({"role": "candidate", "recommendation": recommendation, "reason": reason})
            output_files.append(row)
        title = best["title"] or best["plex_title"] or best["parsed_title"] or best["filename"]
        year = best["year"] or best["plex_year"] or best["parsed_year"]
        reclaimable = sum(file["size"] for file in ranked[1:])
        groups.append({
            "key": "|".join(file["path"] for file in ranked),
            "title": f"{title}{f' ({year})' if year else ''}",
            "files": output_files,
            "reclaimable_bytes": reclaimable,
            "reclaimable_human": format_size(reclaimable),
            "recommended_count": sum(file["recommendation"] == "recommended" for file in output_files[1:]),
        })
    return sorted(groups, key=lambda group: group["title"].lower())


def build_maintenance_audit(candidates, generation=0):
    """Build a maintenance view from the persisted catalog without walking disks."""
    items = [_item_from_candidate(candidate) for candidate in candidates if _text(candidate.get("path") or (candidate.get("raw_json") or {}).get("path"))]
    duplicates = _duplicate_groups(items)
    grouped_by_path = {
        item["path"]: group
        for group in duplicates
        for item in group["files"]
    }
    upgrades = [
        item for item in items
        if item["metadata_accepted"] and item["identity_verified"]
        and item["resolution_rank"] < RESOLUTION_RANK["1080p"]
        and not any(
            other["resolution_rank"] >= RESOLUTION_RANK["1080p"]
            for other in (grouped_by_path.get(item["path"], {}).get("files") or [])
        )
    ]
    unmatched = [
        item for item in items
        if not item["metadata_accepted"] and item["metadata_status"] != "pending"
    ]
    verification = [
        item for item in items
        if item["metadata_accepted"] and item["verification_status"] in {"unverified", "hard_conflict"}
    ]
    audit_pending = sum(
        1 for item in items
        if item["metadata_accepted"] and item["verification_status"] == "audit_pending"
    )
    pending = sum(1 for item in items if not item["metadata_accepted"] and item["metadata_status"] == "pending")
    extra_copies = sum(max(0, len(group["files"]) - 1) for group in duplicates)
    reclaimable = sum(group["reclaimable_bytes"] for group in duplicates)
    recommended = sum(group["recommended_count"] for group in duplicates)
    return {
        "source": "catalog",
        "generation": int(generation or 0),
        "generated_at": time.time(),
        "summary": {
            "duplicate_groups": len(duplicates),
            "extra_copies": extra_copies,
            "reclaimable_bytes": reclaimable,
            "reclaimable_human": format_size(reclaimable),
            "recommended_removals": recommended,
            "upgrade_candidates": len(upgrades),
            "identity_issues": len(unmatched) + len(verification),
            "unmatched_files": len(unmatched),
            "verification_gaps": len(verification),
            "automated_identity_checks": audit_pending,
            "hard_conflicts": sum(item["identity_conflict"] for item in verification),
            "metadata_drift": sum(item["metadata_drift"] for item in items),
            "metadata_pending": pending,
        },
        "storage": {"groups": duplicates},
        "upgrades": {"items": sorted(upgrades, key=lambda item: (item["title"].lower(), item["path"].lower()))},
        "identity": {
            "items": sorted(unmatched, key=lambda item: item["filename"].lower()),
            "verification": sorted(
                verification,
                key=lambda item: (item["metadata_status"] != "conflict", item["filename"].lower()),
            ),
        },
    }
