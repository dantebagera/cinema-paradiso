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
    ignored = bool(re.search(r'(?i)(?:^|[. _-])(sample|trailer|extras?|featurette)(?:[. _-]|$)', text))
    result = {'name': text, 'ignored': ignored, 'season_number': None, 'episode_numbers': [], 'air_date': None, 'scope': 'unknown'}
    match = re.search(r'(?i)(?<![a-z0-9])S(\d{1,3})E(\d{1,4})((?:(?:-?E|-)(\d{1,4}))*)', text)
    if match:
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
        result.update(season_number=int(match[1]), episode_numbers=[int(match[2])], scope='episode')
        return result
    match = re.search(r'(?<!\d)(20\d{2})[. -](\d{2})[. -](\d{2})(?!\d)', text)
    if match:
        try:
            result.update(air_date=date(*map(int, match.groups())).isoformat(), scope='daily')
        except ValueError:
            pass
        return result
    match = re.search(r'(?i)(?:^|[. _-])S(\d{1,3})(?![0-9e])', text)
    if match:
        result.update(season_number=int(match[1]), scope='season')
    return result


def resolve_episode_claim(claim, episodes, *, provider_episode_id=None):
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
    else:
        matches = []
    if not matches or any(row.get('reconciliation_required') for row in matches):
        return {'state': 'needs_review', 'episode_ids': [], 'reason': 'Numbering or identity requires an explicit mapping'}
    return {'state': 'accepted', 'episode_ids': [row['id'] for row in matches], 'reason': 'Numbering matches the selected canonical series'}
