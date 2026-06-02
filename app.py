import os
import re
import stat
import shutil
import time
import urllib.request
import urllib.parse
import json as _json
from flask import Flask, render_template, jsonify, request, make_response
from send2trash import send2trash

app = Flask(__name__)

# Config file stored next to app.py
_CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')

def _load_config():
    if os.path.exists(_CONFIG_FILE):
        try:
            with open(_CONFIG_FILE, 'r', encoding='utf-8') as f:
                return _json.load(f)
        except Exception:
            pass
    return {}

def _save_config(data):
    try:
        with open(_CONFIG_FILE, 'w', encoding='utf-8') as f:
            _json.dump(data, f, indent=2)
    except Exception:
        pass

_cfg = _load_config()
_movies_dir     = _cfg.get('movies_dir', r"E:\Movies")
_prowlarr_url   = _cfg.get('prowlarr_url', '')
_prowlarr_key   = _cfg.get('prowlarr_key', '')
_tmdb_key       = _cfg.get('tmdb_key', '')
_plex_url       = _cfg.get('plex_url', 'http://localhost:32400')
_plex_token     = _cfg.get('plex_token', '')
_ollama_url     = _cfg.get('ollama_url', 'http://localhost:11434')
_ollama_model   = _cfg.get('ollama_model', 'gemma4:31b-cloud')
_plex_cache     = {}   # _norm(file_path) -> {plex_title, plex_year, plex_genres}
_plex_unmatched = {}   # _norm(path) -> {rating_key, plex_title}  (Plex has file but no metadata)
_plex_matched_by_fname   = {}  # filename.lower() -> matched entry   (path-mismatch fallback)
_plex_unmatched_by_fname = {}  # filename.lower() -> unmatched entry (path-mismatch fallback)

def _norm(path):
    """Normalise a file path for use as a cache key.
    Uses normcase so Windows drive-letter case differences don't cause misses.
    e.g. Plex returns 'e:\\...' while os.walk gives 'E:\\...'
    """
    return os.path.normcase(os.path.normpath(path))
_plex_section_ids = [] # movie section keys — used for triggering rescans
_metadata_cache  = {}  # "{title}_{year}" -> {poster_url, genres, plot, tmdb_rating} — memory-only
_tmdb_genres     = {}  # genre_id -> genre_name, lazy-loaded once from TMDB
_TV_RE = re.compile(
    r'(?:s\d{1,2}e\d{1,2}|\d{1,2}x\d{2}|season[\s._-]*\d|episode[\s._-]*\d'
    r'|\bep[\s._-]*\d{1,3}\b|complete[\s._-]+series|\bcomplete[\s._-]+season)',
    re.IGNORECASE
)
_MOVIE_FOLDER_RE = re.compile(r'\b(19|20)\d{2}\b')  # folder name looks like a movie title
_LANG_NAMES = {
    'en':'English','fr':'French','es':'Spanish','de':'German','it':'Italian',
    'pt':'Portuguese','ru':'Russian','ja':'Japanese','ko':'Korean','zh':'Chinese',
    'ar':'Arabic','hi':'Hindi','tr':'Turkish','nl':'Dutch','sv':'Swedish',
    'pl':'Polish','da':'Danish','fi':'Finnish','no':'Norwegian','th':'Thai',
    'vi':'Vietnamese','id':'Indonesian','cs':'Czech','hu':'Hungarian','ro':'Romanian',
}
_LANG_COUNTRY = {
    'en':'US','fr':'FR','es':'ES','de':'DE','it':'IT','pt':'PT','ru':'RU',
    'ja':'JP','ko':'KR','zh':'CN','ar':'SA','hi':'IN','tr':'TR','nl':'NL',
    'sv':'SE','pl':'PL','da':'DK','fi':'FI','no':'NO','th':'TH','vi':'VN',
    'id':'ID','cs':'CZ','hu':'HU','ro':'RO',
}
def _country_flag(code):
    if not code or len(code) != 2: return ''
    return chr(ord(code[0].upper())+127397) + chr(ord(code[1].upper())+127397)

_res_cache = {}  # (abspath, mtime) -> resolution_str  — resolution probe cache
_RES_CACHE_FILE  = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'res_cache.json')
_library_status  = ''  # live status string polled by the browser during a scan
_plex_cache_time = 0.0
_PLEX_TTL        = 300  # seconds before auto-refresh
_library_cache   = {}   # keys: items, plex_enabled, plex_cached, time
_LIBRARY_TTL     = 300  # seconds — same as Plex TTL

def _all_config():
    return {
        'movies_dir': _movies_dir,
        'prowlarr_url': _prowlarr_url,
        'prowlarr_key': _prowlarr_key,
        'plex_url': _plex_url,
        'plex_token': _plex_token,
        'tmdb_key': _tmdb_key,
        'ollama_url': _ollama_url,
        'ollama_model': _ollama_model,
    }

VIDEO_EXTENSIONS = {'.mkv', '.mp4', '.avi', '.m4v', '.mov', '.wmv', '.flv', '.ts', '.m2ts', '.iso'}

try:
    from pymediainfo import MediaInfo as _MediaInfo
    _MEDIAINFO_AVAILABLE = True
except ImportError:
    _MediaInfo = None
    _MEDIAINFO_AVAILABLE = False


def get_movies_dir():
    return _movies_dir


def _probe_resolution(filepath):
    """Use pymediainfo to read actual video height. Returns resolution string or None."""
    if not _MEDIAINFO_AVAILABLE:
        return None
    try:
        info = _MediaInfo.parse(filepath)
        for track in info.tracks:
            if track.track_type == 'Video':
                h = int(track.height or 0)
                if h >= 2160: return '4K'
                if h >= 1080: return '1080p'
                if h >= 720:  return '720p'
                if h >= 480:  return '480p'
                if h > 0:     return f'{h}p'
        return None
    except Exception:
        return None


def get_resolution_from_file(filepath):
    """Return resolution string for a video file.
    Uses filename parsing first (fast). If the filename gives 'Unknown',
    falls back to pymediainfo to read actual video stream dimensions.
    Falls back gracefully if pymediainfo is not installed."""
    filename = os.path.basename(filepath)
    res = get_resolution(filename)
    if res != 'Unknown':
        return res
    # Filename has no resolution tag — probe with mediainfo
    try:
        mtime = os.path.getmtime(filepath)
    except OSError:
        return res
    key = (os.path.abspath(filepath), mtime)
    if key in _res_cache:
        return _res_cache[key]
    probed = _probe_resolution(filepath)
    result = probed if probed else res
    _res_cache[key] = result
    return result


def get_resolution_rank_str(resolution):
    """Return numeric rank for an already-resolved resolution string."""
    order = {'4K': 4, '1080p': 3, '720p': 2, '480p': 1, 'Unknown': 0}
    return order.get(resolution, 0)


def _load_res_cache():
    """Load persisted resolution cache from disk into _res_cache."""
    global _res_cache
    try:
        with open(_RES_CACHE_FILE, 'r', encoding='utf-8') as f:
            data = _json.load(f)
        for path, v in data.items():
            _res_cache[(path, float(v['mtime']))] = v['res']
    except Exception:
        pass


def _save_res_cache():
    """Persist resolution cache to disk so probed results survive app restarts."""
    try:
        data = {}
        for (path, mtime), res in _res_cache.items():
            data[path] = {'mtime': mtime, 'res': res}
        with open(_RES_CACHE_FILE, 'w', encoding='utf-8') as f:
            _json.dump(data, f, indent=2)
    except Exception:
        pass


_load_res_cache()  # populate cache from disk at startup

def parse_movie_title(filename):
    """Return a (title, year) key so remakes with the same name are not grouped together."""
    name = os.path.splitext(filename)[0]

    # Extract year — handles: .2003. / (2003) / [2003] / {2003} / _2003_ / -2003- / space
    year_match = re.search(r'[\.\s_\-\(\[\{]((19|20)\d{2})[\.\s_\-\)\]\}]', name)
    year = year_match.group(1) if year_match else ''

    if year_match:
        name = name[:year_match.start()]
    else:
        name = re.sub(
            r'[\.\s_\-]*(1080p|720p|480p|2160p|4k|uhd|bluray|blu-ray|bdrip|bdremux|'
            r'hdrip|webrip|web-dl|dvdrip|hdtv|x264|x265|hevc|avc|aac|dts|ac3|h264|h265|'
            r'10bit|remux|extended|theatrical|remastered|directors\.cut).*',
            '', name, flags=re.IGNORECASE
        )

    name = re.sub(r'[\._\-]', ' ', name)
    name = re.sub(r'\s+', ' ', name).strip().lower()
    return (name, year)


def get_resolution(filename):
    name = filename.lower()
    if '2160p' in name or '4k' in name or 'uhd' in name:
        return '4K'
    elif '1080p' in name or re.search(r'[\.\-_ \[\(]1080[\.\-_ \]\)\[]', name):
        return '1080p'
    elif '720p' in name or re.search(r'[\.\-_ \[\(]720[\.\-_ \]\)\[]', name):
        return '720p'
    elif '480p' in name or re.search(r'[\.\-_ \[\(]480[\.\-_ \]\)\[]', name):
        return '480p'
    return 'Unknown'


def get_rip_rank(rip_source):
    order = {
        'BD Remux': 9, 'Remux': 8, 'Blu-ray': 7, 'BDRip': 6,
        'WEB-DL': 5, 'WEBRip': 4, 'HDRip': 3, 'HDTV': 2,
        'DVDRip': 1, 'DVDScr': 0, 'CAMRip': -1, 'HDCAM': -2, 'Unknown': -3,
    }
    return order.get(rip_source, -3)


def get_resolution_rank(filename):
    order = {'4K': 4, '1080p': 3, '720p': 2, '480p': 1, 'Unknown': 0}
    return order.get(get_resolution(filename), 0)


