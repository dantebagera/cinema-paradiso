import json
import re
import socket
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from difflib import SequenceMatcher


TMDB_API_ROOT = "https://api.themoviedb.org/3"
TMDB_IMAGE_ROOT = "https://image.tmdb.org/t/p"
PARSER_VERSION = 4
MATCHER_VERSION = 3
MAX_QUERY_VARIANTS = 6
MAX_MERGED_CANDIDATES = 20
MAX_RESULTS_PER_ALIAS = 5
MAX_HYDRATED_CANDIDATES = 8
MAX_LOCALIZED_HYDRATIONS = 3
MAX_BULK_SEARCH_PAGES = 5
BULK_SEARCH_LIMIT_REASON = 'CP couldn’t finish checking competing matches.'


class IPTVTMDBError(RuntimeError):
    def __init__(self, message, *, status=0, retryable=False, retry_after=0):
        super().__init__(message)
        self.status = int(status or 0)
        self.retryable = bool(retryable)
        self.retry_after = max(0, int(retry_after or 0))


def _text(value):
    return str(value or "").strip()


def extract_year(value):
    match = re.search(r"\b(19\d{2}|20\d{2}|21\d{2})\b", _text(value))
    return int(match.group(1)) if match else 0


_year = extract_year


_YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2}|21\d{2})\b")
_PARENTHESIZED_YEAR_RE = re.compile(r"\(\s*(19\d{2}|20\d{2}|21\d{2})\s*\)")
_ARABIC_RE = re.compile(r"[\u0600-\u06ff]")
_ARABIC_MARKS_RE = re.compile(r"[\u0610-\u061a\u0640\u064b-\u065f\u0670\u06d6-\u06ed]")
_PROVIDER_SUFFIX_RE = re.compile(r"(?:\s+|^)multi\s+(?:subs?|subtitles?|audios?(?:\s+and\s+subtitles?)?)\b|\s+hd\s*$", re.I)
_RANKED_PLAYLIST_RE = re.compile(r"\bimdb\b.*\btop\s+\d+\b", re.I)
_NOISE_RE = re.compile(
    r"(?i)(?:\b(?:2160p|1080p|720p|4k|uhd|fhd|hdcam|camrip|cam|web[- .]?dl|webrip|"
    r"bluray|brrip|hdrip|x26[45]|hevc|multi|dubbed|subbed|subtitle(?:d|s)?|translated|"
    r"eng(?:lish)?\s+(?:audio|sub(?:title)?s?)|arabic\s+audio|dual\s+audio)\b|"
    r"(?:مدبلج|مترجم|ترجمة|دبلجة\s*(?:إنجليزي(?:ة)?|انجليزي(?:ة)?)?|صوت\s*(?:إنجليزي|انجليزي|عربي)))"
)


def _clean_alias(value):
    text = unicodedata.normalize("NFKC", _text(value))
    text = _ARABIC_MARKS_RE.sub("", text)
    text = _NOISE_RE.sub(" ", text)
    text = "".join(character if character.isalnum() else " " for character in text)
    return re.sub(r"\s+", " ", text).strip().casefold()


def _release_year(value):
    year = extract_year(value)
    if not year:
        return 0
    # Far-future numbers in titles (for example Blade Runner 2049) are title
    # identity, not plausible current release metadata.
    return year if year <= datetime.now(timezone.utc).year + 5 else 0


def _remove_context_tokens(value):
    text = _text(value)
    without_pure = re.sub(r"(?i)\bpure\b", " ", text)
    if any(character.isalpha() for character in without_pure):
        text = without_pure
    return text


def _script_runs(value):
    """Split Arabic and all non-Arabic alphabetic scripts without ASCII bias."""

    runs = []
    current = []
    current_script = ""
    leading = []
    for character in value:
        if _ARABIC_RE.search(character):
            script = "arabic"
        elif character.isalpha():
            script = "latin"
        else:
            script = ""
        if script:
            if current_script and script != current_script:
                runs.append((current_script, "".join(current)))
                current = []
            elif not current_script and leading:
                current.extend(leading)
                leading = []
            current_script = script
            current.append(character)
        elif current_script:
            current.append(character)
        else:
            leading.append(character)
    if current_script:
        runs.append((current_script, "".join(current)))
    return runs


def provider_release_evidence(raw, explicit_year=0):
    explicit = _release_year(explicit_year)
    parenthesized = _PARENTHESIZED_YEAR_RE.findall(raw)
    parenthesized_year = _release_year(parenthesized[-1]) if parenthesized else 0
    if explicit and re.match(rf"^\s*{explicit}\b", raw):
        # The legacy projection sometimes treated a leading title number as the year.
        explicit = 0
    return explicit, parenthesized_year, parenthesized


def parse_provider_title(value, explicit_year=0, *, playlist_name=""):
    raw = unicodedata.normalize("NFKC", _text(value))
    explicit, parenthesized_year, parenthesized = provider_release_evidence(raw, explicit_year)
    year = explicit or parenthesized_year
    year_source = "explicit" if explicit else "parenthesized-title" if parenthesized_year else ""
    text = re.sub(r"\[[^\]]*\]", " ", raw)
    text = re.sub(r"\(\s*(?:19\d{2}|20\d{2}|21\d{2})\s*\)", " ", text)
    text = re.sub(r"\(\s*(?:مدبلج|مترجم|dubbed|subbed|translated)\s*\)", " ", text, flags=re.I)
    if year:
        # Remove the known release year wherever technical suffixes placed it,
        # but leave other year-bearing title tokens untouched.
        text = re.sub(rf"\b{year}\b", " ", text)
    if _RANKED_PLAYLIST_RE.search(_text(playlist_name)):
        text = re.sub(r"^\s*\d{1,3}\s*[-–—]\s*(?=\D)", "", text)
    text = _PROVIDER_SUFFIX_RE.sub(" ", text)
    text = _NOISE_RE.sub(" ", text)
    text = _remove_context_tokens(text)
    text = re.sub(r"\s+[-–—|]\s*$", " ", text)

    latin_aliases = []
    arabic_aliases = []
    runs = _script_runs(text)
    for script, run in runs:
        alias = _clean_alias(run)
        if not alias:
            continue
        if len(alias) == 1 and not any(character.isalpha() for character in run):
            continue
        if script == "arabic":
            arabic_aliases.append(alias)
        elif script == "latin":
            latin_aliases.append(alias)
    if not runs:
        alias = _clean_alias(text)
        if alias:
            (arabic_aliases if _ARABIC_RE.search(text) else latin_aliases).append(alias)
    latin_aliases = list(dict.fromkeys(latin_aliases))
    arabic_aliases = list(dict.fromkeys(arabic_aliases))
    aliases = list(dict.fromkeys([*latin_aliases, *arabic_aliases]))
    return {
        "raw_title": raw,
        "year": int(year or 0),
        "latin_aliases": latin_aliases,
        "arabic_aliases": arabic_aliases,
        "aliases": aliases,
        "primary_alias": (latin_aliases or arabic_aliases or [""])[0],
        "explicit_year": explicit,
        "title_years": [int(item) for item in parenthesized],
        "year_source": year_source,
        "parser_version": PARSER_VERSION,
    }


