"""One source dictionary; eligibility belongs to acquisition profiles."""
import re

SOURCE_CATALOG = (
    {'id': 'bd_remux', 'label': 'BD Remux', 'family': 'bluray', 'rank': 9, 'pattern': r'\bbd[ ._-]*remux\b', 'legacy': ('bdremux', 'bd remux')},
    {'id': 'bluray', 'label': 'Blu-ray', 'family': 'bluray', 'rank': 7, 'pattern': r'\bblu[ ._-]*ray\b', 'legacy': ('bluray', 'blu-ray')},
    {'id': 'bdrip', 'label': 'BDRip', 'family': 'bluray', 'rank': 6, 'pattern': r'\b(?:bd|br)[ ._-]*rip\b', 'legacy': ('brrip', 'br-rip', 'bdrip', 'bd-rip')},
    {'id': 'web_dl', 'label': 'WEB-DL', 'family': 'web', 'rank': 5, 'pattern': r'\bweb[ ._-]*dl\b', 'legacy': ('web-dl', 'webdl')},
    {'id': 'webrip', 'label': 'WEBRip', 'family': 'web', 'rank': 4, 'pattern': r'\bweb[ ._-]*rip\b', 'legacy': ('webrip', 'web-rip')},
    {'id': 'hdrip', 'label': 'HDRip', 'family': 'web', 'rank': 3, 'pattern': r'\bhd[ ._-]*rip\b', 'legacy': ('hdrip',)},
    {'id': 'hdtv', 'label': 'HDTV', 'family': 'broadcast', 'rank': 2, 'pattern': r'\bhdtv\b', 'legacy': ('hdtv',)},
    {'id': 'dvdrip', 'label': 'DVDRip', 'family': 'disc', 'rank': 1, 'pattern': r'\bdvd[ ._-]*rip\b', 'legacy': ('dvdrip', 'dvd-rip')},
    {'id': 'dvdscr', 'label': 'DVDScr', 'family': 'screener', 'rank': 0, 'pattern': r'\bdvd[ ._-]*scr\b', 'legacy': ('dvdscr', 'dvd-scr')},
    {'id': 'hdcam', 'label': 'HDCAM', 'family': 'cinema', 'rank': -2, 'pattern': r'\bhdcam\b', 'legacy': ('hdcam',)},
    {'id': 'camrip', 'label': 'CAMRip', 'family': 'cinema', 'rank': -1, 'pattern': r'\bcam[ ._-]*rip\b', 'legacy': ('camrip', 'cam-rip')},
    {'id': 'remux', 'label': 'Remux', 'family': 'bluray', 'rank': 8, 'pattern': r'\bremux\b', 'legacy': ('remux',)},
    {'id': 'cam', 'label': 'CAM', 'family': 'cinema', 'rank': -2, 'pattern': r'\bcam\b', 'legacy': ()},
    {'id': 'hqcam', 'label': 'HQCAM', 'family': 'cinema', 'rank': -2, 'pattern': r'\bhqcam\b', 'legacy': ()},
    {'id': 'ts', 'label': 'TS', 'family': 'cinema', 'rank': -2, 'pattern': r'\b(?:telesync|hdts|ts)\b', 'legacy': ()},
    {'id': 'tc', 'label': 'TC', 'family': 'cinema', 'rank': -2, 'pattern': r'\b(?:telecine|tc)\b', 'legacy': ()},
    {'id': 'workprint', 'label': 'Workprint', 'family': 'screener', 'rank': 0, 'pattern': r'\b(?:workprint|wp)\b', 'legacy': ()},
    {'id': 'screener', 'label': 'Screener', 'family': 'screener', 'rank': 0, 'pattern': r'\b(?:scr|screener)\b', 'legacy': ()},
    {'id': 'unknown', 'label': 'Unknown', 'family': 'unknown', 'rank': -3, 'pattern': r'(?!)', 'legacy': ()},
)
SOURCES = {row['id']: row for row in SOURCE_CATALOG}
SOURCE_RANK = {row['label']: row['rank'] for row in SOURCE_CATALOG}
RESOLUTIONS = ('480p', '576p', '720p', '1080p', '2160p', 'unknown')
ELIGIBILITY = ('blocked', 'manual_only', 'allowed', 'preferred')
FOLLOW_COMPATIBILITY_SOURCES = frozenset({'webrip', 'bluray', 'bdrip'})


def source_claim(title):
    # Container suffixes are not source claims (notably MPEG transport .ts).
    text = re.sub(r'(?i)\.(?:mkv|mp4|m4v|avi|mov|ts|m2ts|webm)$', '', str(title or ''))
    matches = [row for row in SOURCE_CATALOG if re.search(row['pattern'], text, re.I)]
    dangerous = [row for row in matches if row['family'] in {'cinema', 'screener'}]
    if dangerous:
        return dangerous[0]['id']
    if any(row['id'] == 'remux' for row in matches) and any(row['id'] == 'bluray' for row in matches):
        return 'bd_remux'
    return matches[0]['id'] if matches else 'unknown'


def legacy_source_label(filename):
    # Temporary classification compatibility: remove only after local-card parity
    # accepts the richer aliases. All definitions still come from this catalog.
    name = str(filename).lower()
    for row in SOURCE_CATALOG:
        if any(alias in name for alias in row['legacy']):
            return row['label']
        if row['id'] == 'camrip' and name.endswith('.cam'):
            return row['label']
    return 'Unknown'


def release_claims(title):
    text = str(title or '')
    match = re.search(r'(?i)(?<!\d)(480|576|720|1080|2160)p?(?!\d)', text)
    resolution = match[1] + 'p' if match else '2160p' if re.search(r'(?i)\b(?:4k|uhd)\b', text) else 'unknown'
    return {'source': source_claim(text), 'resolution': resolution,
            'codec': 'HEVC' if re.search(r'(?i)\b(?:x265|h265|hevc)\b', text) else 'AVC' if re.search(r'(?i)\b(?:x264|h264|avc)\b', text) else 'unknown',
            'hdr': bool(re.search(r'(?i)\b(?:hdr|hdr10|dolby[ ._-]*vision|dv)\b', text)),
            'revision': 1 if re.search(r'(?i)\b(?:proper|repack)\b', text) else 0,
            'edition': next((word for word in ('extended', 'unrated', 'remastered', 'directors.cut') if word in text.lower()), ''),
            'group': text.rsplit('-', 1)[-1] if '-' in text else '', 'title': text}
