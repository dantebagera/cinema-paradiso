"""Episode filename claims only; no catalog writes or title-only matching."""
from datetime import date
from pathlib import Path
import re
import unicodedata


def title_key(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(value or '')).casefold() if c.isalnum())


def series_identity(release, series, *, ambiguous=False):
    """Identity evidence is separate from episode coverage and torrent identity."""
    text = str(release.get('title') or '')
    prefix = re.split(r'(?i)(?:^|[. _-])(?:S\d{1,3}(?=E\d|$|[. _-])|\d{1,3}x\d+|20\d{2}[. -]\d{2}[. -]\d{2})', text, maxsplit=1)[0].strip(' ._-()[]')
    aliases = [series.get('title'), series.get('original_title'), *(series.get('alternative_titles') or [])]
    alias_keys = {title_key(x) for x in aliases if x}
    suffix = re.search(r'(?:[. _(-])((?:19|20)\d{2})[)\]]*$', prefix)
    # A number in the canonical title (for example 1923) is not a release year.
    year = suffix[1] if suffix and title_key(prefix) not in alias_keys else ''
    title = prefix[:suffix.start()].strip(' ._-()[]') if year else prefix
    title_match = title_key(title) in {title_key(x) for x in aliases if x}
    if not title_match and len(title_key(title)) >= 6 and release.get('folder_title'):
        folder = str(release['folder_title'])
        folder_words = set(re.findall(r'\w+', folder.casefold()))
        title_match = title_key(title) in title_key(folder) and any(
            len(title_key(alias)) >= 6 and set(re.findall(r'\w+', str(alias).casefold())) <= folder_words
            for alias in aliases if alias)
    expected_year = str(series.get('first_air_date') or '')[:4]
    evidence = {'title': title, 'year': year, 'title_match': title_match, 'method': 'title_year'}
    ids = [(release.get('tmdbId'), series.get('tmdb_id')), (release.get('tvdbId'), series.get('external_ids', {}).get('tvdb_id'))]
    conflicts = any(actual and expected and str(actual) != str(expected) for actual, expected in ids)
    matched_id = any(actual and expected and str(actual) == str(expected) for actual, expected in ids)
    if conflicts or (year and expected_year and year != expected_year) or (not title_match):
        return {**evidence, 'state': 'conflict', 'reason': 'Release title, year or provider identity does not match this series'}
    if matched_id:
        return {**evidence, 'state': 'matched', 'method': 'provider_id', 'reason': 'Provider identity matches'}
    if not year and ambiguous:
        return {**evidence, 'state': 'review', 'reason': 'Several series share this title; confirm which series this release contains'}
    return {**evidence, 'state': 'matched', 'reason': 'Series title and available year evidence match'}


VIDEO_EXTENSIONS = {'.mkv', '.mp4', '.avi', '.m4v', '.mov', '.ts', '.webm'}


