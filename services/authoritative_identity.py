"""Authoritative, provider-independent movie identity projection."""


IDENTITY_STATES = {"accepted", "review", "conflict", "unmatched"}
ENRICHMENT_STATES = {"complete", "incomplete", "stale", "unavailable"}


def _text(value):
    return str(value or "").strip()


def _first(*values):
    return next((_text(value) for value in values if _text(value)), "")


def _provider_has_details(metadata):
    metadata = metadata or {}
    return bool(
        metadata
        and not metadata.get("error")
        and any(metadata.get(key) for key in ("title", "overview", "poster_path", "poster_url", "cast"))
    )


def resolve_authoritative_identity(file_record, provider_metadata=None, fallback=None):
    """Resolve persisted identity separately from optional provider enrichment."""
    record = dict(file_record or {})
    provider = dict(provider_metadata or {})
    fallback = dict(fallback or {})
    identity_state = _first(
        record.get("identity_status"),
        record.get("metadata_status"),
    ).lower()
    identity_state = {
        "needs_review": "review",
        "candidate": "review",
        "pending": "unmatched",
    }.get(identity_state, identity_state)
    if identity_state not in IDENTITY_STATES:
        identity_state = "unmatched"

    accepted = identity_state == "accepted"
    title = _first(
        record.get("identity_title"),
        record.get("accepted_title"),
        provider.get("title") if accepted else "",
        record.get("title") if accepted else "",
        record.get("plex_title") if accepted else "",
        fallback.get("title") if accepted else "",
    )
    year = _first(
        record.get("identity_year"),
        record.get("accepted_year"),
        provider.get("year") if accepted else "",
        record.get("year") if accepted else "",
        record.get("plex_year") if accepted else "",
        fallback.get("year") if accepted else "",
    )

    requested_enrichment = _first(record.get("enrichment_status")).lower()
    if requested_enrichment in {"stale", "unavailable"}:
        enrichment_state = requested_enrichment
    elif _provider_has_details(provider):
        enrichment_state = "complete"
    else:
        enrichment_state = "incomplete"

    return {
        "identity_state": identity_state,
        "enrichment_state": enrichment_state,
        "accepted": accepted,
        "title": title,
        "year": year,
        "tmdb_id": _first(record.get("tmdb_id"), provider.get("tmdb_id") if accepted else ""),
        "imdb_id": _first(record.get("imdb_id"), provider.get("imdb_id") if accepted else ""),
        "plex_guid": _first(record.get("plex_guid"), provider.get("plex_guid") if accepted else ""),
        "plex_rating_key": _first(record.get("plex_rating_key"), provider.get("rating_key") if accepted else ""),
        "identity_source": _first(record.get("identity_source"), record.get("metadata_source")),
        "identity_revision": int(record.get("identity_revision", 0) or 0),
        "manual_lock": bool(record.get("manual_lock") or record.get("manual_metadata_lock")),
    }


def accepted_identity_patch(record, identity, source="", manual_lock=False):
    """Return the fields written together whenever Cinema Paradiso accepts an identity."""
    record = dict(record or {})
    identity = dict(identity or {})
    revision = int(record.get("identity_revision", 0) or 0) + 1
    return {
        "identity_status": "accepted",
        "metadata_status": "accepted",
        "identity_title": _first(identity.get("title"), record.get("identity_title")),
        "identity_year": _first(identity.get("year"), record.get("identity_year")),
        "accepted_title": _first(identity.get("title"), record.get("accepted_title")),
        "accepted_year": _first(identity.get("year"), record.get("accepted_year")),
        "tmdb_id": _first(identity.get("tmdb_id"), record.get("tmdb_id")),
        "imdb_id": _first(identity.get("imdb_id"), record.get("imdb_id")),
        "plex_guid": _first(identity.get("plex_guid"), identity.get("guid"), record.get("plex_guid")),
        "plex_rating_key": _first(
            identity.get("plex_rating_key"),
            identity.get("rating_key"),
            record.get("plex_rating_key"),
        ),
        "identity_source": _first(source, identity.get("source"), record.get("identity_source")),
        "manual_lock": bool(manual_lock or record.get("manual_lock")),
        "identity_revision": revision,
    }
