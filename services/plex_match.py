import json
import urllib.error
import urllib.parse
import urllib.request


class PlexMatchError(RuntimeError):
    def __init__(self, message, status=502):
        super().__init__(message)
        self.status = int(status or 502)


class PlexMatchAdapter:
    def __init__(self, base_url, token, open_url=None, timeout=15):
        self.base_url = str(base_url or "").rstrip("/")
        self.token = str(token or "")
        self.open_url = open_url or urllib.request.urlopen
        self.timeout = timeout

    def _safe_error_detail(self, error):
        try:
            detail = error.read(500).decode("utf-8", "replace").strip()
        except Exception:
            detail = ""
        if self.token:
            detail = detail.replace(self.token, "[redacted]")
        return " ".join(detail.split())[:300]

    def _query(self, rating_key, title, year, source):
        params = {"manual": "1", "title": title}
        if year and source == "title_year":
            params["year"] = str(year)
        query = urllib.parse.urlencode(params)
        url = (
            f"{self.base_url}/library/metadata/"
            f"{urllib.parse.quote(str(rating_key), safe='')}/matches?{query}"
        )
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "X-Plex-Token": self.token,
            },
        )
        try:
            with self.open_url(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            detail = self._safe_error_detail(error)
            suffix = f": {detail}" if detail else ""
            raise PlexMatchError(
                f"Plex returned HTTP {error.code}{suffix}",
                status=error.code,
            ) from error
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise PlexMatchError("Plex returned a malformed matching response") from error
        except PlexMatchError:
            raise
        except Exception as error:
            message = str(error)
            if self.token:
                message = message.replace(self.token, "[redacted]")
            raise PlexMatchError(f"Cannot reach Plex matching service: {message}") from error

        results = (payload.get("MediaContainer") or {}).get("SearchResult", [])
        if not isinstance(results, list):
            raise PlexMatchError("Plex returned a malformed matching response")
        return results

    def search(self, rating_key, title="", year="", imdb_id="", tmdb_id=""):
        queries = []
        clean_title = str(title or "").strip()
        if clean_title:
            queries.append(("title_year", clean_title))
        clean_imdb = str(imdb_id or "").strip().lower()
        if clean_imdb:
            queries.append(("imdb_id", f"imdb-{clean_imdb}"))
        clean_tmdb = str(tmdb_id or "").strip()
        if clean_tmdb:
            queries.append(("tmdb_id", f"tmdb-{clean_tmdb}"))
        if not queries:
            return []

        merged = {}
        for source, query_title in queries:
            for rank, raw in enumerate(
                self._query(rating_key, query_title, year, source),
                1,
            ):
                guid = str(raw.get("guid") or "").strip()
                if not guid:
                    continue
                candidate = merged.get(guid)
                if candidate is None:
                    candidate = {
                        "guid": guid,
                        "title": str(raw.get("name") or raw.get("title") or ""),
                        "name": str(raw.get("name") or raw.get("title") or ""),
                        "year": str(raw.get("year") or ""),
                        "score": int(raw.get("score") or 0),
                        "rank": rank,
                        "provider_rank": rank,
                        "poster_url": str(raw.get("thumb") or ""),
                        "summary": str(raw.get("summary") or ""),
                        "query_sources": [],
                        "match_reasons": [],
                        "exact_external_id": False,
                    }
                    merged[guid] = candidate
                candidate["provider_rank"] = min(
                    int(candidate.get("provider_rank") or rank),
                    rank,
                )
                candidate["rank"] = candidate["provider_rank"]
                if source not in candidate["query_sources"]:
                    candidate["query_sources"].append(source)
                if source == "imdb_id":
                    if rank == 1:
                        candidate["exact_external_id"] = True
                        candidate["match_reasons"].append("Exact IMDb identity")
                elif source == "tmdb_id":
                    if rank == 1:
                        candidate["exact_external_id"] = True
                        candidate["match_reasons"].append("Exact TMDB identity")
                elif source == "title_year":
                    candidate["match_reasons"].append("Plex title and year search")

        source_rank = {"imdb_id": 0, "tmdb_id": 1, "title_year": 2}
        for candidate in merged.values():
            candidate["query_sources"] = sorted(
                set(candidate["query_sources"]),
                key=lambda source: source_rank.get(source, 99),
            )
            candidate["match_reasons"] = list(
                dict.fromkeys(candidate["match_reasons"])
            )
        return sorted(
            merged.values(),
            key=lambda item: (
                not item.get("exact_external_id"),
                int(item.get("provider_rank") or 999),
                str(item.get("title") or "").lower(),
            ),
        )[:20]
