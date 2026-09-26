"""Bounded hierarchical monitoring. No enablement from metadata discovery."""
from datetime import datetime, timezone
import time
import uuid


class TVMonitoring:
    MODES = {'none', 'future', 'missing', 'all', 'cutoff', 'inherit'}

    def __init__(self, tv, store, acquisition, clock=time.time):
        self.tv, self.store, self.acquisition, self.clock = tv, store, acquisition, clock
        self.owner = uuid.uuid4().hex

    def configure(self, series_id, *, mode, profile_id=None, season=None, episode=None):
        if mode not in self.MODES:
            raise ValueError('Unknown monitoring mode')
        target, series, rows = self.acquisition.target(series_id, season, episode)
        if profile_id:
            self.store.profile(profile_id)
        if mode == 'inherit' and season is None:
            raise ValueError('Series monitoring cannot inherit')
        parent = f"series:tmdb:tv:{series['tmdb_id']}" if season is not None else None
        if episode is not None:
            parent = f"season:tmdb:tv:{series['tmdb_id']}:{season}"
        with self.store.transaction() as db:
            db.execute('INSERT INTO monitors(target,parent,mode,profile_id,next_due) VALUES(?,?,?,?,?) ON CONFLICT(target) DO UPDATE SET mode=excluded.mode,profile_id=excluded.profile_id,next_due=excluded.next_due,failures=0', (target['key'], parent, mode, profile_id, self.clock()))
        return self.describe(series_id)

    def effective(self, series, episode):
        keys = [f"episode:tmdb:tv:{series['tmdb_id']}:{episode['season_number']}:{episode['episode_number']}", f"season:tmdb:tv:{series['tmdb_id']}:{episode['season_number']}", f"series:tmdb:tv:{series['tmdb_id']}"]
        mode, origin, profile_id, since = 'none', 'default', None, 0
        with self.store.connection() as db:
            for key in keys:
                row = db.execute('SELECT * FROM monitors WHERE target=?', (key,)).fetchone()
                if row:
                    profile_id = profile_id or row['profile_id']
                    if row['mode'] != 'inherit' and origin == 'default':
                        mode, origin, since = row['mode'], key, row['next_due']
        return {'mode': mode, 'origin': origin, 'profile_id': profile_id or 'safe-hd', 'since': since}

    def describe(self, series_id):
        series = self.tv.series(series_id)
        with self.store.connection() as db:
            prefix = f"%:tmdb:tv:{series['tmdb_id']}"
            rules = [dict(row) for row in db.execute('SELECT * FROM monitors WHERE target LIKE ? OR target LIKE ? ORDER BY target', (prefix, prefix+':%'))]
        return {'rules': rules, 'episodes': [{'episode_id': row['id'], **self.effective(series, row)} for row in self.tv.episodes(series_id)]}

    def monitored_tmdb_ids(self):
        with self.store.connection() as db:
            rows = db.execute("SELECT target FROM monitors WHERE mode NOT IN ('none','inherit')")
            return {int(parts[3]) for row in rows if len(parts := row['target'].split(':')) > 3 and parts[1:3] == ['tmdb', 'tv'] and parts[3].isdigit()}

    def run_once(self, *, limit=10, submit=False):
        limit = min(25, max(1, int(limit)))
        now, results = self.clock(), []
        with self.store.connection() as db:
            rules = [dict(row) for row in db.execute("SELECT * FROM monitors WHERE mode NOT IN ('none','inherit') AND next_due<=? ORDER BY next_due,target LIMIT 100", (now,))]
        seen = set()
        for rule in rules:
            tmdb_id = int(rule['target'].split(':')[3])
            with self.tv.store.connection() as db:
                row = db.execute('SELECT id FROM series WHERE tmdb_id=?', (tmdb_id,)).fetchone()
            if not row:
                continue
            series = self.tv.series(row[0])
            for episode in self.tv.episodes(series['id']):
                if len(results) >= limit:
                    return results
                if episode['id'] in seen or not episode['released'] or episode['reconciliation_required']:
                    continue
                seen.add(episode['id'])
                policy = self.effective(series, episode)
                if policy['mode'] == 'none':
                    continue
                profile = self.store.profile(policy['profile_id'])
                if episode['available'] and (policy['mode'] != 'cutoff' or not profile['automatic_upgrades']):
                    continue
                work_key = f"monitor:episode:{episode['id']}"
                with self.store.connection() as db:
                    queued = db.execute('SELECT 1 FROM intent_claims WHERE target=?', (f"tv:episode:{episode['id']}",)).fetchone()
                    retry = db.execute('SELECT value FROM settings WHERE key=?', (work_key,)).fetchone()
                if queued or (retry and float(retry[0]) > now):
                    continue
                aired = datetime.fromisoformat(episode['air_date']).replace(tzinfo=timezone.utc).timestamp()
                if policy['mode'] == 'future' and aired < policy['since']:
                    continue
                if now < aired + profile['delay_seconds']:
                    continue
                if not self.store.lease(work_key, self.owner, ttl=120):
                    continue
                try:
                    review = self.acquisition.search(series['id'], episode['season_number'], episode['episode_number'], policy['profile_id'], manual=False)
                    accepted = next((decision for decision in review['decisions'] if decision['accepted']), None)
                    result = {'episode_id': episode['id'], 'decision': accepted, 'submitted': False}
                    if accepted and submit:
                        result['acquisition'] = self.acquisition.submit(accepted['decision_token'], work_key+':'+accepted['decision_token'])
                        result['submitted'] = True
                    results.append(result)
                    delay = 3600 if not accepted else 86400
                except Exception as error:
                    results.append({'episode_id': episode['id'], 'error': str(error), 'submitted': False})
                    delay = min(86400, 300 * 2 ** min(rule['failures'], 8))
                    with self.store.transaction() as db:
                        db.execute('UPDATE monitors SET failures=failures+1 WHERE target=?', (rule['target'],))
                finally:
                    with self.store.transaction() as db:
                        db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)', (work_key, str(now+locals().get('delay', 300))))
                    self.store.release_lease(work_key, self.owner)
        return results
