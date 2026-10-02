"""Durable TV Follow and one-shot download tasks over the existing acquisition owner."""
from datetime import date
import hashlib
import json
from pathlib import Path
import time
import uuid
from send2trash import send2trash


class TVMonitoring:
    ACTIONS = {'missing', 'future', 'upgrade', 'selected'}
    SCOPES = {'series', 'season', 'episodes'}

    def __init__(self, tv, store, acquisition, clock=time.time, active_media_path=lambda: '', trash_file=send2trash):
        self.tv, self.store, self.acquisition, self.clock = tv, store, acquisition, clock
        self.active_media_path, self.trash_file = active_media_path, trash_file
        self._resolve_legacy_drafts()

    def _resolve_legacy_drafts(self):
        """Attach saved old rules to local identities without activating downloads."""
        with self.store.connection() as db:
            pending = [dict(row) for row in db.execute(
                "SELECT id,tmdb_id,scope FROM tv_tasks WHERE id LIKE 'legacy:%' "
                "AND state NOT IN ('completed','cancelled') "
                "AND NOT EXISTS(SELECT 1 FROM tv_task_episodes WHERE task_id=tv_tasks.id) "
                "AND (series_id=0 OR state<>'draft')")]
        for task in pending:
            with self.tv.store.connection() as db:
                series = db.execute('SELECT id FROM series WHERE tmdb_id=?', (task['tmdb_id'],)).fetchone()
            if not series:
                continue
            selected = []
            error = 'Migrated rule: review and Start explicitly'
            if task['scope'] == 'episodes':
                parts = task['id'][len('legacy:'):].split(':')
                if len(parts) != 6 or not parts[4].isdigit() or not parts[5].isdigit():
                    error = 'Legacy episode identity needs review before Start'
                else:
                    selected = [row['id'] for row in self.tv.episodes(series[0])
                                if row['season_number'] == int(parts[4]) and row['episode_number'] == int(parts[5])]
                    if not selected:
                        error = 'Legacy episode identity needs review before Start'
            with self.store.transaction() as db:
                db.execute('UPDATE tv_tasks SET series_id=?,selected_episodes=?,state="draft",'
                           'target_episode_ids="[]",started_at=NULL,next_due=0,error=? WHERE id=?',
                           (series[0], json.dumps(selected), error, task['id']))

    def _series(self, series_id):
        return self.tv.series(int(series_id))

    def _rows(self, series_id, scope, season=None, selected_episodes=()):
        rows = [row for row in self.tv.episodes(series_id) if row['season_number'] > 0 or scope == 'episodes']
        if scope == 'season':
            rows = [row for row in rows if row['season_number'] == int(season)]
        elif scope == 'episodes':
            ids = {int(value) for value in selected_episodes}
            if not ids or len(ids) > 500:
                raise ValueError('Select 1 to 500 episodes')
            rows = [row for row in rows if row['id'] in ids]
            if {row['id'] for row in rows} != ids:
                raise ValueError('Selected episode identities changed; review the task')
        return rows

    def _pending(self, series_id):
        with self.tv.store.connection() as db:
            reviews = [json.loads(row[0]) for row in db.execute(
                "SELECT payload FROM ingestion_candidates WHERE state='needs_review' "
                "AND CAST(json_extract(payload,'$.series_id') AS INTEGER)=?", (series_id,))]
        scoped = set()
        uncertain = False
        for review in reviews:
            claim = review.get('claim') or {}
            season = claim.get('season_number')
            numbers = claim.get('episode_numbers') or []
            if season is None or not numbers:
                uncertain = True
                continue
            scoped.update((int(season), int(number)) for number in numbers)
        return scoped, uncertain

    def preview(self, series_id, *, scope='series', action='missing', season=None, selected_episodes=(), profile_id='safe-hd'):
        if scope not in self.SCOPES or action not in self.ACTIONS or (action == 'selected' and scope != 'episodes'):
            raise ValueError('Choose a valid TV scope and action')
        if scope == 'season' and (season is None or int(season) <= 0):
            raise ValueError('Choose a regular season')
        series = self._series(series_id)
        self.store.profile(profile_id)
        if action == 'future' and str(series.get('status') or '').casefold() == 'ended':
            raise ValueError('Future following is unavailable for an ended series')
        rows = self._rows(series_id, scope, season, selected_episodes)
        scoped, uncertain = self._pending(series_id)
        with self.store.connection() as db:
            queued = {row[0] for row in db.execute('SELECT target FROM intent_claims')}
        counts = {'released_missing': 0, 'future': 0, 'owned': 0, 'queued': 0, 'review': 0, 'unknown_date': 0}
        candidates = []
        for row in rows:
            withheld = (row['reconciliation_required'] or uncertain or
                        (row['season_number'], row['episode_number']) in scoped or
                        f"tv:episode:{row['id']}" in queued)
            if not row['air_date']:
                counts['unknown_date'] += 1
                continue
            if row['available']:
                counts['owned'] += 1
            elif f"tv:episode:{row['id']}" in queued:
                counts['queued'] += 1
            elif (row['season_number'], row['episode_number']) in scoped or uncertain or row['reconciliation_required']:
                counts['review'] += 1
            elif not row['released']:
                counts['future'] += 1
            else:
                counts['released_missing'] += 1
            if action == 'upgrade' and row['available'] and row['released'] and not withheld:
                candidates.append(row['id'])
            elif action == 'future' and not row['released'] and bool(row['air_date']) and not row['available'] and not withheld:
                candidates.append(row['id'])
            elif action == 'selected' and not row['available'] and not withheld:
                candidates.append(row['id'])
            elif action == 'missing' and row['released'] and not row['available'] and not withheld:
                candidates.append(row['id'])
        return {'series_id': int(series_id), 'tmdb_id': series['tmdb_id'], 'scope': scope,
                'action': action, 'season': season, 'profile_id': profile_id, 'counts': counts,
                'target_episode_ids': candidates, 'metadata_complete': self.tv.hydration(series_id)['status'] == 'complete'}

    def save_task(self, series_id, *, scope='series', action='missing', season=None, selected_episodes=(), profile_id='safe-hd', kind='follow'):
        if kind not in {'follow', 'bulk'} or (kind == 'bulk' and action != 'missing'):
            raise ValueError('Bulk Download is a one-shot Missing action')
        preview = self.preview(series_id, scope=scope, action=action, season=season,
                               selected_episodes=selected_episodes, profile_id=profile_id)
        if kind == 'bulk' and scope != 'series':
            raise ValueError('Bulk Download selects whole shows')
        identity, now = uuid.uuid4().hex, self.clock()
        with self.store.transaction() as db:
            db.execute('INSERT INTO tv_tasks(id,series_id,tmdb_id,kind,scope,action,season,selected_episodes,profile_id,state,created_at,updated_at) '
                       'VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                       (identity, int(series_id), preview['tmdb_id'], kind, scope, action, season,
                        json.dumps(list(selected_episodes)), profile_id, 'draft', now, now))
        return self.task(identity)

    def task(self, task_id):
        with self.store.connection() as db:
            row = db.execute('SELECT * FROM tv_tasks WHERE id=?', (task_id,)).fetchone()
            if not row:
                raise LookupError('TV task not found')
            episodes = [dict(item) for item in db.execute('SELECT * FROM tv_task_episodes WHERE task_id=? ORDER BY episode_id', (task_id,))]
        result = dict(row)
        result['selected_episodes'] = json.loads(result['selected_episodes'])
        result['target_episode_ids'] = json.loads(result['target_episode_ids'])
        result['episodes'] = episodes
        return result

    def list_tasks(self, series_id=None, *, history=False, page=1, page_size=50):
        page = max(1, int(page)); page_size = min(100, max(1, int(page_size)))
        where = "state IN ('completed','cancelled')" if history else "state NOT IN ('completed','cancelled')"
        args = []
        if series_id is not None:
            where += ' AND series_id=?'; args.append(int(series_id))
        with self.store.connection() as db:
            total = db.execute(f'SELECT COUNT(*) FROM tv_tasks WHERE {where}', args).fetchone()[0]
            ids = [row[0] for row in db.execute(f'SELECT id FROM tv_tasks WHERE {where} ORDER BY created_at DESC LIMIT ? OFFSET ?',
                                                 (*args, page_size, (page-1)*page_size))]
        return {'items': [self.task(identity) for identity in ids], 'total': total, 'page': page,
                'total_pages': max(1, (total+page_size-1)//page_size)}

    def start_task(self, task_id):
        task = self.task(task_id)
        if task['state'] != 'draft':
            raise ValueError('Only a saved draft can be started')
        if not task['series_id'] or task['scope'] == 'episodes' and not task['selected_episodes']:
            raise ValueError('Migrated TV identity needs review before Start')
        metadata = getattr(self.acquisition, 'metadata', None)
        if metadata:
            try:
                metadata.refresh(task['tmdb_id'])
            except (OSError, ValueError, KeyError, TimeoutError) as error:
                with self.store.transaction() as db:
                    db.execute('UPDATE tv_tasks SET error=?,updated_at=? WHERE id=?', (str(error)[:500], self.clock(), task_id))
                raise ValueError('TV metadata refresh failed; the draft remains saved') from error
        preview = self.preview(task['series_id'], scope=task['scope'], action=task['action'],
            season=task['season'], selected_episodes=task['selected_episodes'], profile_id=task['profile_id'])
        if not preview['metadata_complete']:
            raise ValueError('Complete regular-season metadata is required before Start')
        if task['action'] == 'future':
            started = date.fromtimestamp(self.clock()).isoformat()
            released_missing = self.preview(task['series_id'], scope=task['scope'], action='missing',
                season=task['season'], profile_id=task['profile_id'])['target_episode_ids']
            preview['target_episode_ids'] = list(dict.fromkeys(preview['target_episode_ids'] + [row['id']
                for row in self._rows(task['series_id'], task['scope'], task['season'])
                if row['id'] in released_missing and row['air_date'] and row['air_date'] >= started]))
        if task['kind'] == 'bulk' and not preview['target_episode_ids']:
            raise ValueError('No released missing regular episodes need download')
        now = self.clock()
        with self.store.transaction() as db:
            db.execute('UPDATE tv_tasks SET state="running",target_episode_ids=?,started_at=?,updated_at=?,next_due=?,last_refresh=?,error="" WHERE id=?',
                       (json.dumps(preview['target_episode_ids']), now, now, now, now, task_id))
            for episode_id in preview['target_episode_ids']:
                db.execute('INSERT INTO tv_task_episodes(task_id,episode_id,state) VALUES(?,?,?)', (task_id, episode_id, 'waiting'))
        self.store.notify(media_type='tv', source='follow', task_id=task_id, event_key=f'task:{task_id}:started',
                          severity='info', title='TV task started', body=f"{task['action'].title()} for {self._series(task['series_id'])['title']}",
                          link=f"/tv/series/{task['series_id']}")
        return self.task(task_id)

    def configure(self, series_id, *, mode, profile_id=None, season=None, episode=None):
        """Convert the former immediate-monitor API to durable tasks for old callers."""
        if mode == 'none':
            with self.store.transaction() as db:
                rows = [dict(row) for row in db.execute("SELECT id,scope,season FROM tv_tasks WHERE series_id=? AND state NOT IN ('completed','cancelled')", (series_id,))]
                for row in rows:
                    if season is None or row['scope'] == 'season' and row['season'] == season:
                        db.execute('UPDATE tv_tasks SET state="cancelled",updated_at=? WHERE id=?', (self.clock(), row['id']))
                    elif row['scope'] == 'series':
                        db.execute('INSERT OR IGNORE INTO tv_task_exclusions VALUES(?,?)', (row['id'], season))
            return self.describe(series_id)
        action = {'all': 'missing', 'cutoff': 'upgrade'}.get(mode, mode)
        if mode == 'inherit' or action not in self.ACTIONS:
            raise ValueError('Choose Missing, Future or Upgrade')
        scope = 'episodes' if episode is not None else 'season' if season is not None else 'series'
        selected = []
        if episode is not None:
            selected = [row['id'] for row in self.tv.episodes(series_id, season) if row['episode_number'] == episode]
            action = 'upgrade' if action == 'upgrade' else 'selected'
        draft = self.save_task(series_id, scope=scope, action=action, season=season,
                               selected_episodes=selected, profile_id=profile_id or 'safe-hd')
        self.start_task(draft['id'])
        return self.describe(series_id)

    def describe(self, series_id):
        tasks = self.list_tasks(series_id)['items']
        active = [task for task in tasks if task['state'] != 'draft']
        with self.store.connection() as db:
            excluded = {(row['task_id'], row['season']) for row in db.execute('SELECT task_id,season FROM tv_task_exclusions')}
        episodes = [{'episode_id': row['id'], 'mode': next((task['action'] for task in active
                    if row['id'] in task['target_episode_ids'] and (task['id'], row['season_number']) not in excluded), 'none')}
                    for row in self.tv.episodes(series_id)]
        return {'rules': tasks, 'tasks': tasks, 'episodes': episodes}

    def monitored_tmdb_ids(self):
        with self.store.connection() as db:
            return {row[0] for row in db.execute("SELECT DISTINCT tmdb_id FROM tv_tasks WHERE state IN ('running','waiting','waiting_season_end','needs_review')")}

    def finish_season(self, task_id):
        task = self.task(task_id)
        if task['action'] != 'future' or task['scope'] != 'season' or task['state'] != 'waiting_season_end':
            raise ValueError('Only a waiting season Future task can be finished explicitly')
        if any(row['state'] != 'acquired' for row in task['episodes']):
            raise ValueError('Some selected-season episodes remain outstanding')
        with self.store.transaction() as db:
            db.execute('UPDATE tv_tasks SET state="completed",updated_at=? WHERE id=?', (self.clock(), task_id))
        self.store.notify(media_type='tv', source='follow', task_id=task_id,
            event_key=f'task:{task_id}:completed', severity='info', title='TV season follow completed',
            body=self._series(task['series_id'])['title'], link=f'/tv/series/{task["series_id"]}')
        return self.task(task_id)

    def cancel_preview(self, task_id):
        task = self.task(task_id)
        if task['state'] in {'completed', 'cancelled'}:
            raise ValueError('This task has already finished')
        intents = sorted({item['intent_id'] for item in task['episodes'] if item['intent_id']})
        manager = self.acquisition.manager()
        jobs = manager.jobs.all()
        torrents = {str(item.get('hash') or '').lower(): item for item in manager.client.torrents()} if intents else {}
        roots = [Path(root).resolve() for root in self.acquisition.roots()]
        playing = self.active_media_path()
        transfers, completed, protected = [], [], []
        with self.store.connection() as db:
            intent_rows = [db.execute('SELECT * FROM intents WHERE id=?', (identity,)).fetchone() for identity in intents]
            for intent in intent_rows:
                if not intent:
                    protected.append({'path': '', 'reason': 'Acquisition intent is missing'})
                    continue
                torrent_hash = intent['info_hash'].lower()
                job = jobs.get(torrent_hash)
                shared = db.execute('SELECT COUNT(*) FROM tv_task_episodes WHERE intent_id=? AND task_id<>?',
                                    (intent['id'], task_id)).fetchone()[0]
                shared += db.execute('SELECT COUNT(*) FROM intents WHERE info_hash=? AND id<>?',
                                     (intent['info_hash'], intent['id'])).fetchone()[0]
                if not job or job.get('acquisition_id') != intent['id'] or shared:
                    protected.append({'path': '', 'reason': f'Transfer {torrent_hash} has uncertain or shared ownership'})
                    continue
                transfer = {'intent_id': intent['id'], 'hash': torrent_hash, 'state': job.get('state'),
                            'paths': [], 'deletable_incomplete': False}
                torrent = torrents.get(torrent_hash)
                if torrent and job.get('state') not in {'imported','partial_import','seed_complete','partial_seed_complete','cancelled','rolled_back'}:
                    save_path = Path(torrent.get('save_path') or '').resolve()
                    if save_path == Path(manager.staging_dir).resolve() or Path(manager.staging_dir).resolve() in save_path.parents:
                        try:
                            paths = [save_path / str(item['name']) for item in manager.client.files(torrent_hash)]
                            if paths and all(Path(manager.staging_dir).resolve() in path.resolve().parents for path in paths):
                                transfer['paths'] = [str(path.resolve()) for path in paths]
                                transfer['deletable_incomplete'] = True
                        except (OSError, KeyError, ValueError):
                            pass
                    if not transfer['deletable_incomplete']:
                        protected.append({'path': str(save_path), 'reason': 'Incomplete transfer paths are not verified'})
                transfers.append(transfer)
                for entry in job.get('preserving_import_plan') or []:
                    if entry.get('state') != 'published':
                        continue
                    path = Path(entry['target']).resolve()
                    if not path.is_file() or not any(root in path.parents for root in roots):
                        protected.append({'path': str(path), 'reason': 'Imported path is missing or outside the TV root'})
                        continue
                    if playing and path == Path(playing).resolve():
                        protected.append({'path': str(path), 'reason': 'Currently playing'})
                        continue
                    with self.tv.store.connection() as tv_db:
                        bindings = {row[0] for row in tv_db.execute('SELECT DISTINCT e.series_id FROM media_files f '
                            'JOIN episode_file_bindings b ON b.file_id=f.id JOIN episodes e ON e.id=b.episode_id WHERE f.path=?',
                            (str(path),))}
                    if bindings != {task['series_id']} or any(str(path) in (other.get('imported_paths') or [])
                        for other_hash, other in jobs.items() if other_hash != torrent_hash):
                        protected.append({'path': str(path), 'reason': 'Imported file has shared or uncertain ownership'})
                        continue
                    stat = path.stat()
                    completed.append({'path': str(path), 'size': stat.st_size, 'modified_ns': stat.st_mtime_ns,
                                      'hash': torrent_hash})
        payload = {'task_id': task_id, 'transfers': transfers, 'completed_files': completed,
                   'protected': protected}
        payload['token'] = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        return payload

    def cancel_task(self, task_id, mode, token):
        if mode not in {'keep', 'incomplete', 'all'}:
            raise ValueError('Choose a cancellation outcome')
        preview = self.cancel_preview(task_id)
        if token != preview['token']:
            raise ValueError('Transfers or files changed; review cancellation again')
        manager = self.acquisition.manager()
        removed, stopped, protected, failures = [], [], list(preview['protected']), []
        with manager._completion_lock:
            if self.cancel_preview(task_id)['token'] != token:
                raise ValueError('Transfers or files changed; review cancellation again')
            for transfer in preview['transfers']:
                try:
                    manager.client.pause(transfer['hash'])
                    if mode in {'incomplete','all'} and transfer['deletable_incomplete']:
                        manager.client.remove_with_files(transfer['hash'])
                        removed.extend(transfer['paths'])
                    elif mode in {'incomplete','all'} and transfer['paths']:
                        protected.extend({'path': path, 'reason': 'Incomplete transfer ownership is uncertain'} for path in transfer['paths'])
                    manager.jobs.upsert(transfer['hash'], {'state': 'cancelled', 'last_error': 'Cancelled by TV task'})
                    self.store.event(transfer['intent_id'], 'cancel', {'task_id': task_id, 'mode': mode}, state='cancelled')
                    stopped.append(transfer['hash'])
                except (OSError, ValueError, RuntimeError) as error:
                    failures.append({'transfer': transfer['hash'], 'reason': str(error)})
            if mode == 'all':
                for item in preview['completed_files']:
                    path = Path(item['path'])
                    try:
                        stat = path.stat()
                        if (stat.st_size, stat.st_mtime_ns) != (item['size'], item['modified_ns']):
                            raise ValueError('Imported file changed after preview')
                        if self.active_media_path() and path.resolve() == Path(self.active_media_path()).resolve():
                            raise ValueError('Imported file is playing')
                        self.trash_file(str(path))
                        with self.tv.store.transaction() as db:
                            db.execute('UPDATE media_files SET available=0 WHERE path=?', (str(path),))
                        removed.append(str(path))
                    except (OSError, ValueError) as error:
                        protected.append({'path': str(path), 'reason': str(error)})
        outcome = {'stopped_transfers': stopped, 'removed_paths': removed, 'protected': protected, 'failures': failures}
        with self.store.transaction() as db:
            db.execute('INSERT OR REPLACE INTO tv_task_cancellations(task_id,mode,preview,outcome,created_at) VALUES(?,?,?,?,?)',
                (task_id, mode, json.dumps(preview), json.dumps(outcome), self.clock()))
            db.execute('UPDATE tv_tasks SET state=?,updated_at=?,error=? WHERE id=?',
                ('cancel_pending' if failures else 'cancelled', self.clock(), 'Transfer cancellation needs review' if failures else '', task_id))
        self.store.notify(media_type='tv', source='follow', task_id=task_id,
            event_key=f'task:{task_id}:cancel:{mode}', severity='warning' if failures or protected else 'info',
            title='TV task cancellation needs review' if failures else 'TV task cancelled',
            body=f'{len(stopped)} transfers stopped; {len(removed)} paths removed; {len(protected)} protected',
            link=f'/tv/series/{self.task(task_id)["series_id"]}')
        return {'task': self.task(task_id), 'outcome': outcome}

    def run_once(self, *, limit=10, submit=False):
        now, results = self.clock(), []
        with self.store.connection() as db:
            ids = [row[0] for row in db.execute("SELECT id FROM tv_tasks WHERE state IN ('running','waiting','waiting_season_end','needs_review') "
                                              "AND next_due<=? ORDER BY next_due,created_at LIMIT 25", (now,))]
        for task_id in ids:
            task = self.task(task_id)
            if not task['series_id']:
                continue
            series = self._series(task['series_id'])
            if task['action'] == 'future' and now - (task['last_refresh'] or 0) >= 21600:
                metadata = getattr(self.acquisition, 'metadata', None)
                if metadata:
                    try:
                        metadata.refresh(task['tmdb_id'])
                        with self.store.transaction() as db:
                            db.execute('UPDATE tv_tasks SET last_refresh=?,error="" WHERE id=?', (now, task_id))
                    except (OSError, ValueError, KeyError, TimeoutError) as error:
                        with self.store.transaction() as db:
                            db.execute('UPDATE tv_tasks SET error=?,next_due=? WHERE id=?', (str(error)[:500], now+3600, task_id))
                        continue
                current = self._rows(task['series_id'], task['scope'], task['season'], task['selected_episodes'])
                known = set(task['target_episode_ids'])
                started = date.fromtimestamp(task['started_at']).isoformat()
                added = [row['id'] for row in current if row['id'] not in known and not row['available']
                         and row['air_date'] and row['air_date'] >= started]
                if added:
                    with self.store.transaction() as db:
                        db.execute('UPDATE tv_tasks SET target_episode_ids=?,updated_at=? WHERE id=?',
                                   (json.dumps(task['target_episode_ids']+added), now, task_id))
                        for episode_id in added:
                            db.execute('INSERT OR IGNORE INTO tv_task_episodes(task_id,episode_id,state) VALUES(?,?,"waiting")', (task_id, episode_id))
                    task = self.task(task_id)
                    for episode_id in added:
                        self.store.notify(media_type='tv', source='follow', task_id=task_id,
                            event_key=f'task:{task_id}:{episode_id}:announced', severity='info',
                            title='New TV episode announced', body=series['title'],
                            link=f'/tv/series/{task["series_id"]}')
            pending, uncertain = self._pending(task['series_id'])
            rows = {row['id']: row for row in self.tv.episodes(task['series_id'])}
            with self.store.connection() as db:
                excluded_seasons = {row[0] for row in db.execute('SELECT season FROM tv_task_exclusions WHERE task_id=?', (task_id,))}
            for item in task['episodes']:
                if len(results) >= max(1, min(25, int(limit))):
                    return results
                if item['state'] == 'acquired':
                    continue
                row = rows.get(item['episode_id'])
                if not row or row['season_number'] in excluded_seasons:
                    continue
                intent_id = None
                if item['state'] == 'queued' and item['intent_id']:
                    with self.store.connection() as db:
                        intent = db.execute('SELECT state FROM intents WHERE id=?', (item['intent_id'],)).fetchone()
                    if intent and intent['state'] == 'ready':
                        with self.store.transaction() as db:
                            db.execute('UPDATE tv_task_episodes SET state="acquired",next_retry=0 WHERE task_id=? AND episode_id=?',
                                (task_id, row['id']))
                        self.store.notify(media_type='tv', source='follow', task_id=task_id, episode_key=row['code'],
                            event_key=f'task:{task_id}:{row["id"]}:acquired', severity='info',
                            title=f'{row["code"]} acquired', body=series['title'],
                            link=f'/tv/series/{task["series_id"]}')
                        continue
                    if intent and intent['state'] in {'failed_terminal','cancelled'}:
                        with self.store.transaction() as db:
                            db.execute('UPDATE tv_task_episodes SET state="needs_review",error=? WHERE task_id=? AND episode_id=?',
                                (f'Acquisition {intent["state"]}', task_id, row['id']))
                        self.store.notify(media_type='tv', source='follow', task_id=task_id, episode_key=row['code'],
                            event_key=f'task:{task_id}:{row["id"]}:needs_review', severity='error',
                            title=f'{row["code"]} needs review', body=series['title'],
                            link=f'/tv/series/{task["series_id"]}')
                        continue
                if row['available'] and task['action'] != 'upgrade':
                    state, retry = 'acquired', 0
                elif not row['released'] or not row['air_date']:
                    state, retry = 'waiting_release', now+3600
                elif row['reconciliation_required'] or uncertain or (row['season_number'], row['episode_number']) in pending:
                    state, retry = 'needs_review', now+3600
                elif item['state'] == 'queued' or item['next_retry'] > now:
                    continue
                else:
                    try:
                        if item['state'] == 'waiting_release' and task['action'] in {'future', 'selected'}:
                            self.store.notify(media_type='tv', source='follow', task_id=task_id,
                                episode_key=row['code'], event_key=f'task:{task_id}:{row["id"]}:eligible',
                                severity='info', title=f'{row["code"]} is ready to search',
                                body=series['title'], link=f'/tv/series/{task["series_id"]}')
                        review = self.acquisition.search(task['series_id'], row['season_number'], row['episode_number'],
                            task['profile_id'], manual=False, missing_only=task['action'] != 'upgrade', upgrade=task['action'] == 'upgrade')
                        accepted = next((decision for decision in review['decisions'] if decision['accepted']), None)
                        submitted = self.acquisition.submit(accepted['decision_token'],
                            f'task:{task_id}:{row["id"]}:{accepted["decision_token"][:24]}') if accepted and submit else None
                        results.append({'task_id': task_id, 'episode_id': row['id'], 'decision': accepted,
                                        'submitted': bool(submitted), 'error': '' if accepted else 'No source found'})
                        intent_id = submitted['intent']['id'] if submitted else None
                        state, retry = ('queued', now+3600) if accepted and submit else ('retry', now+3600)
                        if accepted:
                            self.store.notify(media_type='tv', source='follow', task_id=task_id,
                                episode_key=row['code'], event_key=f'task:{task_id}:{row["id"]}:source', severity='info',
                                title=f'Source found for {row["code"]}', body=series['title'], link=f'/tv/series/{task["series_id"]}')
                        elif item['state'] != 'retry':
                            self.store.notify(media_type='tv', source='follow', task_id=task_id,
                                episode_key=row['code'], event_key=f'task:{task_id}:{row["id"]}:retry', severity='warning',
                                title=f'No source yet for {row["code"]}', body=series['title'], link=f'/tv/series/{task["series_id"]}')
                    except Exception as error:
                        state, retry = 'retry', now+3600
                        results.append({'task_id': task_id, 'episode_id': row['id'], 'error': str(error), 'submitted': False})
                        intent_id = None
                with self.store.transaction() as db:
                    db.execute('UPDATE tv_task_episodes SET state=?,next_retry=?,last_search=?,error=?,intent_id=COALESCE(?,intent_id) WHERE task_id=? AND episode_id=?',
                               (state, retry, now if state in {'queued','retry'} else item['last_search'],
                                results[-1].get('error', '') if results and results[-1].get('episode_id') == row['id'] else '',
                                intent_id if state in {'queued','retry'} else None, task_id, row['id']))
                    if state in {'queued','retry'}:
                        db.execute('UPDATE tv_tasks SET last_search=? WHERE id=?', (now, task_id))
            self._settle(task_id)
            with self.store.transaction() as db:
                db.execute('UPDATE tv_tasks SET next_due=?,updated_at=? WHERE id=?', (now+60, now, task_id))
        return results

    def _settle(self, task_id):
        task = self.task(task_id)
        states = [row['state'] for row in task['episodes']]
        if task['kind'] == 'bulk' and (not states or all(state in {'acquired','retry','needs_review','queued'} for state in states)):
            state = 'completed'
        elif (states and all(state == 'acquired' for state in states)) or (not states and task['action'] != 'future'):
            series = self._series(task['series_id'])
            if task['action'] == 'future' and task['scope'] == 'season' and str(series.get('status') or '').casefold() != 'ended':
                state = 'waiting_season_end'
            elif task['action'] == 'future' and task['scope'] == 'series' and str(series.get('status') or '').casefold() != 'ended':
                state = 'waiting'
            elif task['action'] == 'future' and self.tv.hydration(task['series_id'])['status'] != 'complete':
                state = 'needs_review'
            else:
                state = 'completed'
        elif not states and task['action'] == 'future':
            series = self._series(task['series_id'])
            state = 'completed' if str(series.get('status') or '').casefold() == 'ended' and self.tv.hydration(task['series_id'])['status'] == 'complete' else 'waiting'
        else:
            state = 'running'
        if state != task['state']:
            with self.store.transaction() as db:
                db.execute('UPDATE tv_tasks SET state=?,updated_at=? WHERE id=?', (state, self.clock(), task_id))
            if state == 'completed':
                self.store.notify(media_type='tv', source='follow', task_id=task_id,
                    event_key=f'task:{task_id}:completed', severity='info', title='TV task completed',
                    body=self._series(task['series_id'])['title'], link=f'/tv/series/{task["series_id"]}')