def clean_provider_title(value, explicit_year=0):
    return parse_provider_title(value, explicit_year).get("primary_alias", "")


def combine_provider_title_evidence(raw_title, raw_year=0, detail_title="", detail_year=0, *, playlist_name=""):
    """Combine distinct raw/detail facts while preferring an explicit raw year."""

    raw = parse_provider_title(raw_title, raw_year, playlist_name=playlist_name)
    detail = parse_provider_title(detail_title, detail_year, playlist_name=playlist_name)
    year = (
        int(raw.get("year") or 0)
        or int(detail.get("year") or 0)
    )
    latin_aliases = list(dict.fromkeys([*(raw.get("latin_aliases") or []), *(detail.get("latin_aliases") or [])]))
    arabic_aliases = list(dict.fromkeys([*(raw.get("arabic_aliases") or []), *(detail.get("arabic_aliases") or [])]))
    return {
        "raw_title": raw.get("raw_title") or _text(raw_title),
        "detail_title": detail.get("raw_title") or _text(detail_title),
        "year": year,
        "year_source": (
            "raw-explicit" if raw.get("explicit_year")
            else "raw-title" if raw.get("year")
            else "detail-explicit" if detail.get("explicit_year")
            else "detail-title" if detail.get("year")
            else ""
        ),
        "latin_aliases": latin_aliases,
        "arabic_aliases": arabic_aliases,
        "aliases": list(dict.fromkeys([*latin_aliases, *arabic_aliases])),
        "primary_alias": (latin_aliases or arabic_aliases or [""])[0],
        "raw_evidence": raw,
        "detail_evidence": detail,
        "parser_version": PARSER_VERSION,
    }


def candidate_title_aliases(candidate):
    alternative_titles = candidate.get("alternative_titles")
    alternative_rows = (
        alternative_titles.get("titles", [])
        if isinstance(alternative_titles, dict)
        else []
    )
    values = [candidate.get("title"), candidate.get("original_title")]
    localized_titles = candidate.get("localized_titles") or []
    if isinstance(localized_titles, dict):
        localized_titles = list(localized_titles.values())
    values.extend(localized_titles if isinstance(localized_titles, list) else [])
    values.extend(
        row.get("title")
        for row in alternative_rows
        if isinstance(row, dict)
    )
    return list(dict.fromkeys(
        name for name in (clean_provider_title(value) for value in values) if name
    ))


def interpreted_title_evidence(provider, interpretation):
    """Use a structured bulk interpretation without discarding provider facts."""
    interpreted_year = extract_year(interpretation.get("year"))
    titles = [interpretation.get("title"), *(interpretation.get("aliases") or [])]
    hints = [parse_provider_title(title, interpreted_year) for title in titles if title]
    latin = list(dict.fromkeys([alias for hint in hints for alias in hint['latin_aliases']] + provider['latin_aliases']))
    arabic = list(dict.fromkeys([alias for hint in hints for alias in hint['arabic_aliases']] + provider['arabic_aliases']))
    aliases = list(dict.fromkeys([alias for hint in hints for alias in hint['aliases']] + provider['aliases']))
    return {**provider, 'aliases': aliases, 'latin_aliases': latin, 'arabic_aliases': arabic,
            'primary_alias': next(iter(aliases), ''), 'year': interpreted_year or provider['year'],
            'bulk_identity': {'provider_aliases': provider['aliases'], 'provider_year': provider['year'],
                              'provider_titles': [provider.get('raw_title') or '', provider.get('detail_title') or ''],
                              'interpreted_year': interpreted_year,
                              'interpreted_aliases': list(dict.fromkeys(alias for hint in hints for alias in hint['aliases']))}}


def _title_numbers(title):
    return {_ROMAN_PARTS.get(token, token) for token in title.split() if token.isdecimal() or token in _ROMAN_PARTS}


_ROMAN_PARTS = {'ii': '2', 'iii': '3', 'iv': '4', 'v': '5', 'vi': '6',
                'vii': '7', 'viii': '8', 'ix': '9', 'x': '10'}


def _recovery_title(value):
    text = unicodedata.normalize('NFKD', value.translate(str.maketrans('أإآى', 'اااي')))
    text = ''.join(char for char in text if not unicodedata.combining(char))
    tokens = _clean_alias(re.sub("['’]", '', text)).split()
    if tokens and tokens[-1] in {'2d', '3d'}:
        tokens.pop()
    return ' '.join(
        _ROMAN_PARTS.get(word, word) if len(tokens) > 1 and
        (len(word) > 1 or (index and tokens[index - 1] in {'part', 'chapter', 'episode'})) else word
        for index, word in enumerate(tokens) if word != 'the')


def _recovery_names(candidate):
    return {_recovery_title(name) for name in [candidate['title'], candidate['original_title'], *candidate['aliases']]
            if name} - {''}


