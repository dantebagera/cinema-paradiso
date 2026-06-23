import os

from services.movie_identity import normalize_movie_title
from services.smart_match import rank_candidates


def _year(value):
    text = str(value or "").strip()
    return text if len(text) == 4 and text.isdigit() else ""


def _candidate_id(candidate):
    return str(
        candidate.get("tmdb_id")
        or candidate.get("id")
        or candidate.get("imdb_id")
        or candidate.get("plex_guid")
        or ""
    )


def _title_variants(candidate):
    return {
        normalize_movie_title(value)
        for value in (
            candidate.get("title"),
            candidate.get("original_title"),
            *(candidate.get("alternative_titles") or []),
        )
        if value
    }


def _exact_title_year(identity, candidate):
    title = normalize_movie_title((identity or {}).get("title"))
    year = _year((identity or {}).get("year"))
    return bool(
        title
        and year
        and title in _title_variants(candidate or {})
        and year == _year((candidate or {}).get("year"))
    )


def _provider_signal(candidate, provider):
    if provider == "tmdb":
        return max(
            int(candidate.get("tmdb_vote_count", 0) or 0),
            int(float(candidate.get("popularity", 0) or 0)),
        )
    return int(float(candidate.get("score", 0) or 0))


def _candidate_identity_key(candidate):
    return _candidate_id(candidate) or "|".join((
        normalize_movie_title(candidate.get("title")),
        _year(candidate.get("year")),
    ))


def _matching_queries(candidate, queries):
    variants = _title_variants(candidate)
    return [
        query for query in (queries or [])
        if normalize_movie_title(query.get("title")) in variants
    ]


def _result(status, ranked, queries, automatic=False, candidate=None, reasons=None, date_discrepancy=False):
    selected = dict(candidate or (ranked[0] if ranked else {}))
    alternatives = [
        item for item in ranked
        if _candidate_identity_key(item) != _candidate_identity_key(selected)
    ][:3]
    return {
        "status": status,
        "automatic": automatic,
        "candidate": selected,
        "alternatives": alternatives,
        "evidence_score": int(selected.get("evidence_score", 0) or 0),
        "runner_up_gap": int(selected.get("runner_up_gap", 0) or 0),
        "reasons": list(reasons if reasons is not None else selected.get("reasons") or []),
        "query_sources": list(dict.fromkeys(
            query.get("source", "") for query in queries if query.get("source")
        )),
        "date_discrepancy": bool(date_discrepancy),
    }


def _dominates_same_identity_candidates(top, ranked, provider):
    rivals = [
        candidate
        for candidate in (ranked or [])[1:]
        if _exact_title_year(
            {"title": top.get("title"), "year": top.get("year")},
            candidate,
        )
    ]
    if not rivals:
        return True
    top_signal = _provider_signal(top, provider)
    rival_signal = max((_provider_signal(candidate, provider) for candidate in rivals), default=0)
    return top_signal >= 100 and top_signal >= max(1, rival_signal) * 5


def _local_exact_title_year_sources(candidate, queries):
    return {
        str(query.get("source") or "")
        for query in (queries or [])
        if query.get("source") in {"filename", "folder", "plex_hint"}
        and _exact_title_year(query, candidate)
    }


def _has_filename_or_folder_and_plex_agreement(candidate, queries):
    sources = _local_exact_title_year_sources(candidate, queries)
    return "plex_hint" in sources and bool(sources & {"filename", "folder"})


def _plex_agreement_overrides_low_rivals(top, rivals, queries):
    top = dict(top or {})
    rivals = [dict(candidate or {}) for candidate in (rivals or [])]
    if not top or not rivals:
        return False
    if not _has_filename_or_folder_and_plex_agreement(top, queries):
        return False
    if int(top.get("provider_rank", 0) or 0) != 1:
        return False
    top_sources = set(top.get("query_sources") or [])
    if not {"title_with_year", "title_without_year"}.issubset(top_sources):
        return False
    top_signal = _provider_signal(top, "tmdb")
    if top_signal < 50:
        return False
    for rival in rivals:
        rival_signal = _provider_signal(rival, "tmdb")
        rival_rank = int(rival.get("provider_rank", 999) or 999)
        if rival_rank == 1:
            return False
        if rival_signal > top_signal:
            return False
        if rival_signal >= 100 and top_signal < rival_signal * 2:
            return False
    return True


def _dominates_exact_title_year_rivals(top, rivals, queries=None):
    top = dict(top or {})
    rivals = [dict(candidate or {}) for candidate in (rivals or [])]
    if not top or not rivals:
        return True
    if int(top.get("provider_rank", 0) or 0) != 1:
        return False
    top_sources = set(top.get("query_sources") or [])
    if not {"title_with_year", "title_without_year"}.issubset(top_sources):
        return False
    top_signal = _provider_signal(top, "tmdb")
    if top_signal <= 0:
        return False

    for rival in rivals:
        rival_signal = _provider_signal(rival, "tmdb")
        rival_rank = int(rival.get("provider_rank", 999) or 999)
        if rival_signal == 0:
            continue
        if rival_rank >= 5 and top_signal >= rival_signal:
            continue
        if top_signal >= rival_signal * 5:
            continue
        return False
    return True