def get_rip_source(filename):
    name = filename.lower()
    # Order matters — check more specific terms first
    if 'bdremux' in name or 'bd remux' in name:
        return 'BD Remux'
    elif 'bluray' in name or 'blu-ray' in name or 'bluray' in name:
        return 'Blu-ray'
    elif 'bdrip' in name or 'bdrip' in name:
        return 'BDRip'
    elif 'web-dl' in name or 'webdl' in name:
        return 'WEB-DL'
    elif 'webrip' in name or 'web-rip' in name:
        return 'WEBRip'
    elif 'hdrip' in name:
        return 'HDRip'
    elif 'hdtv' in name:
        return 'HDTV'
    elif 'dvdrip' in name or 'dvd-rip' in name:
        return 'DVDRip'
    elif 'dvdscr' in name or 'dvd-scr' in name:
        return 'DVDScr'
    elif 'hdcam' in name:
        return 'HDCAM'
    elif 'camrip' in name or 'cam-rip' in name or name.endswith('.cam'):
        return 'CAMRip'
    elif 'remux' in name:
        return 'Remux'
    return 'Unknown'


def format_size(size):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} PB"


def scan_duplicates(movies_dir):
    # If Plex assigns more than this many files to the same title+year it has
    # almost certainly bulk-mis-matched them (e.g. whole folder → one wrong film).
    # Fall back to filename parsing for those files.
    MAX_PLEX_GROUP = 4

    groups     = {}   # title_key -> [file_dict, ...]
    plex_keyed = set()  # title keys that came from Plex metadata

    for root, dirs, files in os.walk(movies_dir):
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext not in VIDEO_EXTENSIONS:
                continue
            full_path = os.path.join(root, file)
            try:
                size = os.path.getsize(full_path)
            except OSError:
                size = 0
            # Prefer Plex metadata title/year — matches exactly what Plex considers a duplicate.
            # Fall back to filename parsing for files not yet in Plex.
            plex_data = _plex_cache.get(_norm(full_path), {})
            if plex_data.get('plex_title'):
                title_key = (plex_data['plex_title'].strip().lower(), str(plex_data.get('plex_year', '')))
                plex_keyed.add(title_key)
            else:
                title_key = parse_movie_title(file)
            if not title_key[0]:
                continue
            res = get_resolution_from_file(full_path)
            groups.setdefault(title_key, []).append({
                'path': full_path,
                'filename': file,
                'size': size,
                'size_human': format_size(size),
                'resolution': res,
                'resolution_rank': get_resolution_rank_str(res),
                'rip_source': get_rip_source(file),
            })

    # Detect Plex bulk mis-matches: a Plex-derived group with > MAX_PLEX_GROUP files
    # means Plex tagged an entire folder as the same movie (wrong). Re-bucket those
    # files by filename so they appear as individual titles instead.
    for bad_key in [k for k in plex_keyed if len(groups.get(k, [])) > MAX_PLEX_GROUP]:
        for entry in groups.pop(bad_key):
            fallback_key = parse_movie_title(entry['filename'])
            if fallback_key[0]:
                groups.setdefault(fallback_key, []).append(entry)

    duplicates = []
    total_wasted = 0
    for (title, year), files in groups.items():
        if len(files) < 2:
            continue
        files_sorted = sorted(files, key=lambda x: (x['resolution_rank'], get_rip_rank(x['rip_source']), x['size']), reverse=True)
        # Wasted space = all copies except the best one
        wasted = sum(f['size'] for f in files_sorted[1:])
        total_wasted += wasted
        display_title = title.title() + (f' ({year})' if year else '')
        duplicates.append({
            'title': display_title,
            'files': files_sorted,
            'wasted': wasted,
            'wasted_human': format_size(wasted),
        })
    duplicates.sort(key=lambda x: x['title'])

    extra_copies = sum(len(d['files']) - 1 for d in duplicates)
    stats = {
        'groups': len(duplicates),
        'extra_copies': extra_copies,
        'wasted_human': format_size(total_wasted),
        'wasted_bytes': total_wasted,
    }
    return duplicates, stats


def _auto_sync_plex(force=False):
    """Refresh _plex_cache if Plex is configured and cache is stale (>5 min). Silent on errors.
    Pass force=True to bypass the TTL and always fetch fresh data."""
    global _plex_cache, _plex_unmatched, _plex_matched_by_fname, _plex_unmatched_by_fname, \
           _plex_section_ids, _plex_cache_time, _library_cache
    if not _plex_url or not _plex_token:
        return
    if not force and time.time() - _plex_cache_time < _PLEX_TTL:
        return  # cache is still fresh
    try:
        _plex_cache, _plex_unmatched, _plex_matched_by_fname, _plex_unmatched_by_fname, \
            _plex_section_ids = _fetch_plex_library()
        _plex_cache_time = time.time()
        _library_cache = {}  # Plex data refreshed — bust library cache so titles update
    except Exception:
        pass  # don't break scan if Plex is unreachable


