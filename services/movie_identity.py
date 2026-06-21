import re


def normalize_movie_title(title):
    if not title:
        return ""
    value = str(title).lower()
    value = re.sub(r"[^\w\s]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    value = re.sub(r"^(the|a|an) ", "", value)
    tokens = value.split()
    normalized = []
    index = 0
    while index < len(tokens):
        if len(tokens[index]) == 1 and tokens[index].isalnum():
            end = index
            while end < len(tokens) and len(tokens[end]) == 1 and tokens[end].isalnum():
                end += 1
            if end - index > 1:
                normalized.append("".join(tokens[index:end]))
            else:
                normalized.append(tokens[index])
            index = end
            continue
        normalized.append(tokens[index])
        index += 1
    return " ".join(normalized)


def same_public_identity(left_title, left_year, right_title, right_year):
    left = normalize_movie_title(left_title)
    right = normalize_movie_title(right_title)
    if not left or not right or left != right:
        return False
    left_year = str(left_year or "").strip()
    right_year = str(right_year or "").strip()
    return not left_year or not right_year or left_year == right_year


def ownership_keys(movie):
    movie = movie or {}
    keys = []
    tmdb_id = str(movie.get("tmdb_id", "") or "").strip()
    imdb_id = str(movie.get("imdb_id", "") or "").strip()
    plex_guid = str(movie.get("plex_guid", "") or "").strip()
    title = normalize_movie_title(movie.get("title", ""))
    year = str(movie.get("year", "") or "").strip()
    if tmdb_id:
        keys.append(f"tmdb:{tmdb_id}")
    if imdb_id:
        keys.append(f"imdb:{imdb_id.lower()}")
    if plex_guid:
        keys.append(f"plex:{plex_guid.lower()}")
    if title and year:
        keys.append(f"title:{title}|{year}")
    return keys


def _record_title_keys(record):
    keys = []
    for title_field, year_field in (
        ("title", "year"),
        ("plex_title", "plex_year"),
        ("parsed_title", "parsed_year"),
    ):
        title = normalize_movie_title(record.get(title_field, ""))
        year = str(record.get(year_field, "") or "").strip()
        if title:
            keys.append(f"title:{title}|{year}")
    return list(dict.fromkeys(keys))


def _record_strong_ids(record):
    return {
        "tmdb": str(record.get("tmdb_id", "") or "").strip(),
        "imdb": str(record.get("imdb_id", "") or "").strip().lower(),
    }


def group_identity_records(records):
    records = list(records or [])
    parents = list(range(len(records)))
    group_ids = [_record_strong_ids(record) for record in records]

    def find(index):
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def can_merge(left, right):
        left_ids = group_ids[find(left)]
        right_ids = group_ids[find(right)]
        for provider in ("tmdb", "imdb"):
            if left_ids[provider] and right_ids[provider] and left_ids[provider] != right_ids[provider]:
                return False
        return True

    def union(left, right):
        left_root = find(left)
        right_root = find(right)
        if left_root == right_root or not can_merge(left_root, right_root):
            return
        parents[right_root] = left_root
        for provider in ("tmdb", "imdb"):
            group_ids[left_root][provider] = group_ids[left_root][provider] or group_ids[right_root][provider]

    strong_indexes = {}
    title_indexes = {}
    for index, record in enumerate(records):
        ids = _record_strong_ids(record)
        for provider in ("tmdb", "imdb"):
            value = ids[provider]
            if not value:
                continue
            key = f"{provider}:{value}"
            if key in strong_indexes:
                union(index, strong_indexes[key])
            else:
                strong_indexes[key] = index
        for key in _record_title_keys(record):
            for candidate in title_indexes.get(key, []):
                union(index, candidate)
            title_indexes.setdefault(key, []).append(index)

    grouped = {}
    for index, record in enumerate(records):
        grouped.setdefault(find(index), []).append(record)
    return list(grouped.values())