def classify_audit_decision(current, queries, ranked, provider):
    current = dict(current or {})
    ranked = list(ranked or [])
    top = dict(ranked[0]) if ranked else {}
    if not top:
        return {
            "classification": "review",
            "automatic": False,
            "preselected": False,
            "candidate": {},
            "reason": "No provider candidate",
        }
    provider_id_key = "tmdb_id" if provider == "tmdb" else "plex_guid"
    current_id = str(current.get(provider_id_key, "") or "")
    candidate_id = str(
        top.get(provider_id_key)
        or (top.get("guid") if provider == "plex" else "")
        or ""
    )
    if current_id and candidate_id and current_id == candidate_id:
        classification = "verified"
    elif (
        not current_id
        and _exact_title_year(current, top)
        and int(top.get("evidence_score", 0) or 0) >= 80
        and int(top.get("provider_rank", 0) or 0) == 1
        and not top.get("identity_conflict")
        and _dominates_same_identity_candidates(top, ranked, provider)
        and (
            any(
                query.get("source") in {"filename", "folder"}
                and _exact_title_year(query, top)
                for query in (queries or [])
            )
            or (
                int(top.get("evidence_score", 0) or 0) == 100
                and int(top.get("runner_up_gap", 0) or 0) >= 15
            )
        )
    ):
        classification = "automatically_verified"
    elif (
        current_id
        and candidate_id
        and current_id != candidate_id
        and int(top.get("evidence_score", 0) or 0) >= 90
        and int(top.get("runner_up_gap", 0) or 0) >= 15
        and any(
            query.get("source") in {"filename", "folder"}
            and _exact_title_year(query, top)
            for query in (queries or [])
        )
        and not top.get("identity_conflict")
    ):
        classification = "recommended"
    elif int(top.get("evidence_score", 0) or 0) < 70:
        classification = "weak"
    else:
        classification = "review"
    return {
        "classification": classification,
        "automatic": classification == "automatically_verified",
        "preselected": classification == "recommended",
        "candidate": top,
    }


def metadata_discrepancy_proposal(current, filename_identity, has_override=False):
    current = dict(current or {})
    filename_identity = dict(filename_identity or {})
    if has_override:
        return {}
    if not any(current.get(key) for key in ("tmdb_id", "imdb_id", "plex_guid")):
        return {}
    current_title = normalize_movie_title(current.get("title"))
    filename_title = normalize_movie_title(filename_identity.get("title"))
    current_year = _year(current.get("year"))
    filename_year = _year(filename_identity.get("year"))
    if (
        not current_title
        or current_title != filename_title
        or not current_year
        or not filename_year
        or abs(int(current_year) - int(filename_year)) <= 2
    ):
        return {}
    return {
        "proposal_type": "metadata_discrepancy",
        "classification": "review",
        "automatic": False,
        "preselected": False,
        "current": current,
        "candidate": {
            **current,
            "title": current.get("title", ""),
            "year": filename_year,
        },
        "evidence_score": 100,
        "runner_up_gap": 0,
        "reasons": [
            "accepted provider identity matches the filename title",
            f"filename year differs from provider year by {abs(int(current_year) - int(filename_year))} years",
        ],
    }