def recovery_candidate_facts(movie, *, localized=True):
    """Extract only film evidence used by the recovery verifier."""
    if not localized:
        movie = {key: value for key, value in movie.items() if key != 'localized_titles'}
    credits = movie.get('credits') or {}
    return {
        'candidate_id': movie['id'], 'title': movie.get('title') or '',
        'original_title': movie.get('original_title') or '',
        'release_date': movie.get('release_date') or '',
        'other_release_years': sorted({year for group in (movie.get('release_dates') or {}).get('results', [])
                                       for row in group.get('release_dates', [])
                                       if (year := extract_year(row.get('release_date')))}),
        'runtime_minutes': movie.get('runtime') or 0, 'original_language': movie.get('original_language') or '',
        'aliases': candidate_title_aliases(movie),
        'directors': [row['name'] for row in credits.get('crew', []) if row.get('job') == 'Director' and row.get('name')],
        'cast': [row['name'] for row in (credits.get('cast') or [])[:8] if row.get('name')],
        'overview': movie.get('overview') or '',
        **{key: movie[key] for key in ('collection_first_movie_id', 'collection_part_number')
           if localized and movie.get(key)},
    }


def _numbered_collection_subtitle(aliases, candidate):
    parts = set()
    for official in (candidate.get('title') or '', candidate.get('original_title') or ''):
        if ':' not in official:
            continue
        series, subtitle = map(_recovery_title, official.split(':', 1))
        if not series or len(subtitle.split()) < 2 or _title_numbers(series + ' ' + subtitle):
            continue
        for alias in aliases:
            for number in _title_numbers(alias):
                if not number.isascii() or len(number) > 2:
                    continue
                if int(number) >= 2 and alias in (f'{series} {number} {subtitle}', f'{series} part {number} {subtitle}'):
                    parts.add(int(number))
    return next(iter(parts)) if len(parts) == 1 else None


def _recovery_title_relation(aliases, names, candidate):
    source_numbers = set().union(*map(_title_numbers, aliases))
    canonical_numbers = [_title_numbers(_recovery_title(candidate[key])) for key in ('title', 'original_title')
                         if candidate[key]]
    canonical_numbers = [numbers for numbers in canonical_numbers if numbers] or [set()]
    for alias in aliases:
        if alias in names and _title_numbers(alias) == source_numbers and source_numbers in canonical_numbers:
            return 'title'
    part = _numbered_collection_subtitle(aliases, candidate)
    if part and source_numbers == {str(part)} and part == candidate.get('collection_part_number'):
        return 'collection_subtitle'
    for alias in aliases:
        if (source_numbers == {'1'} and _title_numbers(alias) == {'1'} and alias.endswith(' 1') and
                alias[:-2] in names and not any(canonical_numbers) and
                candidate.get('collection_first_movie_id') == candidate['candidate_id']):
            return 'first_installment'
        # Match the entire official franchise title and distinctive subtitle.
        # A missing numeral is only safe when the canonical subtitle identifies the part.
        for official in (candidate['title'], candidate['original_title']):
            if ':' not in official:
                continue
            series, subtitle = map(_recovery_title, official.split(':', 1))
            numbers = _title_numbers(series)
            if (len(subtitle.split()) >= 2 and len(numbers) == 1 and not source_numbers and
                    alias == ' '.join([*(word for word in series.split() if word not in numbers), subtitle])):
                return 'official_subtitle'
        if (len(alias.split()) >= 2 and not source_numbers and not any(canonical_numbers) and
                any(name.startswith(alias + ' ') and not _title_numbers(name) and
                    ':' not in candidate['title'] for name in names)):
            return 'shortened_title'
    return ''


def _recovery_runtime(value):
    pieces = _text(value).split(':')
    if len(pieces) == 3 and all(part.isdecimal() for part in pieces):
        hours, minutes, seconds = map(int, pieces)
        if minutes < 60 and seconds < 60:
            return hours * 60 + minutes + seconds / 60
    return 0


def _recovery_credit(value):
    # Name order varies between providers (for example Huang Yi / Yi Huang).
    return tuple(sorted(_recovery_title(value).split()))


def _plot_overlap(left, right):
    def words(value):
        generic = {'about', 'after', 'before', 'could', 'first', 'friends', 'group', 'journey', 'story',
                   'their', 'there', 'these', 'those', 'through', 'together', 'where', 'which', 'world', 'young'}
        return {word for word in _recovery_title(value).split() if len(word) >= 5 and not word.isdecimal()} - generic
    source, target = words(left), words(right)
    return len(source & target) >= max(4, len(source | target) * .18)


