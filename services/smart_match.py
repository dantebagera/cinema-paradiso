import os
import re
import threading
import time
import uuid
import unicodedata
from difflib import SequenceMatcher

from services.movie_identity import normalize_movie_title


_EDITIONS = (
    (r"\bdirector(?:'s|s)?[ ._-]*cut\b", "Director's Cut"),
    (r"\bfinal[ ._-]*cut\b", "Final Cut"),
    (r"\bunrated\b", "Unrated"),
    (r"\bextended\b", "Extended"),
    (r"\btheatrical\b", "Theatrical"),
    (r"\bremastered\b", "Remastered"),
)
_RESOLUTIONS = (
    (r"\b(?:2160p|4k|uhd)\b", "4K"),
    (r"\b1080p?\b", "1080p"),
    (r"\b720p?\b", "720p"),
    (r"\b480p?\b", "480p"),
)
_SOURCES = (
    (r"\b(?:web[ ._-]*dl|webdl)\b", "WEB-DL"),
    (r"\b(?:web[ ._-]*rip|webrip)\b", "WEBRip"),
    (r"\b(?:blu[ ._-]*ray|bluray)\b", "Blu-ray"),
    (r"\b(?:bd[ ._-]*remux|bdremux)\b", "BD Remux"),
    (r"\bbdrip\b", "BDRip"),
    (r"\bhdtv\b", "HDTV"),
    (r"\bdvdrip\b", "DVDRip"),
)
_NOISE = re.compile(
    r"\b(?:h264|h265|x264|x265|hevc|avc|10bit|8bit|aac|ac3|eac3|dts|"
    r"mp4|mkv|avi|eng|english|subs?|subtitles?|dual[ ._-]*audio|multi|"
    r"sci[ ._-]*fi|science[ ._-]*fiction|action|drama|comedy|horror|thriller|"
    r"alternate[ ._-]*ending)\b",
    re.IGNORECASE,
)


def _display_title(value):
    words = [word for word in re.split(r"\s+", value.strip()) if word]
    result = []
    for index, word in enumerate(words):
        lower = word.lower()
        if lower in {"vs", "versus"}:
            result.append("vs.")
        elif lower in {"and", "of", "the", "a", "an"} and index:
            result.append(lower)
        else:
            result.append(word.capitalize())
    return " ".join(result)