def decide_identity(queries, candidates, known_identity=None):
    queries = [dict(query or {}) for query in (queries or []) if query.get("title")]
    ranked = rank_candidates(queries, candidates or [], known_identity=known_identity or {})
    if not ranked:
        return _result("unmatched", [], queries, reasons=["no provider candidates"])

    strong_matches = [
        candidate for candidate in ranked
        if "existing provider ID matches" in (candidate.get("reasons") or [])
    ]
    if strong_matches:
        return _result("accepted", ranked, queries, True, strong_matches[0])

    non_conflicting = [candidate for candidate in ranked if not candidate.get("identity_conflict")]
    if not non_conflicting:
        return _result("conflict", ranked, queries, candidate=ranked[0])

    exact = [
        candidate for candidate in non_conflicting
        if _matching_queries(candidate, queries)
    ]
    exact_year = [
        candidate for candidate in exact
        if any(
            _year(query.get("year"))
            and _year(query.get("year")) == _year(candidate.get("year"))
            for query in _matching_queries(candidate, queries)
        )
    ]
    exact_year_ids = {_candidate_identity_key(candidate) for candidate in exact_year}
    if len(exact_year_ids) == 1:
        chosen = next(candidate for candidate in exact_year if _candidate_identity_key(candidate) in exact_year_ids)
        return _result("accepted", ranked, queries, True, chosen)
    if len(exact_year_ids) > 1:
        chosen = exact_year[0]
        rivals = [
            candidate for candidate in exact_year
            if _candidate_identity_key(candidate) != _candidate_identity_key(chosen)
        ]
        if _dominates_exact_title_year_rivals(chosen, rivals):
            return _result(
                "accepted", ranked, queries, True, chosen,
                reasons=[
                    "dominant exact title and year match",
                    *list(chosen.get("reasons") or []),
                ],
            )
        if _plex_agreement_overrides_low_rivals(chosen, rivals, queries):
            return _result(
                "accepted", ranked, queries, True, chosen,
                reasons=[
                    "filename and Plex agree",
                    "rank one exact title and year match",
                    *list(chosen.get("reasons") or []),
                ],
            )
        return _result(
            "review", ranked, queries, candidate=exact_year[0],
            reasons=["multiple provider identities have the same exact title and year"],
        )

    yearless_exact = [
        candidate for candidate in exact
        if any(not _year(query.get("year")) for query in _matching_queries(candidate, queries))
    ]
    yearless_ids = {_candidate_identity_key(candidate) for candidate in yearless_exact}
    if len(yearless_ids) == 1:
        chosen = yearless_exact[0]
        return _result("accepted", ranked, queries, True, chosen)
    if len(yearless_ids) > 1:
        return _result(
            "review", ranked, queries, candidate=yearless_exact[0],
            reasons=["multiple releases share the exact title"],
        )

    one_year = []
    for candidate in exact:
        candidate_year = _year(candidate.get("year"))
        if not candidate_year:
            continue
        for query in _matching_queries(candidate, queries):
            query_year = _year(query.get("year"))
            if query_year and abs(int(query_year) - int(candidate_year)) == 1:
                one_year.append(candidate)
                break
    one_year_ids = {_candidate_identity_key(candidate) for candidate in one_year}
    competing_exact_ids = {_candidate_identity_key(candidate) for candidate in exact}
    if len(one_year_ids) == 1 and len(competing_exact_ids) == 1:
        return _result(
            "accepted", ranked, queries, True, one_year[0],
            date_discrepancy=True,
        )
    if one_year:
        return _result(
            "review", ranked, queries, candidate=one_year[0],
            reasons=["the title matches but multiple releases are plausible"],
        )

    top = non_conflicting[0]
    top_reasons = set(top.get("reasons") or [])
    if (
        int(top.get("evidence_score", 0) or 0) >= 90
        and int(top.get("runner_up_gap", 0) or 0) >= 20
        and "strong title similarity" in top_reasons
        and "found by multiple independent queries" in top_reasons
    ):
        return _result("accepted", ranked, queries, True, top)

    plausible = [
        candidate for candidate in non_conflicting
        if int(candidate.get("evidence_score", 0) or 0) >= 55
    ]
    if len(plausible) > 1:
        return _result("review", ranked, queries, candidate=plausible[0])
    return _result("unmatched", ranked, queries, candidate=top)


def _record_identity(record):
    canonical = record.get("canonical_metadata") or {}
    return {
        "path": str(record.get("path") or canonical.get("path") or ""),
        "tmdb_id": str(canonical.get("tmdb_id") or record.get("tmdb_id") or ""),
        "imdb_id": str(canonical.get("imdb_id") or record.get("imdb_id") or "").lower(),
        "title": str(canonical.get("title") or record.get("title") or record.get("plex_title") or ""),
        "year": str(canonical.get("year") or record.get("year") or record.get("plex_year") or ""),
    }


def resolve_collection_membership(collection, library_records):
    parts = list((collection or {}).get("parts") or [])
    records = [_record_identity(record or {}) for record in (library_records or [])]
    owned_paths = []
    unresolved = []
    conflicts = []
    matched_record_paths = set()
    for part in parts:
        part_path = os.path.normcase(os.path.abspath(str(part.get("path") or ""))) if part.get("path") else ""
        part_tmdb = str(part.get("tmdb_id") or "")
        part_imdb = str(part.get("imdb_id") or "").lower()
        part_title = normalize_movie_title(part.get("title"))
        part_year = str(part.get("year") or "")
        matches = []
        for record in records:
            record_path = os.path.normcase(os.path.abspath(record["path"])) if record["path"] else ""
            if part_path and record_path == part_path:
                matches.append(record)
                continue
            if part_tmdb and record["tmdb_id"]:
                if part_tmdb == record["tmdb_id"]:
                    matches.append(record)
                continue
            if part_imdb and record["imdb_id"]:
                if part_imdb == record["imdb_id"]:
                    matches.append(record)
                continue
            if (
                part_title
                and part_year
                and normalize_movie_title(record["title"]) == part_title
                and record["year"] == part_year
            ):
                matches.append(record)
        unique = {record["path"]: record for record in matches if record["path"]}
        if len(unique) == 1:
            path = next(iter(unique))
            if path not in matched_record_paths:
                owned_paths.append(path)
                matched_record_paths.add(path)
        elif len(unique) > 1:
            conflicts.append({"part": part, "paths": list(unique)})
        else:
            unresolved.append(part)
    return {
        "owned_paths": owned_paths,
        "unresolved_parts": unresolved,
        "conflicts": conflicts,
    }