def verify_recovery_candidate(provider, candidates, candidate_id, *, search_limited=False, require_support=True):
    """Check a TMDB nomination against listing and detail facts, without model confidence."""
    original = parse_provider_title(provider['title'], provider['year'], playlist_name=provider['playlist'])
    detail = parse_provider_title(provider['detail_title'], provider['detail_year'], playlist_name=provider['playlist'])
    raw_names = {_recovery_title(alias) for alias in original['aliases']} - {''}
    detail_names = {_recovery_title(alias) for alias in detail['aliases']} - {''}
    runtime = _recovery_runtime(provider['duration'])
    cast = {_recovery_credit(name) for name in provider['cast'].split(',') if name.strip()}
    directors = {_recovery_credit(name) for name in provider['director'].split(',') if name.strip()}

    def facts(candidate):
        names = _recovery_names(candidate)
        minutes = candidate['runtime_minutes']
        difference = round(abs(minutes - runtime), 3) if minutes and runtime else None
        return {'candidate_id': candidate['candidate_id'],
                'title': _recovery_title_relation(raw_names, names, candidate),
                'detail_title': _recovery_title_relation(detail_names, names, candidate),
                'primary_year': extract_year(candidate['release_date']),
                'other_years': [extract_year(year) for year in candidate['other_release_years']],
                'duration_difference': difference,
                'runtime_matches': difference is not None and difference <= max(3, minutes * .05),
                'cast_matches': len(cast & {_recovery_credit(name) for name in candidate['cast']}),
                'has_cast': bool(candidate['cast']),
                'director_matches': bool(directors & {_recovery_credit(name) for name in candidate['directors']}),
                'has_director': bool(candidate['directors']),
                'plot_matches': _plot_overlap(provider['plot'], candidate['overview'])}

    evaluated = [facts(candidate) for candidate in candidates]
    chosen = next((row for row in evaluated if row['candidate_id'] == candidate_id), None)
    candidate = next((row for row in candidates if row['candidate_id'] == candidate_id), None)

    def result(reason=''):
        return {'verified': not reason, 'reason': reason, 'candidate': chosen,
                'provider_year': original['year'], 'detail_year': detail['year'],
                'rivals': [row for row in evaluated if row is not chosen]}

    if not chosen:
        return result('recovery_no_candidate')
    if search_limited:
        return result('recovery_search_limited')
    if original['year'] and (not chosen['primary_year'] or abs(original['year'] - chosen['primary_year']) > 1):
        return result('recovery_primary_year_conflict')
    if detail['year'] and chosen['primary_year'] and abs(detail['year'] - chosen['primary_year']) > 1:
        return result('recovery_conflicting_provider_metadata')
    if not chosen['title']:
        return result('recovery_title_or_installment_conflict')
    if detail_names and not chosen['detail_title'] and not detail_names & raw_names:
        return result('recovery_conflicting_provider_metadata')
    if chosen['duration_difference'] is not None and not chosen['runtime_matches']:
        return result('recovery_runtime_conflict')
    if ((cast and candidate['cast'] and chosen['cast_matches'] == 0 and len(cast) >= 2) or
            (directors and candidate['directors'] and not chosen['director_matches'] and chosen['cast_matches'] < 2)):
        return result('recovery_conflicting_provider_metadata')
    runtime_distinguished = False
    for rival in evaluated:
        if rival is chosen:
            continue
        if ((rival['cast_matches'] >= chosen['cast_matches'] + 2 and rival['cast_matches'] >= 2) or
                (rival['plot_matches'] and not chosen['plot_matches'] and
                 (rival['detail_title'] or rival['director_matches'] or rival['cast_matches'] >= 2))):
            return result('recovery_conflicting_provider_metadata')
        years = [year for year in [rival['primary_year'], *rival['other_years']] if year]
        year_rules_out = original['year'] and years and all(abs(original['year'] - year) > 1 for year in years)
        runtime_rules_out = (chosen['runtime_matches'] and rival['duration_difference'] is not None
                             and not rival['runtime_matches'])
        credits_rule_out = (chosen['director_matches'] and chosen['cast_matches'] >= 2 and
                            rival['has_director'] and not rival['director_matches'] and rival['cast_matches'] == 0)
        if rival['title'] and not year_rules_out and runtime_rules_out:
            runtime_distinguished = True
        if rival['title'] and not year_rules_out and not runtime_rules_out and not credits_rule_out:
            return result('recovery_competing_identities')

    credit_support = chosen['cast_matches'] >= 2 or (chosen['director_matches'] and chosen['cast_matches'] >= 1)
    if not original['year']:
        # Shared event year can corroborate a distinctive bilingual title even
        # when the provider and TMDB descriptions are in different languages.
        event_years = set(_YEAR_RE.findall(provider['plot'])) & set(_YEAR_RE.findall(candidate['overview']))
        distinctive = {name for name in raw_names & _recovery_names(candidate) if len(name.split()) >= 3}
        bilingual = len(distinctive) >= 2 and any(_ARABIC_RE.search(name) for name in distinctive)
        if not (chosen['runtime_matches'] and (chosen['plot_matches'] or (event_years and bilingual))):
            return result('recovery_insufficient_identity_evidence')
    elif (require_support or chosen['title'] == 'shortened_title') and not (chosen['runtime_matches'] and
            (credit_support or chosen['plot_matches'] or
             (chosen['title'] == 'title' and chosen['duration_difference'] <= 1 and runtime_distinguished
              and candidate['overview'] and provider['plot']))):
        return result('recovery_insufficient_identity_evidence')
    return result()


def _supported_cleaned_title(source, name):
    # Harakat are already removed by the parser. Normalize common Arabic letter
    # variants for comparison, without changing displayed/provider titles.
    translation = str.maketrans({'أ': 'ا', 'إ': 'ا', 'آ': 'ا', 'ى': 'ي'})
    source, name = source.translate(translation), name.translate(translation)
    if source == name:
        return bool(name)
    source = re.sub(r'^(?:فيلم|movie|film)\s+', '', source)
    def comparable(value):
        value = re.sub(r'\s+(?:2d|3d)$', '', value).strip()
        return ' '.join(token for token in value.split() if token != 'the')
    source, name = comparable(source), comparable(name)
    return bool(name and (source == name or (len(source.split()) == len(name.split()) and
                          SequenceMatcher(None, source, name).ratio() >= .9)))


def _bulk_year_conflict(evidence, candidate):
    years = [year for year in (evidence['provider_year'], evidence['interpreted_year']) if year]
    actual_year = _candidate_year(candidate)
    return ((len(years) == 2 and abs(years[0] - years[1]) > 1) or
            bool(actual_year and any(abs(year - actual_year) > 1 for year in years)))


def _first_film_label(evidence, names):
    numbers = set().union(*(_title_numbers(alias) for alias in evidence['provider_aliases']))
    return numbers == {'1'} and any(
        source.endswith(' 1') and _supported_cleaned_title(source[:-2], name)
        for source in evidence['provider_aliases'] for name in names if not _title_numbers(name))


def _bulk_number_conflict(evidence, candidate, names):
    numbers = set().union(*(_title_numbers(alias) for alias in evidence['provider_aliases']))
    first = candidate.get('collection_first_movie_id') == candidate.get('id') and _first_film_label(evidence, names)
    return not first and not any(_title_numbers(name) == numbers for name in names)


def _bulk_identity_conflict(parsed, candidate):
    evidence = parsed.get('bulk_identity')
    if not evidence:
        return ''
    if candidate.get('bulk_search_limited'):
        return BULK_SEARCH_LIMIT_REASON
    if _bulk_year_conflict(evidence, candidate):
        return 'Provider, interpreted and TMDB release years conflict.'
    names = candidate_title_aliases(candidate)
    if _bulk_number_conflict(evidence, candidate, names):
        return 'Meaningful title or sequel numbers conflict.'
    if not (any(_supported_cleaned_title(source, name)
                for source in evidence['provider_aliases'] for name in names) or
            (candidate.get('collection_first_movie_id') == candidate.get('id') and _first_film_label(evidence, names)) or
            _supported_title_segments(evidence, candidate, names)):
        return 'TMDB titles do not corroborate the provider identity.'
    return ''


