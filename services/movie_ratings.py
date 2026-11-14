"""Plex ratings are optional display data, never a card-loading dependency."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re
import threading
import time
import uuid
from collections import OrderedDict, deque
from email.utils import parsedate_to_datetime
from .plex_transport import plex_json


_CRITIC_IMAGES = {'rottentomatoes://image.rating.ripe', 'rottentomatoes://image.rating.rotten'}
_AUDIENCE_IMAGES = {'rottentomatoes://image.rating.upright', 'rottentomatoes://image.rating.spilled'}


def _score(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return None
    try:
        number = Decimal(str(value))
        if number.is_finite() and 0 <= number <= 10:
            return int((number * 10).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    except (InvalidOperation, ValueError):
        pass
    return None


def normalize_plex_ratings(item):
    result = {'critics': None, 'audience': None}
    rows = item.get('Rating') if isinstance(item.get('Rating'), list) else []
    for field, role, images, scalar, marker in (
        ('critics', 'critic', _CRITIC_IMAGES, 'rating', 'ratingImage'),
        ('audience', 'audience', _AUDIENCE_IMAGES, 'audienceRating', 'audienceRatingImage'),
    ):
        tagged = [row for row in rows if isinstance(row, dict) and row.get('image') in images and row.get('type') == role]
        if tagged:
            values = {_score(row.get('value')) for row in tagged}
            if len(values) == 1:
                result[field] = values.pop()
        elif item.get(marker) in images:
            result[field] = _score(item.get(scalar))
    return result


def movie_identity(value):
    if not isinstance(value, dict) or value.get('type', 'movie') != 'movie':
        raise ValueError('invalid_movie_identity')
    out = {}
    for field, pattern in [('tmdb_id', r'[0-9]{1,12}'), ('imdb_id', r'tt[0-9]{5,12}'), ('plex_guid', r'plex://movie/[a-f0-9]{24}')]:
        raw = value.get(field)
        if raw is None or raw == '':
            continue
        text = str(raw).strip().lower()
        if isinstance(raw, bool) or not re.fullmatch(pattern, text):
            raise ValueError('invalid_movie_identity')
        if field == 'tmdb_id':
            if int(text) < 1:
                raise ValueError('invalid_movie_identity')
            text = str(int(text))
        out[field] = text
    aliases = []
    if out.get('tmdb_id'): aliases.append('movie:tmdb:' + out['tmdb_id'])
    if out.get('imdb_id'): aliases.append('movie:imdb:' + out['imdb_id'])
    if out.get('plex_guid'): aliases.append('movie:plex:' + out['plex_guid'].rsplit('/', 1)[-1])
    if not aliases:
        raise ValueError('missing_movie_identity')
    return {**out, 'key': aliases[0], 'aliases': aliases,
            'priority': 'expanded' if value.get('priority') == 'expanded' else 'visible'}


def plex_identity(item):
    if item.get('type', 'movie') != 'movie':
        raise ValueError('not_movie')
    ids = [item.get('guid', '')] + [g.get('id', '') for g in (item.get('Guid') or []) if isinstance(g, dict)]
    value = {}
    for ident in ids:
        for prefix, field in [('tmdb://', 'tmdb_id'), ('imdb://', 'imdb_id'), ('plex://movie/', 'plex_guid')]:
            if str(ident).startswith(prefix):
                candidate = ident if field == 'plex_guid' else ident[len(prefix):]
                if field in value and value[field] != candidate:
                    raise ValueError('conflicting_provider_ids')
                value[field] = candidate
    return movie_identity(value)


def matches_identity(identity, item):
    try:
        actual = plex_identity(item)
        return all(actual.get(field) == identity[field] for field in ('tmdb_id', 'imdb_id', 'plex_guid') if identity.get(field))
    except (ValueError, TypeError):
        return False


def _demand_key(identity):
    return '|'.join(str(identity.get(field) or '') for field in ('tmdb_id', 'imdb_id', 'plex_guid'))


class MovieRatingsService:
    """One bounded, lazy worker. Card APIs never call this provider synchronously."""
    def __init__(self, store, *, config, ownership, transport=plex_json, clock=time.time):
        self.store, self.config, self.ownership = store, config, ownership
        self.transport, self.clock = transport, clock
        self.owner = uuid.uuid4().hex
        self._condition = threading.Condition(threading.RLock())
        self._queue, self._snapshots, self._states = OrderedDict(), deque(maxlen=200), {}
        self._thread, self._stopped, self._active = None, False, None
        self._fingerprint = self._credentials()
        self._lease, self._retry, self._failures = 0, 0, 0
        self._local_lease, self._online_lease = 0, 0
        self._last_online_start = 0
        self._plex_state = 'unknown' if all(self._fingerprint) else 'not_configured'

    def _credentials(self):
        value = self.config() or {}
        return str(value.get('url') or '').rstrip('/'), str(value.get('token') or '')

    def invalidate_config(self):
        with self._condition:
            self._fingerprint = self._credentials()
            self.store.invalidate()
            self.owner = uuid.uuid4().hex
            self._queue.clear()
            self._snapshots.clear()
            self._states.clear()
            self._lease = self._retry = self._failures = 0
            self._local_lease = self._online_lease = 0
            self._plex_state = 'unknown' if all(self._fingerprint) else 'not_configured'

    def _check_config(self):
        if self._credentials() != self._fingerprint:
            self.invalidate_config()

    def _owned(self, items):
        try:
            return self.ownership(items) or {}
        except Exception:
            return {}  # An unavailable catalog cannot grant the offline exception.

    def read(self, items):
        with self._condition:
            self._check_config()
            owned = self._owned(items)
            cache_available = True
            try:
                saved = self.store.read_many([i['key'] for i in items])
            except Exception:
                saved = {}
                cache_available = False
            now = self.clock()
            available = all(self._fingerprint) and self._plex_state == 'available' and self._lease > now
            result = {}
            for ident in items:
                key = ident['key']
                is_owned = key in owned
                record = saved.get(key, {}).get('local_saved' if is_owned else 'online_cache')
                accepted = (owned.get(key) or {}).get('identity') or ident
                # Every supplied accepted ID must agree, even when a cache alias exists.
                if record and not all(record.get('identity', {}).get(f) == evidence[f]
                                      for evidence in (ident, accepted) for f in ('tmdb_id', 'imdb_id', 'plex_guid') if evidence.get(f)):
                    record = None
                allowed = bool(record and (is_owned or available))
                state, retry = self._states.get(_demand_key(ident), ('missing', 0))
                if allowed: state = 'ready'
                elif not cache_available: state = 'unavailable'
                elif not all(self._fingerprint) or self._plex_state == 'unavailable': state = 'unavailable'
                result[key] = {'state': state, 'owned': is_owned, 'display_allowed': allowed,
                    'critics': record.get('critics') if allowed else None,
                    'audience': record.get('audience') if allowed else None,
                    'source': ('plex_local' if is_owned else 'plex_catalog') if allowed else None,
                    'retrieved_at': record.get('retrieved_at') if allowed else None,
                    'revision': record.get('sequence') if allowed else None,
                    'stale': bool(allowed and now > record.get('expires_at', record['retrieved_at']+604800)),
                    'retry_at': max(retry, self._retry, record.get('refresh_after', 0) if allowed else 0) if self._retry != float('inf') else None}
            return {'schema_version': 1, 'owner': self.owner, 'generation': self.store.epoch,
                'cache_state': 'available' if cache_available else 'unavailable',
                'plex': {'state': 'available' if available else ('unknown' if self._plex_state == 'available' else self._plex_state),
                         'valid_until': self._lease}, 'items': result}

    def request(self, items):
        with self._condition:
            result = self.read(items)
            now = self.clock()
            if self._stopped or not all(self._fingerprint) or now < self._retry:
                return result
            for ident in items:
                key = ident['key']
                demand = _demand_key(ident)
                item = result['items'][key]
                if item['display_allowed'] and not item['stale']: continue
                if (item.get('retry_at') or 0) > now: continue
                if self._states.get(demand, ('', 0))[1] > now: continue
                if self._active and demand == _demand_key(self._active):
                    self._states[demand] = ('pending', 0)
                    continue
                duplicate = demand if demand in self._queue else None
                if duplicate:
                    self._queue[duplicate] = (self._queue[duplicate][0], now + 15, self.store.epoch)
                    continue
                self._queue[demand] = (ident, now + 15, self.store.epoch)
                self._queue.move_to_end(demand, last=ident['priority'] != 'expanded')
                self._states[demand] = ('pending', 0)
                while len(self._queue) > 200:
                    dropped, _ = self._queue.popitem(last=True)
                    self._states.pop(dropped, None)
            if self._queue: self._start()
            return self.read(items)

    def _start(self):
        if not self._thread or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._run, name='cp-movie-ratings', daemon=True)
            self._thread.start()
        self._condition.notify_all()

    def offer_local_snapshot(self, items, section_ids=(), *, expected_epoch=None):
        """Already-fetched minimal facts; no network or disk work on the sync caller."""
        with self._condition:
            self._check_config()
            if self._stopped or (expected_epoch is not None and expected_epoch != self.store.epoch): return
            self._local_lease = self.clock() + 300
            self._lease = min(self._local_lease, self._online_lease)
            for start in range(0, min(len(items), 10000), 50):
                self._snapshots.append((items[start:start+50], self.store.epoch, self.clock()))
            if self._snapshots: self._start()

    def _record(self, item, source, observed_at=None):
        identity = plex_identity(item)
        observed_at = item.get('_rt_observed_at', observed_at if observed_at is not None else self.clock())
        scores = normalize_plex_ratings(item)
        refresh_after = observed_at + (604800 if all(v is not None for v in scores.values()) else 86400)
        raw = {}
        for field, role, images, scalar, marker in (
            ('critics', 'critic', _CRITIC_IMAGES, 'rating', 'ratingImage'),
            ('audience', 'audience', _AUDIENCE_IMAGES, 'audienceRating', 'audienceRatingImage')):
            rows = [r for r in (item.get('Rating') or []) if isinstance(r, dict) and r.get('type') == role and r.get('image') in images]
            if scores[field] is not None:
                raw[field] = {'value': float(rows[0]['value'] if rows else item[scalar]),
                              'type': role, 'image': rows[0]['image'] if rows else item[marker]}
        return {'key': ('movie:plex:' + identity['plex_guid'].rsplit('/', 1)[-1]) if identity.get('plex_guid') else identity['key'],
            'aliases': identity['aliases'], 'identity': identity, 'source': source,
            **scores, 'raw': raw, 'retrieved_at': observed_at,
            'expires_at': refresh_after, 'refresh_after': refresh_after, 'sequence': observed_at}

    def _run(self):
        while True:
            with self._condition:
                if self._stopped: return
                if self._queue:
                    key, (ident, expires, epoch) = self._queue.popitem(last=False)
                    if expires < self.clock():
                        self._states.pop(key, None)
                        continue
                    self._active = ident
                    snapshot = None
                elif self._snapshots:
                    snapshot, epoch, observed_at = self._snapshots.popleft()
                else:
                    self._condition.wait(30)
                    continue
            try:
                if snapshot is not None:
                    records = []
                    for item in snapshot:
                        try: records.append(self._record(item, 'local_saved', observed_at))
                        except (ValueError, TypeError): pass
                    try:
                        self.store.publish(records, expected_epoch=epoch)
                    except ValueError:
                        for record in records:
                            try: self.store.publish([record], expected_epoch=epoch)
                            except ValueError: pass
                else:
                    self._resolve(ident, epoch)
            except Exception:
                if snapshot is None:
                    with self._condition:
                        if epoch == self.store.epoch: self._states[_demand_key(ident)] = ('unavailable', self.clock()+60)
            finally:
                with self._condition: self._active = None

    def _resolve(self, ident, epoch):
        with self._condition:
            if epoch != self.store.epoch or self.clock() < self._retry: return
            # A preceding compatible demand may have confirmed this fuller identity.
            # Recheck evidence before HTTP; never merge unverified conflicting hints.
            cached = self.read([ident])['items'][ident['key']]
            if cached['display_allowed'] and (not cached['stale'] or (cached.get('retry_at') or 0) > self.clock()):
                self._states[_demand_key(ident)] = ('ready', 0)
                return
            base, token = self._fingerprint
            owned = self._owned([ident]).get(ident['key'])
            accepted = {**ident, **((owned or {}).get('identity') or {})}
            lease = self._local_lease
        try:
            if owned is not None:
                rating_key = str(owned.get('rating_key') or '')
                if not rating_key.isdigit():
                    with self._condition: self._states[_demand_key(ident)] = ('missing', self.clock()+3600)
                    return
                payload = self.transport(base, token, '/library/metadata/' + rating_key)
                source = 'local_saved'
                local_checked = True
            else:
                local_checked = lease <= self.clock()
                if lease <= self.clock():
                    self.transport(base, token, '/library/sections')
                with self._condition:
                    if epoch != self.store.epoch: return
                    while time.monotonic() - self._last_online_start < .5:
                        self._condition.wait(.5 - (time.monotonic() - self._last_online_start))
                        if self._stopped or epoch != self.store.epoch: return
                    self._last_online_start = time.monotonic()
                if ident.get('tmdb_id') or ident.get('imdb_id'):
                    guid = ('tmdb://' + ident['tmdb_id']) if ident.get('tmdb_id') else ('imdb://' + ident['imdb_id'])
                    payload = self.transport('https://metadata.provider.plex.tv', token, '/library/metadata/matches', params={'guid': guid, 'type': 1})
                else:
                    payload = self.transport('https://metadata.provider.plex.tv', token, '/library/metadata/' + ident['plex_guid'].rsplit('/', 1)[-1])
                source = 'online_cache'
            rows = payload.get('MediaContainer', {}).get('Metadata', [])
            matches = [row for row in rows if isinstance(row, dict) and matches_identity(ident, row) and matches_identity(accepted, row)]
            with self._condition:
                if epoch != self.store.epoch or self._stopped: return
                if local_checked: self._local_lease = self.clock()+300
                if source == 'online_cache': self._online_lease = self.clock()+300
                self._lease = min(self._local_lease, self._online_lease)
                self._plex_state, self._retry, self._failures = ('available' if self._lease > self.clock() else 'unknown'), 0, 0
                if len(matches) != 1:
                    self._states[_demand_key(ident)] = ('identity_mismatch' if rows else 'not_found', self.clock()+86400)
                    return
            published = self.store.publish([self._record(matches[0], source)], expected_epoch=epoch)
            with self._condition:
                if published and epoch == self.store.epoch:
                    self._states[_demand_key(ident)] = ('ready', 0)
        except Exception as exc:
            with self._condition:
                if epoch != self.store.epoch: return
                code = getattr(exc, 'code', None)
                self._failures += 1
                delay = (60, 300, 1800)[min(self._failures-1, 2)]
                if code in (401, 403): delay = float('inf')
                elif code == 429:
                    retry = (getattr(exc, 'headers', None) or {}).get('Retry-After', '')
                    try: delay = max(1, float(retry))
                    except (ValueError, TypeError):
                        try: delay = max(1, parsedate_to_datetime(retry).timestamp()-self.clock())
                        except (ValueError, TypeError, OverflowError): delay = 900
                self._plex_state, self._lease, self._retry = 'unavailable', 0, self.clock()+delay
                self._local_lease = self._online_lease = 0
                self._states[_demand_key(ident)] = ('unavailable', self._retry)

    def stop(self):
        with self._condition:
            self._stopped = True
            self.store.invalidate()
            self._queue.clear()
            self._snapshots.clear()
            self._condition.notify_all()
        if self._thread: self._thread.join(timeout=7)