def parse_release_filename(filename):
    stem = os.path.splitext(os.path.basename(str(filename or "")))[0]
    original = unicodedata.normalize("NFKC", stem)
    original = re.sub(r"[\u2010-\u2015]", "-", original)
    original = re.sub(r"^\s*\d{1,3}[\s._-]+", "", original)
    year_match = re.search(r"(?<!\d)((?:19|20)\d{2})(?!\d)", original)
    year = year_match.group(1) if year_match else ""
    text = original[:year_match.start()] if year_match else original
    release_text = original

    edition = ""
    for pattern, label in _EDITIONS:
        if re.search(pattern, release_text, re.IGNORECASE):
            edition = label
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE)

    resolution = ""
    for pattern, label in _RESOLUTIONS:
        if not resolution and re.search(pattern, release_text, re.IGNORECASE):
            resolution = label
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE)

    source = ""
    for pattern, label in _SOURCES:
        if not source and re.search(pattern, release_text, re.IGNORECASE):
            source = label
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE)

    text = re.sub(r"\[[^\]]*\]|\{[^}]*\}", " ", text)
    text = _NOISE.sub(" ", text)
    text = re.sub(r"[-_.]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    tokens = text.split()
    if len(tokens) >= 3:
        acronym = "".join(token[0] for token in tokens[:-1] if token.lower() not in {"the", "a", "an"})
        if tokens[-1].isupper() and len(tokens[-1]) >= 2 and tokens[-1].lower() == acronym.lower():
            tokens.pop()
    title = _display_title(" ".join(tokens))
    return {
        "title": title,
        "year": year,
        "edition": edition,
        "resolution": resolution,
        "source": source,
    }


def _title_variants(candidate):
    values = [
        candidate.get("title", ""),
        candidate.get("original_title", ""),
        *(candidate.get("alternative_titles", []) or []),
    ]
    variants = set()
    for value in values:
        normalized = normalize_movie_title(value)
        if normalized:
            variants.add(normalized)
            variants.add(re.sub(r"^(?:avp|aka)\s+", "", normalized))
    return variants


def parse_ai_match_response(content, expected_ids=None):
    text = str(content or "").strip()
    text = re.sub(r"^\s*```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```\s*$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("AI response did not contain a JSON object")
    import json
    payload = json.loads(text[start:end + 1])
    entries = payload.get("matches")
    if entries is None and any(key in payload for key in ("id", "title", "canonical")):
        entries = [payload]
    if not isinstance(entries, list):
        raise ValueError("AI response is missing a matches list")
    matches = {}
    duplicate_ids = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        item_id = str(entry.get("id", "") or "").strip()
        title = str(entry.get("title") or entry.get("canonical") or "").strip()
        if not item_id or not title:
            continue
        if item_id in matches:
            duplicate_ids.append(item_id)
            continue
        alternatives = []
        for alternative in (entry.get("alternatives") or [])[:3]:
            if not isinstance(alternative, dict):
                continue
            alt_title = str(alternative.get("title") or alternative.get("canonical") or "").strip()
            if not alt_title:
                continue
            alternatives.append({
                "title": alt_title,
                "year": _normalize_year(alternative.get("year")),
            })
        matches[item_id] = {
            "title": title,
            "year": _normalize_year(entry.get("year")),
            "alternatives": alternatives,
        }
    expected = [str(item_id) for item_id in (expected_ids or [])]
    return {
        "matches": matches,
        "missing_ids": [item_id for item_id in expected if item_id not in matches],
        "duplicate_ids": list(dict.fromkeys(duplicate_ids)),
    }


def _normalize_year(value):
    text = str(value or "").strip()
    match = re.search(r"(?:19|20)\d{2}", text)
    return match.group(0) if match else ""


def _title_similarity(query_title, candidate):
    query = normalize_movie_title(query_title)
    variants = _title_variants(candidate)
    if not query or not variants:
        return 0.0, ""
    if query in variants:
        return 1.0, "exact title or alias"
    best = 0.0
    for variant in variants:
        query_tokens = set(query.split())
        variant_tokens = set(variant.split())
        overlap = len(query_tokens & variant_tokens) / max(1, len(query_tokens | variant_tokens))
        sequence = SequenceMatcher(None, query, variant).ratio()
        containment = min(len(query), len(variant)) / max(len(query), len(variant)) if query in variant or variant in query else 0
        best = max(best, overlap, sequence, containment)
    if best >= 0.78:
        return best, "strong title similarity"
    if best >= 0.58:
        return best, "moderate title similarity"
    return best, ""


def _candidate_identity(candidate):
    for key in ("tmdb_id", "guid", "plex_guid", "imdb_id"):
        value = str(candidate.get(key, "") or "").strip().lower()
        if value:
            return f"{key}:{value}"
    return "|".join((
        normalize_movie_title(candidate.get("title", "")),
        str(candidate.get("year", "") or ""),
    ))


def _score_evidence(queries, candidate, known_identity=None):
    known_identity = known_identity or {}
    candidate = dict(candidate or {})
    reasons = []
    known_tmdb = str(known_identity.get("tmdb_id", "") or "")
    candidate_tmdb = str(candidate.get("tmdb_id", "") or "")
    known_imdb = str(known_identity.get("imdb_id", "") or "").lower()
    candidate_imdb = str(candidate.get("imdb_id", "") or "").lower()
    known_plex_guid = str(known_identity.get("plex_guid", "") or "").lower()
    candidate_plex_guid = str(candidate.get("guid", "") or candidate.get("plex_guid", "") or "").lower()
    for known, current, label in (
        (known_tmdb, candidate_tmdb, "TMDB ID"),
        (known_imdb, candidate_imdb, "IMDb ID"),
        (known_plex_guid, candidate_plex_guid, "Plex GUID"),
    ):
        if known and current and known != current:
            return 0, [f"conflicting {label}"], True
    strong_id_match = bool(
        (known_tmdb and known_tmdb == candidate_tmdb)
        or (known_imdb and known_imdb == candidate_imdb)
        or (known_plex_guid and known_plex_guid == candidate_plex_guid)
    )
    if strong_id_match:
        return 100, ["existing provider ID matches"], False

    best_title_score = 0
    best_title_reason = ""
    best_year_score = 0
    best_year_reason = ""
    for query in queries:
        similarity, title_reason = _title_similarity(query.get("title", ""), candidate)
        title_score = 60 if similarity == 1 else 50 if similarity >= 0.78 else 35 if similarity >= 0.58 else 0
        if title_score > best_title_score:
            best_title_score = title_score
            best_title_reason = title_reason
        query_year = _normalize_year(query.get("year"))
        candidate_year = _normalize_year(candidate.get("year"))
        if query_year and candidate_year:
            difference = abs(int(query_year) - int(candidate_year))
            year_score = 20 if difference == 0 else 10 if difference == 1 else -25
            year_reason = (
                "release year matches"
                if difference == 0
                else "release year is within one year"
                if difference == 1
                else "release year differs by more than one year"
            )
            if year_score > best_year_score or not best_year_reason:
                best_year_score = year_score
                best_year_reason = year_reason
    score = best_title_score + best_year_score
    if best_title_reason:
        reasons.append(best_title_reason)
    if best_year_reason:
        reasons.append(best_year_reason)

    rank = int(candidate.get("provider_rank", 0) or 0)
    rank_bonus = {1: 10, 2: 6, 3: 3}.get(rank, 0)
    if rank_bonus:
        score += rank_bonus
        reasons.append(f"provider result rank {rank}")
    query_sources = list(dict.fromkeys(candidate.get("query_sources", []) or []))
    if len(query_sources) >= 2:
        score += 10
        reasons.append("found by multiple independent queries")
    candidate_title = normalize_movie_title(candidate.get("title", ""))
    query_has_qualifier = any(
        re.search(r"\b(?:making of|behind the scenes)\b", normalize_movie_title(query.get("title", "")))
        for query in queries
    )
    if re.search(r"\b(?:making of|behind the scenes)\b", candidate_title) and not query_has_qualifier:
        score -= 25
        reasons.append("unrequested making-of qualifier")
    return max(0, min(score, 100)), reasons or ["limited matching evidence"], False


def rank_candidates(queries, candidates, known_identity=None):
    queries = [query for query in (queries or []) if query.get("title")]
    merged = {}
    for candidate in candidates or []:
        identity = _candidate_identity(candidate)
        current = merged.get(identity)
        if current is None:
            merged[identity] = dict(candidate)
            continue
        current["provider_rank"] = min(
            int(current.get("provider_rank", 999) or 999),
            int(candidate.get("provider_rank", 999) or 999),
        )
        current["query_sources"] = list(dict.fromkeys(
            [*(current.get("query_sources", []) or []), *(candidate.get("query_sources", []) or [])]
        ))
        current["alternative_titles"] = list(dict.fromkeys(
            [*(current.get("alternative_titles", []) or []), *(candidate.get("alternative_titles", []) or [])]
        ))
    ranked = []
    for candidate in merged.values():
        score, reasons, conflict = _score_evidence(queries, candidate, known_identity)
        ranked.append({
            **candidate,
            "evidence_score": score,
            "confidence": score,
            "reasons": reasons,
            "identity_conflict": conflict,
        })
    ranked.sort(key=lambda item: int(item.get("evidence_score", 0)), reverse=True)
    for index, candidate in enumerate(ranked):
        runner_up = int(ranked[index + 1].get("evidence_score", 0)) if index + 1 < len(ranked) else 0
        gap = max(0, int(candidate.get("evidence_score", 0)) - runner_up)
        strong_id = "existing provider ID matches" in candidate.get("reasons", [])
        score = int(candidate.get("evidence_score", 0))
        recommendation = (
            "recommended"
            if strong_id or (score >= 80 and gap >= 15)
            else "review"
            if score >= 55 and gap >= 8
            else "weak"
        )
        candidate["runner_up_gap"] = gap
        candidate["recommendation"] = recommendation
        candidate["preselected"] = recommendation == "recommended" and not candidate.get("identity_conflict")
    return ranked


def score_candidate(parsed, candidate, known_identity=None):
    ranked = rank_candidates([parsed or {}], [{**(candidate or {}), "provider_rank": 1}], known_identity)
    return ranked[0] if ranked else {
        "confidence": 0,
        "evidence_score": 0,
        "runner_up_gap": 0,
        "recommendation": "weak",
        "preselected": False,
        "reasons": ["candidate requires manual review"],
    }


def build_rename_filename(title, year, release, extension):
    release = release or {}
    name = str(title or "").strip()
    if year:
        name += f" ({year})"
    if release.get("edition"):
        name += f" [{release['edition']}]"
    quality = " ".join(
        value for value in (release.get("resolution", ""), release.get("source", "")) if value
    )
    if quality:
        name += f" [{quality}]"
    name = re.sub(r'[<>:"/\\|?*]', "", name).strip()
    extension = str(extension or "")
    if extension and not extension.startswith("."):
        extension = f".{extension}"
    return f"{name}{extension}"


def validate_rename_filename(filename):
    filename = str(filename or "")
    if filename.startswith(".") and filename.count(".") == 1:
        return False
    stem = os.path.splitext(filename)[0].strip().rstrip(". ")
    if not stem:
        return False
    reserved = {
        "con", "prn", "aux", "nul",
        *(f"com{number}" for number in range(1, 10)),
        *(f"lpt{number}" for number in range(1, 10)),
    }
    return stem.lower() not in reserved and filename == os.path.basename(filename)


class SmartMatchCoordinator:
    def __init__(
        self,
        load_state,
        save_state,
        process_path,
        process_batch=None,
        batch_size=5,
        batch_delay=0.1,
    ):
        self._load_state = load_state
        self._save_state = save_state
        self._process_path = process_path
        self._process_batch = process_batch
        self._batch_size = batch_size
        self._batch_delay = batch_delay
        self._lock = threading.RLock()
        self._thread = None
        self._recover_interrupted_state()

    def _recover_interrupted_state(self):
        state = self._load_state() or {}
        if state.get("status") != "running":
            return
        now = time.time()
        self._save_state({
            **state,
            "status": "paused",
            "current_path": "",
            "interrupted_at": now,
            "updated_at": now,
        })

    def _default_state(self):
        return {
            "id": "",
            "status": "idle",
            "provider": "tmdb",
            "method": "classic",
            "paths": [],
            "processed": 0,
            "remaining": 0,
            "total": 0,
            "proposals": [],
            "unresolved": [],
            "errors": [],
            "preselected": 0,
            "current_path": "",
            "started_at": 0,
            "updated_at": 0,
            "completed_at": 0,
        }

    def status(self):
        with self._lock:
            return {**self._default_state(), **(self._load_state() or {})}

    def start(self, paths, provider, method, background=True):
        with self._lock:
            current = self.status()
            if current["status"] in {"running", "paused"}:
                raise RuntimeError("Smart Match preview is already active")
            paths = list(dict.fromkeys(paths or []))
            now = time.time()
            state = {
                **self._default_state(),
                "id": uuid.uuid4().hex,
                "status": "running",
                "provider": provider,
                "method": method,
                "paths": paths,
                "remaining": len(paths),
                "total": len(paths),
                "started_at": now,
                "updated_at": now,
            }
            self._save_state(state)
        if background:
            self._ensure_thread()
        return self.status()

    def cancel(self):
        with self._lock:
            state = self.status()
            if state["status"] == "running":
                state["status"] = "cancelled"
                state["current_path"] = ""
                state["updated_at"] = time.time()
                self._save_state(state)
            return dict(state)

    def resume(self, background=True):
        with self._lock:
            state = self.status()
            if state["status"] == "running" and state["remaining"] > 0:
                pass
            elif state["status"] in {"paused", "cancelled"} and state["remaining"] > 0:
                state["status"] = "running"
                state["updated_at"] = time.time()
                self._save_state(state)
        if background and self.status()["status"] == "running":
            self._ensure_thread()
        return self.status()

    def run_batch(self, limit=None):
        with self._lock:
            state = self.status()
            if state["status"] != "running":
                return state
            batch = state["paths"][state["processed"]:state["processed"] + (limit or self._batch_size)]
        batch_results = None
        batch_error = ""
        if self._process_batch:
            try:
                batch_results = list(
                    self._process_batch(batch, state["provider"], state["method"]) or []
                )
            except Exception as exc:
                batch_results = []
                batch_error = str(exc)
        for index, path in enumerate(batch):
            with self._lock:
                state = self.status()
                if state["status"] != "running":
                    return state
                state["current_path"] = path
                self._save_state(state)
            try:
                if batch_results is None:
                    result = self._process_path(path, state["provider"], state["method"]) or {}
                    error = ""
                else:
                    result = batch_results[index] if index < len(batch_results) else {}
                    error = batch_error or (
                        "" if result else "Smart Match batch did not return a result for this file"
                    )
            except Exception as exc:
                result = {}
                error = str(exc)
            with self._lock:
                state = self.status()
                if result.get("candidate") or result.get("id"):
                    proposal = dict(result)
                    proposal.setdefault("id", uuid.uuid4().hex)
                    state["proposals"] = [*state["proposals"], proposal]
                    if proposal.get("preselected"):
                        state["preselected"] += 1
                else:
                    unresolved = {"path": path, **result}
                    state["unresolved"] = [*state["unresolved"], unresolved]
                if error:
                    state["errors"] = [*state["errors"], {"path": path, "error": error}]
                state["processed"] += 1
                state["remaining"] = max(0, state["total"] - state["processed"])
                state["current_path"] = ""
                state["updated_at"] = time.time()
                self._save_state(state)
        with self._lock:
            state = self.status()
            if state["status"] == "running" and state["processed"] >= state["total"]:
                state["status"] = "completed"
                state["completed_at"] = time.time()
                state["updated_at"] = state["completed_at"]
                self._save_state(state)
            return state

    def _ensure_thread(self):
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()

    def _run_loop(self):
        while True:
            state = self.run_batch()
            if state["status"] != "running":
                return
            time.sleep(self._batch_delay)