def parse_episode_name(name):
    text = Path(str(name)).name
    stem = Path(text).stem
    marker = r'(?:sample|trailer|extras?|featurette)'
    ignored = bool(re.search(rf'(?i)(?:^|[._-]){marker}(?:[._-]|$)', stem))
    result = {'name': text, 'ignored': ignored, 'series_title': '', 'season_number': None, 'episode_numbers': [], 'absolute_number': None, 'air_date': None, 'scope': 'unknown'}
    match = re.search(r'(?i)(?<![a-z0-9])S(\d{1,3})E(\d{1,4})((?:(?:-?E|-)(\d{1,4}))*)', text)
    if match:
        result['series_title'] = stem[:match.start()].strip(' ._-()[]')
        tail = stem[match.end():].strip(' ._-()[]')
        result['ignored'] = bool(re.search(rf'(?i)(?:^|[._-]){marker}(?:[._-]|$)', result['series_title'])) or bool(
            re.match(r'(?i)^(?:sample|featurette|extras?)(?:[. _-]|$)|^trailer(?:[. _-]|$)', tail))
        numbers = [int(match[2])]
        suffix = match[3]
        if suffix:
            rest = [int(value) for value in re.findall(r'\d+', suffix)]
            if suffix.startswith('-') and len(rest) == 1 and numbers[0] <= rest[0] <= numbers[0] + 100:
                numbers = list(range(numbers[0], rest[0] + 1))
            else:
                numbers += rest
        result.update(season_number=int(match[1]), episode_numbers=sorted(set(numbers)), scope='episode')
        return result
    match = re.search(r'(?i)(?<!\d)(\d{1,3})x(\d{1,4})(?!\d)', text)
    if match:
        result['series_title'] = stem[:match.start()].strip(' ._-()[]')
        tail = stem[match.end():].strip(' ._-()[]')
        result['ignored'] = bool(re.search(rf'(?i)(?:^|[._-]){marker}(?:[._-]|$)', result['series_title'])) or bool(
            re.match(r'(?i)^(?:sample|featurette|extras?|trailer)(?:[. _-]|$)', tail))
        result.update(season_number=int(match[1]), episode_numbers=[int(match[2])], scope='episode')
        return result
    match = re.search(r'(?<!\d)(20\d{2})[. -](\d{2})[. -](\d{2})(?!\d)', text)
    if match:
        try:
            result['series_title'] = stem[:match.start()].strip(' ._-()[]')
            result.update(air_date=date(*map(int, match.groups())).isoformat(), scope='daily')
        except ValueError:
            pass
        return result
    clean_stem = re.sub(r'^\[[^\]]+\][ ._-]*', '', stem)
    clean_stem = re.sub(r'(?i)^(?:BBC|PBS|ITV)[ ._-]+', '', clean_stem)
    match = re.match(r'(?i)^(?P<title>.+?)[ ._-]+season[ ._-]*(?P<season>\d{1,3})[ ._-]+episode[ ._-]*(?P<episode>\d{1,4})(?=[ ._-]|$)', clean_stem)
    if match:
        result.update(series_title=match['title'].strip(' ._-()[]'), season_number=int(match['season']), episode_numbers=[int(match['episode'])], scope='episode')
        return result
    match = re.search(r'(?i)(?<!\d)(?P<number>\d{1,3})of(?P<total>\d{1,3})(?!\d)', clean_stem)
    if match:
        result.update(series_title=clean_stem[:match.start()].strip(' ._-()[]'), absolute_number=int(match['number']), absolute_total=int(match['total']), scope='absolute')
        return result
    match = re.match(r'^(?P<number>\d{1,3})[ ._-]+(?=[^\d\s])', clean_stem)
    if match:
        result.update(absolute_number=int(match['number']), scope='absolute')
        return result
    match = re.match(r'(?i)^(?P<title>.+?)[ ._-]+(?P<number>\d{1,3})(?=[ ._-]|$)', clean_stem)
    if match:
        result.update(series_title=match['title'].strip(' ._-()[]'), absolute_number=int(match['number']), scope='absolute')
        return result
    match = re.search(r'(?i)(?:^|[. _-])S(\d{1,3})(?![0-9e])', text)
    if match:
        result.update(season_number=int(match[1]), scope='season')
    return result


def resolve_episode_claim(claim, episodes, *, provider_episode_id=None, season_hint=None):
    if claim['ignored']:
        return {'state': 'ignored', 'episode_ids': [], 'reason': 'Sample or extra'}
    if provider_episode_id:
        matches = [row for row in episodes if str(row.get('provider_id')) == str(provider_episode_id)]
        # Explicit provider evidence must not conflict with filename numbering.
        if len(matches) == 1 and claim['scope'] == 'episode' and (matches[0]['season_number'] != claim['season_number'] or matches[0]['episode_number'] not in claim['episode_numbers']):
            return {'state': 'needs_review', 'episode_ids': [], 'reason': 'Provider and filename numbering conflict'}
    elif claim['scope'] == 'episode':
        matches = [row for row in episodes if row['season_number'] == claim['season_number'] and row['episode_number'] in claim['episode_numbers']]
        if len(matches) != len(claim['episode_numbers']):
            matches = []
    elif claim['scope'] == 'daily':
        matches = [row for row in episodes if row['air_date'] == claim['air_date']]
        if len(matches) != 1:
            matches = []
    elif claim['scope'] == 'absolute':
        regular_seasons = {row['season_number'] for row in episodes if row['season_number'] > 0}
        target_season = season_hint if season_hint in regular_seasons else (next(iter(regular_seasons)) if len(regular_seasons) == 1 else None)
        matches = [row for row in episodes if row['season_number'] == target_season and row['episode_number'] == claim['absolute_number']] if target_season is not None else []
        if claim.get('absolute_total') is not None and (target_season is None or sum(row['season_number'] == target_season for row in episodes) != claim['absolute_total']):
            matches = []
        if len(matches) != 1:
            matches = []
    else:
        matches = []
    if not matches or any(row.get('reconciliation_required') for row in matches):
        return {'state': 'needs_review', 'episode_ids': [], 'reason': 'Numbering or identity requires an explicit mapping'}
    return {'state': 'accepted', 'episode_ids': [row['id'] for row in matches], 'reason': 'Numbering matches the selected canonical series'}