def _supported_title_segments(evidence, candidate, names):
    """A separator is not permission to discard a sequel subtitle.

    Each alternate title needs a catalogue alias, or a leading collection label
    must identify an actor, director or character credited in this same movie.
    """
    credits = candidate.get('credits') or {}
    cast = credits.get('cast') or []
    credited = [row.get('name') for row in cast]
    credited.extend(role for row in cast for role in (row.get('character') or '').split('/'))
    credited.extend(row.get('name') for row in credits.get('crew', []) if row.get('job') == 'Director')
    credited = [clean_provider_title(value.split('(')[0]) for value in credited if value]
    for raw in evidence['provider_titles']:
        segments = re.split(r'\s+[-–—|/]\s+', raw)
        if len(segments) < 2:
            continue
        aliases = [parse_provider_title(part, evidence['provider_year'])['aliases'] for part in segments]
        supported = [any(_supported_cleaned_title(alias, name) for alias in group for name in names)
                     for group in aliases]
        if all(supported):
            return True
        if supported[-1] and all(any(label == credit or (len(credit.split()) > 1 and label.startswith(credit + ' '))
                                    for label in group for credit in credited if credit)
                                 for group in aliases[:-1]):
            return True
    return False


def score_candidate(provider_title, provider_year, candidate):
    parsed = provider_title if isinstance(provider_title, dict) else parse_provider_title(provider_title, provider_year)
    targets = parsed.get("aliases") or [parsed.get("primary_alias")]
    targets = [target for target in targets if target]
    names = candidate_title_aliases(candidate)
    if not targets or not names:
        return 0.0
    best_target, best_name, similarity = max(
        (
            (target, name, SequenceMatcher(None, target, name).ratio())
            for target in targets
            for name in names
        ),
        key=lambda row: (row[2], len(row[0]), len(row[1])),
    )
    score = similarity * 80.0
    if any(target in names for target in targets):
        score = 85.0
    expected_year = _release_year(provider_year) or int(parsed.get("year") or 0)
    candidate_year = _year(candidate.get("release_date") or candidate.get("year"))
    if expected_year and candidate_year:
        difference = abs(expected_year - candidate_year)
        if difference == 0:
            score += 15.0
        elif difference == 1:
            # The structured bulk policy permits one release-year difference;
            # original and interpreted years are both checked before acceptance.
            score += 15.0 if parsed.get('bulk_identity') else 5.0
        else:
            score -= min(20.0, difference * 4.0)
    elif not expected_year:
        score += 5.0
    # Shared franchise prefixes are weak evidence; missing distinctive sequel
    # tokens are a strong negative signal.
    stop = {"the", "and", "movie", "film", "part", "episode", "a", "an", "of", "to", "in"}
    target_tokens = set(best_target.split()) - stop
    candidate_tokens = set(best_name.split()) - stop
    missing = {token for token in target_tokens - candidate_tokens if len(token) >= 5}
    conflicting = {token for token in candidate_tokens - target_tokens if len(token) >= 6}
    if missing and candidate_tokens:
        score -= min(24.0, len(missing) * 8.0)
    if missing and conflicting:
        score -= min(12.0, len(conflicting) * 4.0)
    return round(max(0.0, min(100.0, score)), 3)


def _candidate_year(candidate):
    return _release_year(candidate.get("release_date") or candidate.get("year"))


def _candidate_facts(parsed, provider_year, candidate):
    targets = [target for target in (parsed.get("aliases") or []) if target]
    names = candidate_title_aliases(candidate)
    exact_title = bool(set(targets) & set(names))
    expected_year = _release_year(provider_year) or int(parsed.get("year") or 0)
    actual_year = _candidate_year(candidate)
    year_difference = abs(expected_year - actual_year) if expected_year and actual_year else 0
    corroborations = set(targets).intersection(candidate.get("search_aliases") or [])
    if candidate.get("provider_id_corroborated"):
        corroborations.add("provider-id")
    if candidate.get("sibling_corroborated"):
        corroborations.add("sibling")
    return {
        "exact_title": exact_title,
        "expected_year": expected_year,
        "candidate_year": actual_year,
        "year_difference": year_difference,
        "material_year_conflict": bool(expected_year and actual_year and year_difference > 1),
        "corroboration_count": len(corroborations),
        "identity_conflict": _bulk_identity_conflict(parsed, candidate),
    }


def _bulk_rival_score(parsed, provider_year, candidate):
    """A regional release can keep a rival plausible, never confirm it alone."""
    evidence = parsed['bulk_identity']
    names = candidate_title_aliases(candidate)
    if (_bulk_number_conflict(evidence, candidate, names) and not _first_film_label(evidence, names)):
        return 0
    variants = [candidate]
    for group in (candidate.get('release_dates') or {}).get('results', []):
        for release in group.get('release_dates', []):
            if extract_year(release.get('release_date')):
                variants.append({**candidate, 'release_date': release['release_date']})
    return max((score_candidate(parsed, provider_year, variant) for variant in variants
                if not _bulk_year_conflict(evidence, variant)), default=0)