def _fetch_plex_library():
    """Fetch all movie file paths + metadata from Plex.
    Returns (matched_cache, unmatched_cache, matched_by_fname, unmatched_by_fname, section_ids).
    matched_cache:    normpath -> {plex_title, plex_year, plex_genres}
    unmatched_cache:  normpath -> {rating_key, plex_title}  (Plex has file but no match)
    matched_by_fname:   filename.lower() -> matched entry   (fallback for path-mismatch cases)
    unmatched_by_fname: filename.lower() -> unmatched entry (fallback for path-mismatch cases)
    section_ids: list of movie library section keys
    """
    if not _plex_url or not _plex_token:
        return {}, {}, {}, {}, []

    def plex_get(path):
        sep = '&' if '?' in path else '?'
        url = f"{_plex_url}{path}{sep}X-Plex-Token={_plex_token}"
        req = urllib.request.Request(url, headers={'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return _json.loads(resp.read().decode())

    data = plex_get('/library/sections')
    sections = data.get('MediaContainer', {}).get('Directory', [])
    movie_sections = [s['key'] for s in sections if s.get('type') == 'movie']

    matched = {}
    unmatched = {}
    matched_by_fname = {}
    unmatched_by_fname = {}
    for section_key in movie_sections:
        data = plex_get(f'/library/sections/{section_key}/all')
        for item in data.get('MediaContainer', {}).get('Metadata', []):
            guid        = item.get('guid', '')
            rating_key  = item.get('ratingKey', '')
            title       = item.get('title', '')
            year        = str(item.get('year', '')) if item.get('year') else ''
            genres      = [g['tag'] for g in item.get('Genre', [])]
            summary     = item.get('summary', '')
            rating      = str(item.get('rating', '') or item.get('audienceRating', '') or '')
            thumb       = item.get('thumb', '')
            is_local    = (not guid) or guid.startswith('local://')
            for media in item.get('Media', []):
                for part in media.get('Part', []):
                    fp = part.get('file', '')
                    if fp:
                        norm  = _norm(fp)
                        fname = os.path.basename(fp).lower()
                        if is_local:
                            entry = {'rating_key': rating_key, 'plex_title': title}
                            unmatched[norm] = entry
                            # filename fallback — only store first hit to avoid collisions
                            unmatched_by_fname.setdefault(fname, entry)
                        else:
                            entry = {'plex_title': title, 'plex_year': year, 'plex_genres': genres,
                                     'plex_summary': summary, 'plex_rating': rating, 'plex_thumb': thumb}
                            matched[norm] = entry
                            matched_by_fname.setdefault(fname, entry)
    return matched, unmatched, matched_by_fname, unmatched_by_fname, movie_sections


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/plex/config', methods=['GET'])
def get_plex_config():
    return jsonify({'url': _plex_url, 'token': _plex_token})


@app.route('/api/plex/config', methods=['POST'])
def set_plex_config():
    global _plex_url, _plex_token
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    _plex_url   = data.get('url', 'http://localhost:32400').rstrip('/')
    _plex_token = data.get('token', '')
    _save_config(_all_config())
    return jsonify({'success': True})


@app.route('/api/plex/test')
def plex_test():
    if not _plex_url or not _plex_token:
        return jsonify({'error': 'URL or token missing — configure Plex first.'}), 400
    try:
        sep = '&' if '?' in '/library/sections' else '?'
        url = f"{_plex_url}/library/sections{sep}X-Plex-Token={_plex_token}"
        req = urllib.request.Request(url, headers={'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = _json.loads(resp.read().decode())
        sections = data.get('MediaContainer', {}).get('Directory', [])
        movie_libs = [s for s in sections if s.get('type') == 'movie']
        return jsonify({'success': True, 'movie_libraries': len(movie_libs), 'total_libraries': len(sections)})
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return jsonify({'error': 'Invalid token — Plex → Settings → General → Advanced → X-Plex-Token.'}), 401
        return jsonify({'error': f'Plex returned HTTP {e.code}'}), 502
    except Exception as e:
        return jsonify({'error': f'Cannot reach Plex: {e}'}), 502


@app.route('/api/plex/image')
def plex_image():
    url = request.args.get('url', '').strip()
    if not url:
        return '', 400
    # Security: only proxy to the configured Plex server — reject any other origin
    if not _plex_url or not url.startswith(_plex_url):
        return '', 403
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read()
            ct   = resp.headers.get('Content-Type', 'image/jpeg')
        response = make_response(data)
        response.headers['Content-Type']  = ct
        response.headers['Cache-Control'] = 'public, max-age=86400'
        return response
    except Exception:
        return '', 502


@app.route('/api/plex/sync')
def plex_sync():
    global _plex_cache, _plex_unmatched, _plex_section_ids, _plex_cache_time
    if not _plex_url or not _plex_token:
        return jsonify({'error': 'Plex not configured.'}), 400
    try:
        _plex_cache, _plex_unmatched, _plex_section_ids = _fetch_plex_library()
        _plex_cache_time = time.time()
        return jsonify({'success': True, 'cached': len(_plex_cache)})
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return jsonify({'error': 'Invalid Plex token.'}), 401
        return jsonify({'error': f'Plex returned HTTP {e.code}'}), 502
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/config', methods=['GET'])
def get_config():
    return jsonify({'directory': get_movies_dir()})


@app.route('/api/config', methods=['POST'])
def set_config():
    global _movies_dir, _library_cache
    data = request.get_json(silent=True)
    if not data or 'directory' not in data:
        return jsonify({'error': 'No directory provided'}), 400
    new_dir = data['directory'].strip()
    if not os.path.isdir(new_dir):
        return jsonify({'error': f'Directory not found: {new_dir}'}), 400
    _movies_dir = new_dir
    _library_cache = {}  # directory changed — bust library cache
    _save_config(_all_config())
    return jsonify({'success': True, 'directory': _movies_dir})


@app.route('/api/prowlarr/config', methods=['GET'])
def get_prowlarr_config():
    return jsonify({'url': _prowlarr_url, 'key': _prowlarr_key})


@app.route('/api/prowlarr/config', methods=['POST'])
def set_prowlarr_config():
    global _prowlarr_url, _prowlarr_key
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    _prowlarr_url = data.get('url', '').rstrip('/')
    _prowlarr_key = data.get('key', '')
    _save_config(_all_config())
    return jsonify({'success': True})


@app.route('/api/prowlarr/test')
def prowlarr_test():
    if not _prowlarr_url or not _prowlarr_key:
        return jsonify({'error': 'URL or API key is missing — please fill in both fields and save.'}), 400
    try:
        url = f"{_prowlarr_url}/api/v1/indexer"
        req = urllib.request.Request(url, headers={'X-Api-Key': _prowlarr_key, 'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=8) as resp:
            indexers = _json.loads(resp.read().decode())
        return jsonify({'success': True, 'indexers': len(indexers)})
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return jsonify({'error': 'Invalid API key — check Prowlarr → Settings → General.'}), 401
        return jsonify({'error': f'Prowlarr returned HTTP {e.code}'}), 502
    except Exception as e:
        return jsonify({'error': f'Cannot reach Prowlarr: {e}'}), 502


@app.route('/api/prowlarr/search')
def prowlarr_search():
    if not _prowlarr_url or not _prowlarr_key:
        return jsonify({'error': 'Prowlarr not configured — click ⚙ Prowlarr in the header to enter your URL and API key.'}), 400
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({'error': 'No query provided'}), 400
    try:
        # Fetch all enabled indexer IDs so every indexer is queried, not just the default subset
        indexer_ids = []
        try:
            idx_req = urllib.request.Request(
                f"{_prowlarr_url}/api/v1/indexer",
                headers={'X-Api-Key': _prowlarr_key, 'Accept': 'application/json'}
            )
            with urllib.request.urlopen(idx_req, timeout=8) as idx_resp:
                indexers = _json.loads(idx_resp.read().decode())
            indexer_ids = [str(ix['id']) for ix in indexers if ix.get('enable', True)]
        except Exception:
            pass  # fall back to Prowlarr default if indexer fetch fails

        qs = {'query': query, 'type': 'search', 'limit': 1000}
        if indexer_ids:
            qs['indexerIds'] = indexer_ids  # will be encoded as repeated params below
        # urllib.parse.urlencode doesn't handle lists — build manually
        parts = [(k, v) for k, v in qs.items() if k != 'indexerIds']
        parts += [('indexerIds', iid) for iid in indexer_ids]
        url = f"{_prowlarr_url}/api/v1/search?{urllib.parse.urlencode(parts)}"
        req = urllib.request.Request(url, headers={'X-Api-Key': _prowlarr_key, 'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=30) as resp:
            results = _json.loads(resp.read().decode())
        # Detect resolution from torrent title and format results (all resolutions)
        filtered = []
        for r in results:
            title = r.get('title', '')
            tl = title.lower()
            res = 'Unknown'
            res_rank = 0
            if '2160p' in tl or '4k' in tl or 'uhd' in tl:
                res, res_rank = '4K', 4
            elif '1080p' in tl or re.search(r'[\.\-_ \[\(]1080[\.\-_ \]\)\[]', tl):
                res, res_rank = '1080p', 3
            elif '720p' in tl or re.search(r'[\.\-_ \[\(]720[\.\-_ \]\)\[]', tl):
                res, res_rank = '720p', 2
            elif '480p' in tl or re.search(r'[\.\-_ \[\(]480[\.\-_ \]\)\[]', tl):
                res, res_rank = '480p', 1
            size = r.get('size', 0)
            filtered.append({
                'title': title,
                'indexer': r.get('indexer', ''),
                'size_human': format_size(size) if size else '?',
                'size': size,
                'seeders': r.get('seeders', 0),
                'resolution': res,
                'download_url': r.get('downloadUrl', ''),
                'magnet_url': r.get('magnetUrl', ''),
                'info_url': r.get('infoUrl', ''),
            })
        # Sort: resolution desc, then seeders desc
        filtered.sort(key=lambda x: (x['size'], x['seeders']), reverse=True)
        return jsonify({'results': filtered})
    except urllib.error.HTTPError as e:
        return jsonify({'error': f'Prowlarr returned HTTP {e.code}'}), 502
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/duplicates')
def get_duplicates():
    try:
        _auto_sync_plex(force=request.args.get('force_plex') == '1')
        duplicates, stats = scan_duplicates(get_movies_dir())
        for group in duplicates:
            for f in group['files']:
                plex_data = _plex_cache.get(_norm(f['path']), {})
                f['plex_title']   = plex_data.get('plex_title', '')
                f['plex_year']    = plex_data.get('plex_year', '')
                f['plex_genres']  = plex_data.get('plex_genres', [])
                f['plex_matched'] = bool(plex_data)
        return jsonify({'duplicates': duplicates, 'directory': get_movies_dir(), 'stats': stats,
                        'plex_enabled': bool(_plex_token), 'plex_cached': len(_plex_cache) > 0})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/open-file', methods=['POST'])
def open_file():
    data = request.get_json(silent=True)
    path = (data or {}).get('path', '').strip()
    if not path or not os.path.isfile(path):
        return jsonify({'error': 'File not found'}), 404
    try:
        os.startfile(path)
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/delete', methods=['POST'])
def delete_file():
    global _movies_dir
    data = request.get_json(silent=True)
    if not data or 'path' not in data:
        return jsonify({'error': 'No path provided'}), 400

    path = data['path']
    use_trash = data.get('trash', True)  # default: Recycle Bin
    abs_path = os.path.abspath(path)
    abs_dir = os.path.abspath(get_movies_dir())

    # Security: only allow deleting files inside the configured movies directory
    if not abs_path.startswith(abs_dir + os.sep) and abs_path != abs_dir:
        return jsonify({'error': 'Path is outside the allowed movies directory'}), 403

    if not os.path.isfile(abs_path):
        return jsonify({'error': 'File not found'}), 404

    try:
        # Clear read-only flag if set
        current_mode = os.stat(abs_path).st_mode
        if not (current_mode & stat.S_IWRITE):
            os.chmod(abs_path, current_mode | stat.S_IWRITE)

        if use_trash:
            send2trash(abs_path)
        else:
            os.remove(abs_path)

        # Clean up parent folder if no video files remain
        parent = os.path.dirname(abs_path)
        folder_removed = False
        if not use_trash and parent != abs_dir and os.path.isdir(parent):
            remaining_videos = [
                f for f in os.listdir(parent)
                if os.path.splitext(f)[1].lower() in VIDEO_EXTENSIONS
            ]
            if not remaining_videos:
                shutil.rmtree(parent, ignore_errors=True)
                folder_removed = True

        _library_cache.pop('items', None)  # bust library cache — file list changed
        return jsonify({'success': True, 'deleted': abs_path, 'folder_removed': folder_removed, 'folder': parent, 'trashed': use_trash})
    except PermissionError:
        return jsonify({
            'error': 'Access denied. The file may be open in Plex or another program. '
                     'Try pausing Plex Media Server and then delete again.'
        }), 500
    except OSError as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/library/status')
def library_status():
    return jsonify({'status': _library_status})


@app.route('/api/library')
def library():
    global _library_cache, _library_status
    force_plex = request.args.get('force_plex') == '1'
    try:
        _auto_sync_plex(force=force_plex)
        # Serve from cache if still fresh and directory hasn't changed
        if (not force_plex
                and _library_cache.get('items') is not None
                and _library_cache.get('dir') == get_movies_dir()
                and time.time() - _library_cache.get('time', 0) < _LIBRARY_TTL):
            c = _library_cache
            return jsonify({'items': c['items'], 'count': len(c['items']),
                            'plex_enabled': c['plex_enabled'], 'plex_cached': c['plex_cached'],
                            'cached': True})
        movies_dir = get_movies_dir()
        _library_status = 'Scanning directory\u2026'
        total = sum(1 for _, _, fs in os.walk(movies_dir)
                    for f in fs if os.path.splitext(f)[1].lower() in VIDEO_EXTENSIONS)
        _library_status = f'Reading metadata for {total} files\u2026'
        items = []
        n = 0
        for root, dirs, files in os.walk(movies_dir):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext not in VIDEO_EXTENSIONS:
                    continue
                n += 1
                if n % 50 == 0:
                    _library_status = f'Reading metadata\u2026 {n}\u00a0/\u00a0{total}'
                full_path = os.path.join(root, file)
                try:
                    size = os.path.getsize(full_path)
                except OSError:
                    size = 0
                res = get_resolution_from_file(full_path)
                rip = get_rip_source(file)
                title_key = parse_movie_title(file)
                if not title_key[0]:
                    continue
                display_title = title_key[0].title() + (f' ({title_key[1]})' if title_key[1] else '')
                norm_path = _norm(full_path)
                plex_data = _plex_cache.get(norm_path, {})
                plex_thumb = plex_data.get('plex_thumb', '')
                plex_poster = (
                    f"{_plex_url}{plex_thumb}?X-Plex-Token={_plex_token}"
                    if _plex_url and _plex_token and plex_thumb else ''
                )
                items.append({
                    'title': display_title,
                    'filename': file,
                    'path': full_path,
                    'resolution': res,
                    'resolution_rank': get_resolution_rank_str(res),
                    'rip_source': rip,
                    'rip_rank': get_rip_rank(rip),
                    'size': size,
                    'size_human': format_size(size),
                    'plex_title': plex_data.get('plex_title', ''),
                    'plex_year': plex_data.get('plex_year', ''),
                    'plex_genres': plex_data.get('plex_genres', []),
                    'plex_summary': plex_data.get('plex_summary', ''),
                    'plex_rating': plex_data.get('plex_rating', ''),
                    'plex_poster': plex_poster,
                    'plex_matched': bool(plex_data),
                })
        _library_status = 'Sorting results\u2026'
        items.sort(key=lambda x: x['title'])
        _library_status = ''
        _save_res_cache()
        _library_cache['items'] = items
        _library_cache['plex_enabled'] = bool(_plex_token)
        _library_cache['plex_cached'] = len(_plex_cache) > 0
        _library_cache['time'] = time.time()
        _library_cache['dir'] = movies_dir
        return jsonify({'items': items, 'count': len(items),
                        'plex_enabled': bool(_plex_token), 'plex_cached': len(_plex_cache) > 0})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/library/check', methods=['POST'])
def library_check():
    """Check which of the supplied movies exist in the local library.

    Request body: {"movies": [{"title": "Inception", "year": "2010"}, …]}
    Response:     {"results": [{"title": …, "year": …, "found": bool,
                                "path": …, "resolution": …, "size_human": …}]}
    Matching uses normalised title comparison (lowercase, no punctuation, no
    leading article) against plex_title+plex_year first, then parsed filename
    title+year.  Returns found:false for all entries when movies_dir is not set.
    """
    import re as _re_local

    def _norm_title(t):
        """Lowercase, strip punctuation, strip leading 'the/a/an '."""
        if not t:
            return ''
        t = str(t).lower()
        t = _re_local.sub(r'[^\w\s]', '', t)   # strip punctuation
        t = _re_local.sub(r'\s+', ' ', t).strip()
        t = _re_local.sub(r'^(the|a|an) ', '', t)
        return t

    try:
        body = request.get_json(force=True, silent=True) or {}
        queries = body.get('movies', [])
        if not queries:
            return jsonify({'results': []})

        movies_dir = get_movies_dir()
        if not movies_dir or not os.path.isdir(movies_dir):
            return jsonify({'results': [
                {'title': q.get('title', ''), 'year': str(q.get('year', '')),
                 'found': False, 'path': '', 'resolution': '', 'size_human': ''}
                for q in queries
            ]})

        # Build lookup: (norm_title, norm_year) -> best file info dict
        # Use library cache if fresh, else walk the directory (no deep scan needed)
        _auto_sync_plex(force=False)
        lookup = {}  # (norm_title, norm_year) -> {path, resolution, size_human}

        if (_library_cache.get('items') is not None
                and _library_cache.get('dir') == movies_dir
                and time.time() - _library_cache.get('time', 0) < _LIBRARY_TTL):
            items_src = _library_cache['items']
        else:
            # Light scan: just filenames + plex cache, no resolution probing
            items_src = []
            for root, _, files in os.walk(movies_dir):
                for file in files:
                    ext = os.path.splitext(file)[1].lower()
                    if ext not in VIDEO_EXTENSIONS:
                        continue
                    full_path = os.path.join(root, file)
                    try:
                        size = os.path.getsize(full_path)
                    except OSError:
                        size = 0
                    res = get_resolution_from_file(full_path)
                    parsed_title, parsed_year = parse_movie_title(file)
                    norm_path = _norm(full_path)
                    plex_data = _plex_cache.get(norm_path, {})
                    items_src.append({
                        'path': full_path,
                        'resolution': res,
                        'size_human': format_size(size),
                        'plex_title': plex_data.get('plex_title', ''),
                        'plex_year': str(plex_data.get('plex_year', '')),
                        'plex_matched': bool(plex_data),
                        '_parsed_title': parsed_title,
                        '_parsed_year': parsed_year,
                    })

        for item in items_src:
            # Prefer Plex-matched title/year as primary key
            if item.get('plex_matched') and item.get('plex_title'):
                key = (_norm_title(item['plex_title']), str(item.get('plex_year', '')).strip())
            else:
                key = (_norm_title(item.get('_parsed_title') or item.get('title', '')),
                       str(item.get('_parsed_year') or '').strip())
            # Keep the highest-resolution copy per title
            existing = lookup.get(key)
            cur_rank = get_resolution_rank_str(item['resolution'])
            if existing is None or cur_rank > get_resolution_rank_str(existing['resolution']):
                lookup[key] = {
                    'path': item['path'],
                    'resolution': item['resolution'],
                    'size_human': item['size_human'],
                }

        results = []
        for q in queries:
            qt = _norm_title(q.get('title', ''))
            qy = str(q.get('year', '')).strip()
            # Try with year first, then without (year may be off by 1 from TMDB)
            match = lookup.get((qt, qy))
            if match is None:
                # year-agnostic fallback
                for (kt, ky), v in lookup.items():
                    if kt == qt:
                        match = v
                        break
            if match:
                results.append({
                    'title': q.get('title', ''),
                    'year': q.get('year', ''),
                    'found': True,
                    'path': match['path'],
                    'resolution': match['resolution'],
                    'size_human': match['size_human'],
                })
            else:
                results.append({
                    'title': q.get('title', ''),
                    'year': q.get('year', ''),
                    'found': False,
                    'path': '',
                    'resolution': '',
                    'size_human': '',
                })
        return jsonify({'results': results})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/low-quality')
def low_quality():
    # Low quality = anything below 1080p (720p, 480p, Unknown resolution)
    MIN_RES_RANK = 3   # 1080p — only files BELOW this rank are flagged
    try:
        _auto_sync_plex(force=request.args.get('force_plex') == '1')
        movies_dir = get_movies_dir()
        items = []
        for root, dirs, files in os.walk(movies_dir):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext not in VIDEO_EXTENSIONS:
                    continue
                full_path = os.path.join(root, file)
                try:
                    size = os.path.getsize(full_path)
                except OSError:
                    size = 0
                res = get_resolution_from_file(full_path)
                res_rank = get_resolution_rank_str(res)
                rip = get_rip_source(file)
                rip_rank = get_rip_rank(rip)
                title_key = parse_movie_title(file)
                if not title_key[0]:
                    continue
                is_low = res_rank < MIN_RES_RANK
                if is_low:
                    display_title = title_key[0].title() + (f' ({title_key[1]})' if title_key[1] else '')
                    norm_path = _norm(full_path)
                    plex_data = _plex_cache.get(norm_path, {})
                    items.append({
                        'title': display_title,
                        'filename': file,
                        'path': full_path,
                        'resolution': res,
                        'rip_source': rip,
                        'size': size,
                        'size_human': format_size(size),
                        'plex_title': plex_data.get('plex_title', ''),
                        'plex_year': plex_data.get('plex_year', ''),
                        'plex_genres': plex_data.get('plex_genres', []),
                        'plex_matched': bool(plex_data),
                    })
        items.sort(key=lambda x: x['title'])
        return jsonify({'items': items, 'count': len(items),
                        'plex_enabled': bool(_plex_token), 'plex_cached': len(_plex_cache) > 0})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/smart-scan')
def smart_scan():
    try:
        duplicates, _ = scan_duplicates(get_movies_dir())
        recommendations = []

        for group in duplicates:
            files = group['files']  # sorted best first by (resolution_rank, size)
            best = files[0]
            best_res_rank = best['resolution_rank']
            best_rip_rank = get_rip_rank(best['rip_source'])

            for f in files[1:]:
                reason = None
                skip_reason = None

                if f['resolution_rank'] < best_res_rank:
                    reason = f"Lower resolution ({f['resolution']} vs {best['resolution']})"

                elif f['resolution_rank'] == best_res_rank:
                    f_rip_rank = get_rip_rank(f['rip_source'])
                    if f_rip_rank < best_rip_rank:
                        if best['size'] > 0 and f['size'] > 0:
                            size_diff_pct = abs(best['size'] - f['size']) / max(best['size'], f['size']) * 100
                            if size_diff_pct < 5:
                                reason = f"Inferior source ({f['rip_source']} vs {best['rip_source']})"
                            else:
                                skip_reason = (
                                    f"Same resolution ({f['resolution']}) but inferior source "
                                    f"({f['rip_source']} vs {best['rip_source']}) — "
                                    f"size difference is {size_diff_pct:.1f}% (≥5%), manual review recommended"
                                )

                if reason:
                    recommendations.append({
                        'movie': group['title'],
                        'delete_path': f['path'],
                        'delete_filename': f['filename'],
                        'delete_resolution': f['resolution'],
                        'delete_rip': f['rip_source'],
                        'delete_size': f['size_human'],
                        'keep_filename': best['filename'],
                        'keep_resolution': best['resolution'],
                        'keep_rip': best['rip_source'],
                        'keep_size': best['size_human'],
                        'reason': reason,
                    })
                elif skip_reason:
                    recommendations.append({
                        'movie': group['title'],
                        'delete_path': None,  # skipped
                        'delete_filename': f['filename'],
                        'delete_resolution': f['resolution'],
                        'delete_rip': f['rip_source'],
                        'delete_size': f['size_human'],
                        'keep_filename': best['filename'],
                        'keep_resolution': best['resolution'],
                        'keep_rip': best['rip_source'],
                        'keep_size': best['size_human'],
                        'reason': skip_reason,
                        'skipped': True,
                    })

        return jsonify({'recommendations': recommendations})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/stats')
def library_stats():
    try:
        _auto_sync_plex(force=request.args.get('force_plex') == '1')
        movies_dir = get_movies_dir()
        all_files = []
        title_set = set()
        by_resolution = {}
        by_source = {}
        by_decade = {}
        RES_RANK = {'4K': 4, '1080p': 3, '720p': 2, '480p': 1, 'Unknown': 0}

        for root, dirs, files in os.walk(movies_dir):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext not in VIDEO_EXTENSIONS:
                    continue
                full_path = os.path.join(root, file)
                try:
                    size = os.path.getsize(full_path)
                except OSError:
                    size = 0
                res = get_resolution_from_file(full_path)
                rip = get_rip_source(file)
                title_key = parse_movie_title(file)
                if not title_key[0]:
                    continue
                title_set.add(title_key)
                display_title = title_key[0].title() + (f' ({title_key[1]})' if title_key[1] else '')
                all_files.append({
                    'title': display_title,
                    'path': full_path,
                    'size': size,
                    'size_human': format_size(size),
                    'resolution': res,
                    'rip_source': rip,
                    'year': title_key[1],
                })
                # by resolution
                br = by_resolution.setdefault(res, {'count': 0, 'size': 0})
                br['count'] += 1
                br['size'] += size
                # by source
                bs = by_source.setdefault(rip, {'count': 0, 'size': 0})
                bs['count'] += 1
                bs['size'] += size
                # by decade
                if title_key[1]:
                    try:
                        decade = f"{(int(title_key[1]) // 10) * 10}s"
                    except ValueError:
                        decade = 'Unknown'
                else:
                    decade = 'Unknown'
                by_decade[decade] = by_decade.get(decade, 0) + 1

        # Duplicates
        duplicates, dup_stats = scan_duplicates(movies_dir)

        # Low quality count
        lq_count = sum(1 for f in all_files if RES_RANK.get(f['resolution'], 0) < 3)

        total_size = sum(f['size'] for f in all_files)
        avg_size = total_size // len(all_files) if all_files else 0

        # Format sizes
        for k in by_resolution:
            by_resolution[k]['size_human'] = format_size(by_resolution[k]['size'])
        for k in by_source:
            by_source[k]['size_human'] = format_size(by_source[k]['size'])

        top_largest = sorted(all_files, key=lambda x: x['size'], reverse=True)[:10]

        plex_matched = None
        plex_unmatched = None
        if _plex_cache:
            plex_matched = sum(1 for f in all_files if _norm(f['path']) in _plex_cache)
            plex_unmatched = len(all_files) - plex_matched

        return jsonify({
            'total_files': len(all_files),
            'unique_titles': len(title_set),
            'total_size': total_size,
            'total_size_human': format_size(total_size),
            'avg_size': avg_size,
            'avg_size_human': format_size(avg_size),
            'duplicate_groups': dup_stats['groups'],
            'extra_copies': dup_stats['extra_copies'],
            'wasted_bytes': dup_stats['wasted_bytes'],
            'wasted_human': dup_stats['wasted_human'],
            'low_quality_count': lq_count,
            'by_resolution': by_resolution,
            'by_source': by_source,
            'by_decade': by_decade,
            'top_largest': top_largest,
            'plex_matched': plex_matched,
            'plex_unmatched': plex_unmatched,
            'plex_enabled': bool(_plex_token),
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── Fix Unmatched ──────────────────────────────────────────────────────────────

def _plex_rescan():
    """Trigger a Plex library refresh for all movie sections. Silent on errors."""
    if not _plex_url or not _plex_token or not _plex_section_ids:
        return
    for sid in _plex_section_ids:
        try:
            url = f"{_plex_url}/library/sections/{sid}/refresh?X-Plex-Token={_plex_token}"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=5):
                pass
        except Exception:
            pass


def _fmt_size(n):
    for unit in ('B', 'KB', 'MB', 'GB'):
        if n < 1024:
            return f'{n:.0f} {unit}'
        n /= 1024
    return f'{n:.1f} TB'


@app.route('/api/fix-unmatched')
def fix_unmatched():
    try:
        _auto_sync_plex(force=request.args.get('force_plex') == '1')
        movies_dir = get_movies_dir()
        items = []
        for root, dirs, files in os.walk(movies_dir):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext not in VIDEO_EXTENSIONS:
                    continue
                full_path  = os.path.join(root, file)
                norm_path  = _norm(full_path)
                fname_lower = file.lower()
                # Skip if already matched — full-path lookup first, filename fallback second
                if norm_path in _plex_cache or fname_lower in _plex_matched_by_fname:
                    continue
                title_key = parse_movie_title(file)
                unparseable = not title_key[0]
                suggested_title = title_key[0].title() if title_key[0] else ''
                suggested_year  = title_key[1] if title_key else ''
                orig_res = get_resolution_from_file(full_path)
                orig_rip = get_rip_source(file)
                quality_tag = ' '.join(t for t in [orig_res, orig_rip] if t and t != 'Unknown')
                suggested_name = suggested_title + (f' ({suggested_year})' if suggested_year else '')
                if quality_tag:
                    suggested_name += f' [{quality_tag}]'
                suggested_name += ext
                # Look up Plex entry — full-path first, filename fallback second
                plex_entry = _plex_unmatched.get(norm_path) or \
                             _plex_unmatched_by_fname.get(fname_lower, {})
                rel_depth = len(os.path.relpath(full_path, movies_dir).split(os.sep)) - 1
                # Build a diagnostic hint so the UI can explain WHY the file is unmatched
                if plex_entry:
                    plex_hint = 'Plex found the file but has no metadata match — use Match in Plex'
                elif rel_depth > 1:
                    plex_hint = (f'Folder is {rel_depth} levels deep — Plex skips it. '
                                 'Use Fix Path to move it up')
                elif unparseable:
                    plex_hint = 'Filename cannot be parsed — rename it so Plex can identify it'
                else:
                    plex_hint = 'Plex has not indexed this file yet — try Scan Plex Library'
                items.append({
                    'filename': file,
                    'path': full_path,
                    'suggested_title': suggested_title,
                    'suggested_year':  suggested_year,
                    'suggested_name':  suggested_name,
                    'resolution': orig_res,
                    'rip_source': orig_rip,
                    'file_size': _fmt_size(os.path.getsize(full_path)),
                    'folder':    root,
                    'depth': rel_depth,
                    'fixable_path': rel_depth > 1,
                    'in_plex':    bool(plex_entry),
                    'rating_key': plex_entry.get('rating_key', ''),
                    'plex_title': plex_entry.get('plex_title', ''),
                    'unparseable': unparseable,
                    'plex_hint':   plex_hint,
                })
        items.sort(key=lambda x: x['filename'].lower())
        return jsonify({'items': items, 'count': len(items),
                        'plex_enabled': bool(_plex_token)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/rename-file', methods=['POST'])
def rename_file():
    data = request.get_json(silent=True)
    if not data or 'path' not in data:
        return jsonify({'error': 'No path provided'}), 400
    old_path  = data['path']
    new_title = data.get('title', '').strip()
    new_year  = data.get('year', '').strip()
    if not new_title:
        return jsonify({'error': 'Title is required'}), 400

    abs_old = os.path.abspath(old_path)
    abs_dir = os.path.abspath(get_movies_dir())
    if not abs_old.startswith(abs_dir + os.sep):
        return jsonify({'error': 'Path is outside the allowed movies directory'}), 403
    if not os.path.isfile(abs_old):
        return jsonify({'error': 'File not found'}), 404

    ext = os.path.splitext(abs_old)[1]
    orig_basename = os.path.basename(abs_old)
    orig_res = get_resolution_from_file(abs_old)
    orig_rip = get_rip_source(orig_basename)
    quality_tag = ' '.join(t for t in [orig_res, orig_rip] if t and t != 'Unknown')
    new_filename = new_title + (f' ({new_year})' if new_year else '')
    if quality_tag:
        new_filename += f' [{quality_tag}]'
    new_filename += ext
    # Strip characters not allowed in Windows filenames
    new_filename = re.sub(r'[<>:"/\\|?*]', '', new_filename).strip()
    new_path = os.path.join(os.path.dirname(abs_old), new_filename)

    if os.path.exists(new_path) and os.path.normpath(new_path) != os.path.normpath(abs_old):
        return jsonify({'error': f'A file named "{new_filename}" already exists in that folder'}), 409

    try:
        os.rename(abs_old, new_path)
        # Remove old path from caches
        old_norm = _norm(abs_old)
        _plex_cache.pop(old_norm, None)
        _plex_unmatched.pop(old_norm, None)
        _library_cache.pop('items', None)  # bust library cache — filename/path changed
        # Ask Plex to rescan so it picks up the renamed file
        _plex_rescan()
        return jsonify({'success': True, 'new_path': new_path, 'new_filename': new_filename})
    except OSError as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/plex/force-scan', methods=['POST'])
def plex_force_scan():
    global _plex_cache_time
    if not _plex_url or not _plex_token:
        return jsonify({'error': 'Plex not configured'}), 400
    try:
        _plex_rescan()
        _plex_cache_time = 0.0
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/fix-path', methods=['POST'])
def fix_path():
    """Move a file (or its containing folder) one directory level up so Plex can find it.
    When the parent folder contains only this one video file, the whole folder is moved
    so Plex retains the folder-name metadata hint (e.g. 'Batman (2010)') after the move.
    Only allowed on files that are NOT already in Plex's matched cache."""
    data = request.get_json(silent=True)
    if not data or 'path' not in data:
        return jsonify({'error': 'No path provided'}), 400

    abs_path = os.path.abspath(data['path'])
    abs_dir  = os.path.abspath(get_movies_dir())
    if not abs_path.startswith(abs_dir + os.sep):
        return jsonify({'error': 'Path is outside the allowed movies directory'}), 403
    if not os.path.isfile(abs_path):
        return jsonify({'error': 'File not found'}), 404

    # Safety: refuse to move files Plex already matched (full-path check + filename fallback)
    norm = _norm(abs_path)
    fname_lower = os.path.basename(abs_path).lower()
    if norm in _plex_cache or fname_lower in _plex_matched_by_fname:
        return jsonify({'error': 'This file is already matched in Plex — not moving it'}), 409

    parent      = os.path.dirname(abs_path)
    grandparent = os.path.dirname(parent)

    # Grandparent must still be inside (or equal to) the movies root
    if not (os.path.normpath(grandparent) == os.path.normpath(abs_dir) or
            os.path.normpath(grandparent).startswith(os.path.normpath(abs_dir) + os.sep)):
        return jsonify({'error': 'Cannot move file — destination would be outside library'}), 400

    # Decide: move entire folder or just the file?
    # Count video files in parent to decide.
    _JUNK = {'desktop.ini', 'thumbs.db', '.ds_store', 'folder.jpg', 'folder.png'}
    try:
        sibling_videos = [
            f for f in os.listdir(parent)
            if os.path.splitext(f)[1].lower() in VIDEO_EXTENSIONS
        ]
    except OSError:
        sibling_videos = [os.path.basename(abs_path)]

    try:
        parent_name = os.path.basename(parent)
        # Use whole-folder move only when:
        #   1. There is exactly one video in the folder (folder acts as a Plex hint), AND
        #   2. The folder name contains a year — i.e. it looks like a movie title.
        # Generic names like "Downloads", "1080p", "Featurettes" would be useless as a hint.
        use_folder_move = (len(sibling_videos) == 1 and
                           bool(_MOVIE_FOLDER_RE.search(parent_name)))

        if use_folder_move:
            # ── Whole-folder move ────────────────────────────────────────────
            # Move the folder one level up so Plex can discover it using the
            # folder name (e.g. "Batman (2010)") as a metadata hint.
            great_grandparent = os.path.dirname(grandparent)
            dest_folder = os.path.join(great_grandparent, parent_name)
            if os.path.normpath(dest_folder) == os.path.normpath(parent):
                return jsonify({'error': 'File is already at the correct depth — no move needed'}), 409
            if os.path.exists(dest_folder):
                return jsonify({'error': f'A folder named "{parent_name}" already exists in the destination'}), 409
            os.rename(parent, dest_folder)
            new_path = os.path.join(dest_folder, os.path.basename(abs_path))
            _plex_cache.pop(norm, None)
            _plex_unmatched.pop(norm, None)
        else:
            # ── File-only move (multiple videos, or generic folder name) ──────
            new_path = os.path.join(grandparent, os.path.basename(abs_path))
            if os.path.normpath(new_path) == os.path.normpath(abs_path):
                return jsonify({'error': 'File is already at the correct depth — no move needed'}), 409
            if os.path.exists(new_path):
                return jsonify({'error': f'A file named "{os.path.basename(abs_path)}" already exists in the destination folder'}), 409
            os.rename(abs_path, new_path)
            # Try to clean up junk files and remove folder if now empty
            try:
                for f in os.listdir(parent):
                    if f.lower() in _JUNK:
                        try:
                            os.remove(os.path.join(parent, f))
                        except OSError:
                            pass
            except OSError:
                pass
            try:
                os.rmdir(parent)
            except OSError:
                pass
            _plex_cache.pop(norm, None)
            _plex_unmatched.pop(norm, None)

        # Ask Plex to rescan so it picks up the new location
        _plex_rescan()
        return jsonify({'success': True, 'new_path': new_path})
    except OSError as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/plex/match-search')
def plex_match_search():
    if not _plex_url or not _plex_token:
        return jsonify({'error': 'Plex not configured'}), 400
    rating_key = request.args.get('rating_key', '').strip()
    title      = request.args.get('title', '').strip()
    year       = request.args.get('year', '').strip()
    if not rating_key:
        return jsonify({'error': 'rating_key is required'}), 400
    try:
        params = {k: v for k, v in {'title': title, 'year': year}.items() if v}
        qs = urllib.parse.urlencode(params)
        sep = '&' if qs else '?'
        url = f"{_plex_url}/library/metadata/{rating_key}/matches?{qs}{sep}X-Plex-Token={_plex_token}"
        req = urllib.request.Request(url, headers={'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = _json.loads(resp.read().decode())
        results = []
        for r in data.get('MediaContainer', {}).get('SearchResult', []):
            results.append({
                'name':  r.get('name', ''),
                'year':  str(r.get('year', '')),
                'guid':  r.get('guid', ''),
                'score': r.get('score', 0),
            })
        return jsonify({'results': results})
    except urllib.error.HTTPError as e:
        return jsonify({'error': f'Plex returned HTTP {e.code}'}), 502
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/plex/match-apply', methods=['POST'])
def plex_match_apply():
    global _plex_cache_time
    if not _plex_url or not _plex_token:
        return jsonify({'error': 'Plex not configured'}), 400
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    rating_key = data.get('rating_key', '').strip()
    guid       = data.get('guid', '').strip()
    name       = data.get('name', '').strip()
    if not rating_key or not guid:
        return jsonify({'error': 'rating_key and guid are required'}), 400
    try:
        # Apply the match
        params = urllib.parse.urlencode({'guid': guid, 'name': name})
        url = f"{_plex_url}/library/metadata/{rating_key}/match?{params}&X-Plex-Token={_plex_token}"
        req = urllib.request.Request(url, method='PUT')
        req.add_header('Content-Length', '0')
        with urllib.request.urlopen(req, timeout=15):
            pass
        # Refresh the item's metadata from the agent
        url2 = f"{_plex_url}/library/metadata/{rating_key}/refresh?X-Plex-Token={_plex_token}"
        req2 = urllib.request.Request(url2, method='PUT')
        req2.add_header('Content-Length', '0')
        with urllib.request.urlopen(req2, timeout=10):
            pass
        # Force plex cache refresh next time
        _plex_cache_time = 0.0
        return jsonify({'success': True})
    except urllib.error.HTTPError as e:
        return jsonify({'error': f'Plex returned HTTP {e.code}'}), 502
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── TMDB / Trending ──────────────────────────────────────────────────────────

@app.route('/api/tmdb/config', methods=['GET'])
def get_tmdb_config():
    return jsonify({'key': _tmdb_key})


@app.route('/api/tmdb/config', methods=['POST'])
def set_tmdb_config():
    global _tmdb_key, _tmdb_genres
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    _tmdb_key = data.get('key', '').strip()
    _tmdb_genres = {}  # reset genre cache when key changes
    _save_config(_all_config())
    return jsonify({'success': True})


@app.route('/api/tmdb/test')
def tmdb_test():
    key = request.args.get('key', _tmdb_key).strip()
    if not key:
        return jsonify({'error': 'No API key — enter your TMDB key in Settings.'}), 400
    try:
        url = f"https://api.themoviedb.org/3/configuration?api_key={urllib.parse.quote(key)}"
        req = urllib.request.Request(url, headers={'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=8) as resp:
            _json.loads(resp.read().decode())
        return jsonify({'success': True})
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return jsonify({'error': 'Invalid API key — check your TMDB account settings.'}), 401
        return jsonify({'error': f'TMDB returned HTTP {e.code}'}), 502
    except Exception as e:
        return jsonify({'error': f'Cannot reach TMDB: {e}'}), 502


def _ensure_tmdb_genres():
    """Lazy-load TMDB genre list into _tmdb_genres. Silent on error."""
    global _tmdb_genres
    if _tmdb_genres or not _tmdb_key:
        return
    try:
        url = f"https://api.themoviedb.org/3/genre/movie/list?api_key={urllib.parse.quote(_tmdb_key)}&language=en"
        req = urllib.request.Request(url, headers={'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = _json.loads(resp.read().decode())
        _tmdb_genres = {g['id']: g['name'] for g in data.get('genres', [])}
    except Exception:
        pass


@app.route('/api/metadata')
def get_metadata():
    title = request.args.get('title', '').strip()
    year  = request.args.get('year', '').strip()
    if not title:
        return jsonify({'error': 'title is required'}), 400
    cache_key = f"{title.lower()}_{year}"
    if cache_key in _metadata_cache:
        return jsonify(_metadata_cache[cache_key])
    if not _tmdb_key:
        return jsonify({'poster_url': '', 'genres': [], 'plot': '', 'tmdb_rating': ''})
    _ensure_tmdb_genres()
    try:
        params = urllib.parse.urlencode({'query': title, 'api_key': _tmdb_key, 'language': 'en-US', 'page': 1})
        if year:
            params += '&year=' + urllib.parse.quote(year)
        url = f"https://api.themoviedb.org/3/search/movie?{params}"
        req = urllib.request.Request(url, headers={'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = _json.loads(resp.read().decode())
        results = data.get('results', [])
        result = results[0] if results else {}
        poster_path = result.get('poster_path', '')
        poster_url  = f"https://image.tmdb.org/t/p/w342{poster_path}" if poster_path else ''
        genre_ids   = result.get('genre_ids', [])
        genres      = [_tmdb_genres[gid] for gid in genre_ids if gid in _tmdb_genres][:3]
        plot        = result.get('overview', '')
        vote        = result.get('vote_average', 0)
        tmdb_rating = f"{vote:.1f}" if isinstance(vote, (int, float)) and vote else ''
        meta = {'poster_url': poster_url, 'genres': genres, 'plot': plot, 'tmdb_rating': tmdb_rating, 'tmdb_id': result.get('id', None)}
        _metadata_cache[cache_key] = meta
        return jsonify(meta)
    except urllib.error.HTTPError as e:
        return jsonify({'error': f'TMDB returned HTTP {e.code}'}), 502
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/explore/browse')
def explore_browse():
    if not _prowlarr_url or not _prowlarr_key:
        return jsonify({'error': 'Prowlarr not configured — click ⚙ Settings to enter your Prowlarr URL and API key.'}), 400
    try:
        # Fetch all enabled indexer IDs
        indexer_ids   = []
        indexer_names = []
        try:
            idx_req = urllib.request.Request(
                f"{_prowlarr_url}/api/v1/indexer",
                headers={'X-Api-Key': _prowlarr_key, 'Accept': 'application/json'}
            )
            with urllib.request.urlopen(idx_req, timeout=8) as idx_resp:
                indexers = _json.loads(idx_resp.read().decode())
            for ix in indexers:
                if ix.get('enable', True):
                    indexer_ids.append(str(ix['id']))
                    indexer_names.append(ix.get('name', ''))
        except Exception:
            pass

        def _fetch(query=''):
            parts = [('query', query), ('type', 'search'), ('categories', '2000'), ('limit', '100')]
            parts += [('indexerIds', iid) for iid in indexer_ids]
            url = f"{_prowlarr_url}/api/v1/search?{urllib.parse.urlencode(parts)}"
            req = urllib.request.Request(url, headers={'X-Api-Key': _prowlarr_key, 'Accept': 'application/json'})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return _json.loads(resp.read().decode())

        results = _fetch('')
        if len(results) < 20:
            fallback = _fetch('2025')
            if len(fallback) > len(results):
                results = fallback

        # Build deduplicated movie list
        movies = {}  # key -> {parsed_title, parsed_year, variants[]}
        for r in results:
            title = r.get('title', '')
            # Skip TV episodes
            if _TV_RE.search(title):
                continue
            tl = title.lower()
            res = 'Unknown'
            if '2160p' in tl or '4k' in tl or 'uhd' in tl:
                res = '4K'
            elif '1080p' in tl or re.search(r'[\.\-_ \[\(]1080[\.\-_ \]\)\[]', tl):
                res = '1080p'
            elif '720p' in tl or re.search(r'[\.\-_ \[\(]720[\.\-_ \]\)\[]', tl):
                res = '720p'
            elif '480p' in tl or re.search(r'[\.\-_ \[\(]480[\.\-_ \]\)\[]', tl):
                res = '480p'
            parsed = parse_movie_title(title)
            parsed_title = parsed[0].title() if parsed[0] else title
            parsed_year  = parsed[1] or ''
            size = r.get('size', 0)
            variant = {
                'resolution': res,
                'seeders': r.get('seeders', 0),
                'magnet_url': r.get('magnetUrl', ''),
                'download_url': r.get('downloadUrl', ''),
                'info_url': r.get('infoUrl', ''),
                'indexer': r.get('indexer', ''),
                'size_human': format_size(size) if size else '?',
                'title': title,
            }
            key = f"{parsed_title.lower()}_{parsed_year}"
            if key not in movies:
                movies[key] = {'parsed_title': parsed_title, 'parsed_year': parsed_year, 'variants': [variant]}
            else:
                movies[key]['variants'].append(variant)

        # Sort variants within each movie by seeders desc; deduplicate by resolution (keep best per res)
        processed = []
        for m in movies.values():
            by_res = {}
            for v in m['variants']:
                r = v['resolution']
                if r not in by_res or v['seeders'] > by_res[r]['seeders']:
                    by_res[r] = v
            RES_ORDER = ['4K', '1080p', '720p', '480p', 'Unknown']
            variants  = [by_res[r] for r in RES_ORDER if r in by_res]
            best = variants[0]
            processed.append({
                'parsed_title': m['parsed_title'],
                'parsed_year':  m['parsed_year'],
                'best_seeders': best['seeders'],
                'best_resolution': best['resolution'],
                'indexer': best['indexer'],
                'variants': variants,
            })

        processed.sort(key=lambda x: x['best_seeders'], reverse=True)
        return jsonify({'results': processed[:100], 'tmdb_enabled': bool(_tmdb_key), 'all_indexers': sorted(indexer_names)})
    except urllib.error.HTTPError as e:
        return jsonify({'error': f'Prowlarr returned HTTP {e.code}'}), 502
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/tmdb/discover')
def tmdb_discover():
    if not _tmdb_key:
        return jsonify({'error': 'TMDB key not configured — add it in ⚙ Settings.'}), 400
    list_name = request.args.get('list', 'trending_week')
    genre_id  = request.args.get('genre', '').strip()
    try:
        page = max(1, min(int(request.args.get('page', '1')), 10))
    except ValueError:
        page = 1

    # Sort strategy per list when using genre filter via /discover/movie
    _list_sort = {
        'trending_week': 'popularity.desc',
        'trending_today': 'popularity.desc',
        'now_playing':   'popularity.desc',
        'popular':       'popularity.desc',
        'upcoming':      'primary_release_date.desc',
        'top_rated':     'vote_average.desc',
        'best_all_time': 'vote_count.desc',
    }

    _ensure_tmdb_genres()
    try:
        if genre_id:
            # All genre-filtered lists go through /discover/movie
            sort_by = _list_sort.get(list_name, 'popularity.desc')
            params = urllib.parse.urlencode({
                'api_key':        _tmdb_key,
                'language':       'en-US',
                'sort_by':        sort_by,
                'with_genres':    genre_id,
                'vote_count.gte': '50',
                'page':           page,
            })
            if list_name == 'top_rated':
                params += '&vote_average.gte=6.0'
            elif list_name == 'best_all_time':
                params += '&vote_average.gte=7.5&vote_count.gte=5000'
            url = f"https://api.themoviedb.org/3/discover/movie?{params}"
        elif list_name == 'best_all_time':
            params = urllib.parse.urlencode({
                'api_key':            _tmdb_key,
                'language':           'en-US',
                'sort_by':            'vote_count.desc',
                'vote_average.gte':   '7.5',
                'vote_count.gte':     '5000',
                'page':               page,
            })
            url = f"https://api.themoviedb.org/3/discover/movie?{params}"
        elif list_name == 'trending_today':
            url = (f"https://api.themoviedb.org/3/trending/movie/day"
                   f"?api_key={urllib.parse.quote(_tmdb_key)}&language=en-US&page={page}")
        else:
            endpoint_map = {
                'trending_week': 'https://api.themoviedb.org/3/trending/movie/week',
                'now_playing':   'https://api.themoviedb.org/3/movie/now_playing',
                'popular':       'https://api.themoviedb.org/3/movie/popular',
                'upcoming':      'https://api.themoviedb.org/3/movie/upcoming',
                'top_rated':     'https://api.themoviedb.org/3/movie/top_rated',
            }
            base_url = endpoint_map.get(list_name, endpoint_map['trending_week'])
            url = f"{base_url}?api_key={urllib.parse.quote(_tmdb_key)}&language=en-US&page={page}"

        req = urllib.request.Request(url, headers={'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = _json.loads(resp.read().decode())
        movies = []
        for m in data.get('results', []):
            poster_path = m.get('poster_path', '')
            release = m.get('release_date', '') or ''
            year    = release[:4] if release else ''
            genre_ids = m.get('genre_ids', [])
            genres  = [_tmdb_genres[gid] for gid in genre_ids if gid in _tmdb_genres][:3]
            vote    = m.get('vote_average', 0)
            lang    = m.get('original_language', '')
            countries = m.get('origin_country', [])
            country_code = countries[0] if countries else _LANG_COUNTRY.get(lang, '')
            movies.append({
                'tmdb_id':    m.get('id'),
                'title':      m.get('title', ''),
                'year':       year,
                'poster_url': f"https://image.tmdb.org/t/p/w342{poster_path}" if poster_path else '',
                'genres':     genres,
                'tmdb_rating': f"{vote:.1f}" if isinstance(vote, (int, float)) and vote else '',
                'plot':       m.get('overview', ''),
                'language':   _LANG_NAMES.get(lang, lang.upper() if lang else ''),
                'country':    country_code,
                'country_flag': _country_flag(country_code),
            })
        return jsonify({'results': movies, 'total_pages': min(data.get('total_pages', 1), 10), 'page': page})
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return jsonify({'error': 'Invalid TMDB API key — check Settings.'}), 401
        return jsonify({'error': f'TMDB returned HTTP {e.code}'}), 502
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/explore/search')
def explore_search():
    title = request.args.get('title', '').strip()
    year  = request.args.get('year', '').strip()
    if not title:
        return jsonify({'error': 'title required'}), 400
    if not _prowlarr_url or not _prowlarr_key:
        return jsonify({'error': 'Prowlarr not configured — add it in ⚙ Settings.'}), 400
    query = f"{title} {year}".strip()
    try:
        indexer_ids = []
        try:
            idx_req = urllib.request.Request(
                f"{_prowlarr_url}/api/v1/indexer",
                headers={'X-Api-Key': _prowlarr_key, 'Accept': 'application/json'}
            )
            with urllib.request.urlopen(idx_req, timeout=8) as idx_resp:
                indexers = _json.loads(idx_resp.read().decode())
            indexer_ids = [str(ix['id']) for ix in indexers if ix.get('enable', True)]
        except Exception:
            pass
        parts = [('query', query), ('type', 'search'), ('categories', '2000'), ('limit', '100')]
        parts += [('indexerIds', iid) for iid in indexer_ids]
        url = f"{_prowlarr_url}/api/v1/search?{urllib.parse.urlencode(parts)}"
        req = urllib.request.Request(url, headers={'X-Api-Key': _prowlarr_key, 'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=30) as resp:
            results = _json.loads(resp.read().decode())
        hd_variants = []
        fallback_variants = []
        for r in results:
            t = r.get('title', '')
            if _TV_RE.search(t):
                continue
            tl = t.lower()
            res = 'Unknown'
            if '2160p' in tl or '4k' in tl or 'uhd' in tl:
                res = '4K'
            elif '1080p' in tl or re.search(r'[.\-_ \[(]1080[.\-_ \])]', tl):
                res = '1080p'
            elif '720p' in tl or re.search(r'[.\-_ \[(]720[.\-_ \])]', tl):
                res = '720p'
            elif '480p' in tl or re.search(r'[.\-_ \[(]480[.\-_ \])]', tl):
                res = '480p'
            size = r.get('size', 0)
            seeders = r.get('seeders', 0)
            entry = {
                'resolution': res, 'seeders': seeders,
                'magnet_url': r.get('magnetUrl', ''),
                'download_url': r.get('downloadUrl', ''),
                'info_url': r.get('infoUrl', ''),
                'indexer': r.get('indexer', ''),
                'size_human': format_size(size) if size else '?',
                'size_bytes': size,
                'title': t,
            }
            if res in ('4K', '1080p'):
                hd_variants.append(entry)
            else:
                fallback_variants.append(entry)
        # Sort: 4K first, then 1080p, within group by seeders desc
        hd_variants.sort(key=lambda x: (0 if x['resolution'] == '4K' else 1, -x['seeders']))
        if hd_variants:
            variants = hd_variants
        else:
            fallback_variants.sort(key=lambda x: -x['seeders'])
            variants = fallback_variants
        return jsonify({'variants': variants})
    except urllib.error.HTTPError as e:
        return jsonify({'error': f'Prowlarr returned HTTP {e.code}'}), 502
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/tmdb/search')
def tmdb_search():
    if not _tmdb_key:
        return jsonify({'error': 'TMDB key not configured — add it in ⚙ Settings.'}), 400
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify({'error': 'q (query) parameter required'}), 400
    try:
        page = max(1, min(int(request.args.get('page', '1')), 10))
    except ValueError:
        page = 1
    _ensure_tmdb_genres()
    try:
        params = urllib.parse.urlencode({
            'query': q, 'api_key': _tmdb_key,
            'language': 'en-US', 'page': page, 'include_adult': 'false'
        })
        url = f"https://api.themoviedb.org/3/search/movie?{params}"
        req = urllib.request.Request(url, headers={'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = _json.loads(resp.read().decode())
        movies = []
        for m in data.get('results', []):
            poster_path = m.get('poster_path', '')
            release = m.get('release_date', '') or ''
            year    = release[:4] if release else ''
            genre_ids = m.get('genre_ids', [])
            genres  = [_tmdb_genres[gid] for gid in genre_ids if gid in _tmdb_genres][:3]
            vote    = m.get('vote_average', 0)
            lang    = m.get('original_language', '')
            country_code = _LANG_COUNTRY.get(lang, '')
            movies.append({
                'tmdb_id':    m.get('id'),
                'title':      m.get('title', ''),
                'year':       year,
                'poster_url': f"https://image.tmdb.org/t/p/w342{poster_path}" if poster_path else '',
                'genres':     genres,
                'tmdb_rating': f"{vote:.1f}" if isinstance(vote, (int, float)) and vote else '',
                'plot':       m.get('overview', ''),
                'language':   _LANG_NAMES.get(lang, lang.upper() if lang else ''),
                'country':    country_code,
                'country_flag': _country_flag(country_code),
            })
        return jsonify({
            'results': movies,
            'total_pages': min(data.get('total_pages', 1), 10),
            'page': page,
            'total_results': data.get('total_results', 0),
        })
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return jsonify({'error': 'Invalid TMDB API key — check Settings.'}), 401
        return jsonify({'error': f'TMDB returned HTTP {e.code}'}), 502
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/tmdb/imdb_id')
def tmdb_imdb_id():
    tmdb_id = request.args.get('tmdb_id', '').strip()
    if not tmdb_id or not _tmdb_key:
        return jsonify({'error': 'tmdb_id and TMDB key required'}), 400
    try:
        url = (f"https://api.themoviedb.org/3/movie/{urllib.parse.quote(str(tmdb_id))}"
               f"?api_key={urllib.parse.quote(_tmdb_key)}&language=en-US")
        req = urllib.request.Request(url, headers={'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = _json.loads(resp.read().decode())
        imdb_id = data.get('imdb_id', '')
        if not imdb_id:
            return jsonify({'error': 'No IMDB ID found for this title'}), 404
        return jsonify({'imdb_id': imdb_id})
    except urllib.error.HTTPError as e:
        return jsonify({'error': f'TMDB returned HTTP {e.code}'}), 502
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── Ollama / Pick My Movie ───────────────────────────────────────────────────

@app.route('/api/ollama/config', methods=['GET'])
def get_ollama_config():
    return jsonify({'url': _ollama_url, 'model': _ollama_model})


@app.route('/api/ollama/config', methods=['POST'])
def set_ollama_config():
    global _ollama_url, _ollama_model
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    _ollama_url   = data.get('url', 'http://localhost:11434').strip().rstrip('/')
    _ollama_model = data.get('model', '').strip()
    _save_config(_all_config())
    return jsonify({'success': True})


@app.route('/api/ollama/test')
def ollama_test():
    url = request.args.get('url', _ollama_url).strip().rstrip('/')
    if not url:
        return jsonify({'error': 'No Ollama URL configured — add it in Settings.'}), 400
    try:
        req = urllib.request.Request(f"{url}/api/tags", headers={'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=8) as resp:
            _json.loads(resp.read().decode())
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': f'Cannot reach Ollama: {e}'}), 502


def _ollama_enrich_with_tmdb(title, year):
    """Search TMDB for a single title and return enriched movie dict. Returns None on failure."""
    if not _tmdb_key:
        return None
    _ensure_tmdb_genres()
    try:
        params = urllib.parse.urlencode({
            'query': title, 'api_key': _tmdb_key,
            'language': 'en-US', 'page': 1, 'include_adult': 'false',
            **(({'year': year}) if year else {})
        })
        url = f"https://api.themoviedb.org/3/search/movie?{params}"
        req = urllib.request.Request(url, headers={'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = _json.loads(resp.read().decode())
        results = data.get('results', [])
        if not results:
            return None
        m = results[0]
        poster_path = m.get('poster_path', '')
        release = m.get('release_date', '') or ''
        yr = release[:4] if release else year
        genre_ids = m.get('genre_ids', [])
        genres = [_tmdb_genres[gid] for gid in genre_ids if gid in _tmdb_genres][:3]
        vote = m.get('vote_average', 0)
        lang = m.get('original_language', '')
        country_code = _LANG_COUNTRY.get(lang, '')
        return {
            'tmdb_id':      m.get('id'),
            'title':        m.get('title', title),
            'year':         yr,
            'poster_url':   f"https://image.tmdb.org/t/p/w342{poster_path}" if poster_path else '',
            'genres':       genres,
            'tmdb_rating':  f"{vote:.1f}" if isinstance(vote, (int, float)) and vote else '',
            'plot':         m.get('overview', ''),
            'language':     _LANG_NAMES.get(lang, lang.upper() if lang else ''),
            'country':      country_code,
            'country_flag': _country_flag(country_code),
        }
    except Exception:
        return None


@app.route('/api/ollama/recommend', methods=['POST'])
def ollama_recommend():
    if not _ollama_url or not _ollama_model:
        return jsonify({'error': 'Ollama not configured — add URL and model in Settings.'}), 400
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    prompt = data.get('prompt', '').strip()
    if not prompt:
        return jsonify({'error': 'Prompt cannot be empty.'}), 400

    system_msg = (
        'You are a movie recommendation expert. '
        'The user will describe a movie or what they want to watch by mood, memory, feeling, actors, or any detail. '
        'Return ONLY valid JSON with this exact shape: '
        '{"recommendations":[{"title":"...","year":"...","reason":"one sentence why this matches"}]}. '
        'Give exactly 5 recommendations. '
        'No markdown, no explanation, no extra text — only the JSON object.'
    )

    body = _json.dumps({
        'model': _ollama_model,
        'messages': [
            {'role': 'system', 'content': system_msg},
            {'role': 'user',   'content': prompt}
        ],
        'stream': False,
        'format': 'json'
    }).encode()

    try:
        req = urllib.request.Request(
            f"{_ollama_url}/api/chat",
            data=body,
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = _json.loads(resp.read().decode())
        parsed = _json.loads(raw['message']['content'])
        recs = parsed.get('recommendations', [])
    except _json.JSONDecodeError:
        return jsonify({'error': 'Ollama returned invalid JSON. Try a different prompt.'}), 502
    except urllib.error.HTTPError as e:
        return jsonify({'error': f'Ollama returned HTTP {e.code}'}), 502
    except Exception as e:
        return jsonify({'error': f'Cannot reach Ollama: {e}'}), 502

    results = []
    for rec in recs:
        title  = rec.get('title', '').strip()
        year   = rec.get('year', '').strip()
        reason = rec.get('reason', '')
        if not title:
            continue
        enriched = _ollama_enrich_with_tmdb(title, year)
        if enriched:
            enriched['reason'] = reason
            results.append(enriched)
        else:
            results.append({'title': title, 'year': year, 'reason': reason,
                            'poster_url': '', 'genres': [], 'tmdb_rating': '',
                            'plot': '', 'tmdb_id': None})

    return jsonify({'results': results, 'model': _ollama_model})


if __name__ == '__main__':
    app.run(debug=False, port=5000, use_reloader=True)
