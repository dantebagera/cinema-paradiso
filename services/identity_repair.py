"""One-time normalization of legacy JSON records into authoritative identities."""


def _text(value):
    return str(value or "").strip()


def _first(*values):
    return next((_text(value) for value in values if _text(value)), "")


def build_identity_repair(files, manual_matches, tmdb_movies, plex_files):
    repaired = {}
    report = {
        "preserved": 0,
        "backfilled": 0,
        "incomplete": 0,
        "unmatched": 0,
        "review": 0,
        "conflicting": 0,
    }
    for key, source_record in (files or {}).items():
        record = dict(source_record or {})
        manual = dict((manual_matches or {}).get(key, {}) or {})
        plex = dict((plex_files or {}).get(key, {}) or {})
        tmdb_id = _first(record.get("tmdb_id"), manual.get("tmdb_id"), plex.get("tmdb_id"))
        tmdb = dict((tmdb_movies or {}).get(tmdb_id, {}) or {}) if tmdb_id else {}
        legacy_status = _text(record.get("identity_status") or record.get("metadata_status")).lower()
        accepted = bool(
            record.get("metadata_accepted")
            or manual.get("accepted")
            or legacy_status == "accepted"
        )
        if accepted:
            title = _first(
                record.get("identity_title"),
                record.get("accepted_title"),
                manual.get("title"),
                tmdb.get("title"),
                plex.get("plex_title"),
                record.get("title"),
                record.get("plex_title"),
                record.get("parsed_title"),
            )
            year = _first(
                record.get("identity_year"),
                record.get("accepted_year"),
                manual.get("year"),
                tmdb.get("year"),
                plex.get("plex_year"),
                record.get("year"),
                record.get("plex_year"),
                record.get("parsed_year"),
            )
            was_backfilled = not record.get("identity_title") or not record.get("identity_year")
            display_provider = _text(record.get("display_provider"))
            provider_complete = (
                bool(tmdb and tmdb.get("title")) if display_provider == "tmdb"
                else bool(plex and plex.get("plex_title")) if display_provider == "plex"
                else bool(tmdb.get("title") or plex.get("plex_title"))
            )
            repaired[key] = {
                **record,
                "identity_status": "accepted",
                "metadata_status": "accepted",
                "metadata_accepted": True,
                "identity_title": title,
                "identity_year": year,
                "accepted_title": title,
                "accepted_year": year,
                "tmdb_id": tmdb_id,
                "imdb_id": _first(
                    record.get("imdb_id"),
                    manual.get("imdb_id"),
                    tmdb.get("imdb_id"),
                    plex.get("imdb_id"),
                ),
                "plex_guid": _first(
                    record.get("plex_guid"),
                    manual.get("plex_guid"),
                    plex.get("plex_guid"),
                    plex.get("guid"),
                ),
                "plex_rating_key": _first(
                    record.get("plex_rating_key"),
                    record.get("rating_key"),
                    manual.get("rating_key"),
                    plex.get("rating_key"),
                ),
                "identity_source": _first(
                    record.get("identity_source"),
                    record.get("metadata_source"),
                    manual.get("source"),
                ),
                "manual_lock": bool(
                    record.get("manual_lock")
                    or record.get("manual_locked")
                    or manual.get("accepted")
                ),
                "identity_revision": max(1, int(record.get("identity_revision", 0) or 0)),
                "enrichment_status": "complete" if provider_complete else "incomplete",
            }
            report["preserved"] += 1
            report["backfilled"] += int(was_backfilled)
            report["incomplete"] += int(not provider_complete)
            continue

        state = {
            "needs_review": "review",
            "candidate": "review",
        }.get(legacy_status, legacy_status)
        if state not in {"review", "conflict", "unmatched"}:
            state = "unmatched"
        repaired[key] = {
            **record,
            "identity_status": state,
            "identity_revision": int(record.get("identity_revision", 0) or 0),
        }
        report["conflicting" if state == "conflict" else state] += 1
    return {"files": repaired, "report": report}