def choose_automatic_match(provider_title, provider_year, candidates):
    parsed = provider_title if isinstance(provider_title, dict) else parse_provider_title(provider_title, provider_year)
    scored = sorted(
        [
            {**candidate, "match_score": score_candidate(parsed, provider_year, candidate)}
            for candidate in candidates or []
            if isinstance(candidate, dict) and candidate.get("id")
        ],
        key=lambda row: (-row["match_score"], int(row.get("id") or 0)),
    )
    if not scored:
        return {"state": "unmatched", "accepted": None, "candidates": []}
    evidence = parsed.get('bulk_identity')
    if evidence:
        for row in scored:
            row['identity_conflict'] = _bulk_identity_conflict(parsed, row)
            row['rival_score'] = _bulk_rival_score(parsed, provider_year, row)
        # Eligibility precedes score/ID ordering. Keep rejected candidates for
        # diagnostics, but do not let an impossible year or sequel veto a match.
        scored.sort(key=lambda row: bool(row['identity_conflict']))
    best = scored[0]
    rival_score = max((row['rival_score'] if evidence else row['match_score']
                       for row in scored[1:]), default=0)
    facts = _candidate_facts(parsed, provider_year, best)
    credible_rival = bool(
        rival_score >= 78.0
        and best["match_score"] - rival_score < 8.0
    )
    independently_strong = bool(
        facts["exact_title"]
        and not facts["material_year_conflict"]
        and (not facts["expected_year"] or not facts["candidate_year"] or facts["year_difference"] <= 1)
    )
    corroborated = facts["corroboration_count"] >= 2 and not facts["material_year_conflict"]
    if best["match_score"] >= 94.0 and not credible_rival and not facts['identity_conflict'] and (independently_strong or corroborated):
        return {"state": "matched-auto", "accepted": best, "candidates": scored[:8]}
    if facts['identity_conflict']:
        return {"state": "ambiguous", "accepted": None, "candidates": scored[:8],
                "reason": facts['identity_conflict']}
    if evidence and credible_rival:
        return {'state': 'ambiguous', 'accepted': None, 'candidates': scored[:8],
                'reason': 'Competing TMDB identities need additional evidence.'}
    if best["match_score"] >= 78.0 or facts["material_year_conflict"]:
        decision = {"state": "ambiguous", "accepted": None, "candidates": scored[:8]}
        if evidence:
            decision['reason'] = 'TMDB title/year evidence is below the automatic match threshold.'
        return decision
    return {"state": "unmatched", "accepted": None, "candidates": scored[:8]}


def provider_id_matches(provider_title, provider_year, movie):
    parsed = provider_title if isinstance(provider_title, dict) else parse_provider_title(provider_title, provider_year)
    score = score_candidate(parsed, provider_year, movie)
    facts = _candidate_facts(parsed, provider_year, movie)
    expected_year = facts["expected_year"]
    actual_year = facts["candidate_year"]
    year_ok = not expected_year or not actual_year or abs(expected_year - actual_year) <= 1
    # Provider IDs corroborate an identity; they cannot rescue a fuzzy or
    # conflicting title by themselves.
    return score >= 94.0 and facts["exact_title"] and year_ok, score


def _merge_candidate(merged, row, alias, phase):
    tmdb_id = int(row["id"])
    current = merged.get(tmdb_id, {})
    aliases = list(dict.fromkeys([*(current.get("search_aliases") or []), alias]))
    phases = list(dict.fromkeys([*(current.get("search_phases") or []), phase]))
    merged[tmdb_id] = {
        **current,
        **row,
        "search_alias": current.get("search_alias") or alias,
        "search_phase": current.get("search_phase") or phase,
        "search_aliases": aliases,
        "search_phases": phases,
    }


def _released_collection_parts(client, collection_id):
    if not collection_id or not hasattr(client, 'collection'):
        return []
    parts = client.collection(collection_id).get('parts') or []
    if len(parts) >= 2 and all(part.get('release_date') for part in parts):
        return sorted(parts, key=lambda part: part['release_date'])
    return []


def collection_first_movie_id(client, collection_id):
    parts = _released_collection_parts(client, collection_id)
    if parts and parts[0]['release_date'] < parts[1]['release_date']:
        return parts[0]['id']
    return None


def collection_part_number(client, collection_id, movie_id):
    parts = _released_collection_parts(client, collection_id)
    if len({part['release_date'] for part in parts}) != len(parts):
        return None
    return next((index for index, part in enumerate(parts, 1) if part.get('id') == movie_id), None)


def _hydrate_candidates(client, parsed, merged, *, strict_bounds=False, missing_movie_ids=None):
    ordered = sorted(
        merged.values(),
        key=lambda row: (-score_candidate(parsed, parsed.get("year"), row), int(row.get("id") or 0)),
    )[:MAX_HYDRATED_CANDIDATES]
    wants_localized = bool(parsed.get("arabic_aliases"))
    localized_remaining = MAX_LOCALIZED_HYDRATIONS
    for row in ordered:
        if row.get("candidate_hydrated"):
            continue
        movie_id = int(row["id"])
        try:
            detail = client.movie(movie_id)
        except IPTVTMDBError as error:
            if missing_movie_ids is None or error.status != 404:
                raise
            missing_movie_ids.add(movie_id)
            del merged[movie_id]
            continue
        except (KeyError, TypeError, ValueError, AttributeError):
            detail = {}
        if isinstance(detail, dict):
            if strict_bounds and detail and detail.get('id') != row['id']:
                raise IPTVTMDBError('TMDB returned a different film identity.')
            provenance = {
                key: row.get(key)
                for key in ("search_alias", "search_phase", "search_aliases", "search_phases")
            }
            row.update(detail)
            row.update(provenance)
        row["candidate_hydrated"] = bool(detail)
        if wants_localized and localized_remaining > 0:
            try:
                localized = client.movie(movie_id, language="ar-SA")
            except IPTVTMDBError as error:
                if missing_movie_ids is None or error.status != 404:
                    raise
                localized = {}
            except (KeyError, TypeError, ValueError, AttributeError):
                localized = {}
            if isinstance(localized, dict):
                row["localized_titles"] = list(dict.fromkeys(
                    _text(value)
                    for value in (localized.get("title"), localized.get("original_title"))
                    if _text(value)
                ))
            localized_remaining -= 1
        evidence = parsed.get('bulk_identity')
        collection_id = (row.get('belongs_to_collection') or {}).get('id')
        if evidence and collection_id and _first_film_label(evidence, candidate_title_aliases(row)):
            first = collection_first_movie_id(client, collection_id)
            if first:
                row['collection_first_movie_id'] = first
        if strict_bounds and collection_id:
            original = parsed.get('raw_evidence') or parsed
            aliases = {_recovery_title(alias) for alias in original['aliases']}
            expected_part = _numbered_collection_subtitle(aliases, row)
            if expected_part and collection_part_number(client, collection_id, row['id']) == expected_part:
                row['collection_part_number'] = expected_part


def recovery_rival_plausible(parsed, candidate):
    # Search results may omit regional dates. A title-compatible result outside
    # the hydration budget remains a possible rival even with a different year.
    return score_candidate({**parsed, 'year': 0}, 0, candidate) >= 78


def _focused_bulk_search(client, parsed, aliases, year):
    merged, attempts = {}, []
    limited = len(aliases) > MAX_QUERY_VARIANTS
    aliases = aliases[:MAX_QUERY_VARIANTS]
    # Cap the entire search as well as each query. Fuzzy or generic titles can
    # otherwise turn several aliases into dozens of additional requests.
    remaining_pages = MAX_QUERY_VARIANTS * 4 + MAX_BULK_SEARCH_PAGES
    for use_year in (year, year - 1, year + 1, 0):
        for alias in aliases:
            phase = 'primary-year' if use_year else 'no-year'
            for page in range(1, MAX_BULK_SEARCH_PAGES + 1):
                if not remaining_pages:
                    limited = True
                    break
                remaining_pages -= 1
                rows, pages = client.search_movie_page(alias, page, primary_year=use_year)
                attempts.append({'phase': phase, 'alias': alias, 'year': use_year,
                                 'page': page, 'results': len(rows), 'total_pages': pages})
                for row in rows:
                    if row.get('id') and recovery_rival_plausible(parsed, row):
                        if len(merged) >= MAX_MERGED_CANDIDATES and row['id'] not in merged:
                            limited = True
                            continue
                        _merge_candidate(merged, row, alias, phase)
                if page >= pages:
                    break
            else:
                limited = True
    _hydrate_candidates(client, parsed, merged, strict_bounds=True)
    if any(not row.get('candidate_hydrated') and recovery_rival_plausible(parsed, row)
           for row in merged.values()):
        limited = True
    if limited:
        return [{**candidate, 'bulk_search_limited': True} for candidate in merged.values()], attempts
    return list(merged.values()), attempts


def bounded_search_candidates(client, parsed, *, search_aliases=None, strict_bounds=False,
                              skip_missing_details=False, focused=False):
    parsed = parsed if isinstance(parsed, dict) else parse_provider_title(parsed)
    aliases = search_aliases if search_aliases is not None else (parsed.get("latin_aliases") or []) + (parsed.get("arabic_aliases") or [])
    aliases = list(dict.fromkeys(alias for alias in aliases if alias))
    primary_year = (parsed.get('bulk_identity') or {}).get('provider_year')
    if focused and primary_year:
        return _focused_bulk_search(client, parsed, aliases, primary_year)
    limited = strict_bounds and len(aliases) > MAX_QUERY_VARIANTS
    aliases = aliases[:MAX_QUERY_VARIANTS]
    year = int(parsed.get("year") or 0)
    merged = {}
    missing_movie_ids = set() if skip_missing_details else None
    attempts = []
    phases = (("year", year), ("no-year", 0)) if year else (("no-year", 0),)
    for phase, use_year in phases:
        for alias in aliases:
            rows = client.search_movies(alias, use_year)
            if strict_bounds and (len(rows) >= 20 or any(
                    isinstance(row, dict) and row.get('id') not in merged and recovery_rival_plausible(parsed, row)
                    for row in rows[MAX_RESULTS_PER_ALIAS:])):
                limited = True
            attempts.append({"phase": phase, "alias": alias, "year": int(use_year or 0), "results": len(rows)})
            for row in rows[:MAX_RESULTS_PER_ALIAS]:
                if not isinstance(row, dict) or not row.get("id"):
                    continue
                if missing_movie_ids and int(row["id"]) in missing_movie_ids:
                    continue
                _merge_candidate(merged, row, alias, phase)
                if len(merged) >= MAX_MERGED_CANDIDATES:
                    break
            if len(merged) >= MAX_MERGED_CANDIDATES:
                break
        _hydrate_candidates(client, parsed, merged, strict_bounds=strict_bounds, missing_movie_ids=missing_movie_ids)
        decision = choose_automatic_match(parsed, year, list(merged.values()))
        # A nearby remake can be absent from the exact-year response. Bulk
        # interpretation must inspect the unfiltered search before confirming.
        if (decision["accepted"] and not parsed.get('bulk_identity')) or not year or len(merged) >= MAX_MERGED_CANDIDATES:
            break
    if limited or (parsed.get('bulk_identity') and len(merged) >= MAX_MERGED_CANDIDATES):
        for candidate in merged.values():
            candidate['bulk_search_limited'] = True
    return list(merged.values()), attempts


def _image(path, size):
    path = _text(path)
    if not path:
        return ""
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return f"{TMDB_IMAGE_ROOT}/{size}/{path.lstrip('/')}"


def normalize_tmdb_movie(payload):
    payload = payload if isinstance(payload, dict) else {}
    credits = payload.get("credits") if isinstance(payload.get("credits"), dict) else {}
    keywords_payload = payload.get("keywords") if isinstance(payload.get("keywords"), dict) else {}
    release_payload = payload.get("release_dates") if isinstance(payload.get("release_dates"), dict) else {}
    crew = credits.get("crew") if isinstance(credits.get("crew"), list) else []
    cast = credits.get("cast") if isinstance(credits.get("cast"), list) else []
    directors = [row for row in crew if isinstance(row, dict) and row.get("job") == "Director"]
    writers = [
        row for row in crew
        if isinstance(row, dict) and row.get("job") in {"Writer", "Screenplay", "Story"}
    ]
    certification = ""
    release_groups = release_payload.get("results") if isinstance(release_payload.get("results"), list) else []
    ordered_groups = sorted(
        [row for row in release_groups if isinstance(row, dict)],
        key=lambda row: (0 if row.get("iso_3166_1") == "US" else 1, _text(row.get("iso_3166_1"))),
    )
    for group in ordered_groups:
        releases = group.get("release_dates") if isinstance(group.get("release_dates"), list) else []
        certification = next((_text(row.get("certification")) for row in releases if isinstance(row, dict) and _text(row.get("certification"))), "")
        if certification:
            break
    collection = payload.get("belongs_to_collection") if isinstance(payload.get("belongs_to_collection"), dict) else {}
    return {
        "tmdb_id": int(payload.get("id") or 0),
        "title": _text(payload.get("title")) or _text(payload.get("original_title")) or "Untitled",
        "original_title": _text(payload.get("original_title")),
        "plot": _text(payload.get("overview")),
        "poster_url": _image(payload.get("poster_path"), "w500"),
        "backdrop_url": _image(payload.get("backdrop_path"), "w1280"),
        "genres": [
            {"id": int(row.get("id") or 0), "name": _text(row.get("name"))}
            for row in payload.get("genres", []) if isinstance(row, dict) and row.get("id") and _text(row.get("name"))
        ],
        "rating": float(payload.get("vote_average") or 0),
        "vote_count": int(payload.get("vote_count") or 0),
        "release_date": _text(payload.get("release_date")),
        "year": _year(payload.get("release_date")),
        "runtime": int(payload.get("runtime") or 0),
        "original_language": _text(payload.get("original_language")),
        "imdb_id": _text(payload.get("imdb_id")) if re.fullmatch(r"tt[0-9]{5,12}", _text(payload.get("imdb_id"))) else "",
        "languages": [
            {"code": _text(row.get("iso_639_1")), "name": _text(row.get("english_name") or row.get("name"))}
            for row in payload.get("spoken_languages", []) if isinstance(row, dict) and _text(row.get("iso_639_1"))
        ],
        "countries": [
            {"code": _text(row.get("iso_3166_1")), "name": _text(row.get("name"))}
            for row in payload.get("production_countries", []) if isinstance(row, dict) and _text(row.get("iso_3166_1"))
        ],
        "certification": certification,
        "directors": directors,
        "writers": writers,
        "cast": cast[:40],
        "collection": {
            "id": int(collection.get("id") or 0),
            "name": _text(collection.get("name")),
        } if collection.get("id") else {},
        "keywords": [
            {"id": int(row.get("id") or 0), "name": _text(row.get("name"))}
            for row in keywords_payload.get("keywords", []) if isinstance(row, dict) and row.get("id") and _text(row.get("name"))
        ],
        "raw": payload,
    }


class IPTVTMDBClient:
    def __init__(self, settings, *, timeout=15, open_url=None, api_root=TMDB_API_ROOT, min_request_interval=0.25):
        self.settings = settings
        self.timeout = max(1, int(timeout or 15))
        self.open_url = open_url or urllib.request.urlopen
        self.api_root = str(api_root).rstrip("/")
        self.min_request_interval = max(0.0, float(min_request_interval or 0))
        self._request_lock = threading.Lock()
        self._last_request_at = 0.0

    def _pace_request(self):
        with self._request_lock:
            wait_for = self.min_request_interval - (time.monotonic() - self._last_request_at)
            if wait_for > 0:
                time.sleep(wait_for)
            self._last_request_at = time.monotonic()

    def _request(self, path, params=None):
        credential_type, credential = self.settings.credential()
        query = dict(params or {})
        headers = {"Accept": "application/json", "User-Agent": "Cinema-Paradiso-IPTV/1"}
        if credential_type == "bearer":
            headers["Authorization"] = f"Bearer {credential}"
        else:
            query["api_key"] = credential
        encoded = urllib.parse.urlencode(query)
        url = f"{self.api_root}/{str(path).lstrip('/')}"
        if encoded:
            url = f"{url}?{encoded}"
        request = urllib.request.Request(url, headers=headers)
        try:
            self._pace_request()
            response = self.open_url(request, timeout=self.timeout)
            with response:
                body = response.read(8 * 1024 * 1024)
            payload = json.loads(body.decode("utf-8"))
            if not isinstance(payload, dict):
                raise IPTVTMDBError("IPTV TMDB returned an invalid response", retryable=True)
            return payload
        except urllib.error.HTTPError as error:
            status = int(error.code or 0)
            retry_after = error.headers.get("Retry-After", "0") if error.headers else "0"
            try:
                retry_after = int(float(retry_after or 0))
            except (TypeError, ValueError):
                retry_after = 0
            if status == 401:
                raise IPTVTMDBError("IPTV TMDB authentication failed", status=401) from None
            if status == 429:
                raise IPTVTMDBError(
                    "IPTV TMDB rate limit reached",
                    status=429,
                    retryable=True,
                    retry_after=max(1, retry_after),
                ) from None
            raise IPTVTMDBError(
                f"IPTV TMDB request failed with HTTP {status}",
                status=status,
                retryable=status >= 500,
            ) from None
        except (urllib.error.URLError, socket.timeout, TimeoutError) as error:
            reason = getattr(error, "reason", error)
            label = "timed out" if isinstance(reason, (socket.timeout, TimeoutError)) else "could not connect"
            raise IPTVTMDBError(f"IPTV TMDB {label}", retryable=True) from None
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise IPTVTMDBError("IPTV TMDB returned invalid JSON", retryable=True) from None

    def validate(self):
        payload = self._request("configuration")
        return bool(payload.get("images"))

    def search_movies(self, title, year=0, page=1):
        params = {"query": _text(title), "page": max(1, int(page or 1)), "include_adult": "false"}
        if _year(year):
            params["year"] = _year(year)
        payload = self._request("search/movie", params)
        return [row for row in payload.get("results", []) if isinstance(row, dict)]

    def search_movie_page(self, title, page=1, *, primary_year=0):
        params = {'query': _text(title), 'page': page, 'include_adult': 'false'}
        if primary_year:
            params['primary_release_year'] = primary_year
        payload = self._request('search/movie', params)
        rows, pages = payload.get('results'), payload.get('total_pages')
        if not isinstance(rows, list) or type(pages) is not int or pages < 0 or (rows and pages < page):
            raise IPTVTMDBError('TMDB returned invalid search pagination.', retryable=True)
        return [row for row in rows if isinstance(row, dict)], pages

    def movie(self, tmdb_id, language=""):
        tmdb_id = int(tmdb_id or 0)
        if tmdb_id <= 0:
            raise ValueError("A valid TMDB movie ID is required")
        params = {"append_to_response": "credits,keywords,release_dates,alternative_titles"}
        if _text(language):
            params["language"] = _text(language)
        return self._request(f"movie/{tmdb_id}", params)

    def collection(self, tmdb_id):
        return self._request(f"collection/{int(tmdb_id)}")

    def person(self, person_id):
        return self._request(f"person/{int(person_id)}", {"language": "en-US"})

    def normalized_movie(self, tmdb_id, language=""):
        return normalize_tmdb_movie(self.movie(tmdb_id, language=language))
