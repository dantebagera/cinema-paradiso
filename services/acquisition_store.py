"""Acquisition policy/intent only. Transfer recovery stays in jobs.json."""
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import time
import uuid

from services.tv_catalog_store import guarded_path
from services.acquisition_profiles import default_profile, validate_profile


class AcquisitionRepository:
    def __init__(self, path, *, quality='1080p', clock=time.time):
        self.path, self.clock = guarded_path(path), clock
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            if db.execute('PRAGMA user_version').fetchone()[0] > 2:
                raise ValueError('Acquisition schema is newer than this application')
            db.executescript('''
                CREATE TABLE IF NOT EXISTS profiles(id TEXT PRIMARY KEY,name TEXT NOT NULL,payload TEXT NOT NULL,version INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS monitors(target TEXT PRIMARY KEY,parent TEXT,mode TEXT NOT NULL,profile_id TEXT REFERENCES profiles(id),next_due REAL NOT NULL DEFAULT 0,failures INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS decisions(token TEXT PRIMARY KEY,target TEXT NOT NULL,payload TEXT NOT NULL,created_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS intents(id TEXT PRIMARY KEY,request_key TEXT NOT NULL UNIQUE,target TEXT NOT NULL,profile_id TEXT NOT NULL REFERENCES profiles(id),decision_token TEXT NOT NULL REFERENCES decisions(token),info_hash TEXT NOT NULL,state TEXT NOT NULL,created_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS intent_claims(target TEXT PRIMARY KEY,intent_id TEXT NOT NULL REFERENCES intents(id));
                CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,intent_id TEXT,event TEXT NOT NULL,payload TEXT NOT NULL,created_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS blocklist(target TEXT NOT NULL,info_hash TEXT NOT NULL,reason TEXT NOT NULL,expires_at REAL NOT NULL,PRIMARY KEY(target,info_hash));
                CREATE TABLE IF NOT EXISTS leases(work_key TEXT PRIMARY KEY,owner TEXT NOT NULL,expires_at REAL NOT NULL,reserved_bytes INTEGER NOT NULL DEFAULT 0);
                CREATE UNIQUE INDEX IF NOT EXISTS active_target ON intents(target) WHERE state IN ('selected','submitted','import_pending');
                CREATE TABLE IF NOT EXISTS batches(request_key TEXT PRIMARY KEY,tokens TEXT NOT NULL,payload TEXT NOT NULL,created_at REAL NOT NULL);
                PRAGMA user_version=2;
            ''')
            profile = default_profile(compatibility=True, quality=quality)
            db.execute('INSERT OR IGNORE INTO profiles VALUES(?,?,?,?)', (profile['id'], profile['name'], json.dumps(profile), 1))
            profile = default_profile()
            db.execute('INSERT OR IGNORE INTO profiles VALUES(?,?,?,?)', (profile['id'], profile['name'], json.dumps(profile), 1))
            db.execute("INSERT OR IGNORE INTO settings VALUES('movie_default','cp-compatibility')")
            db.commit()

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('PRAGMA synchronous=FULL')
        try:
            yield db
        finally:
            db.close()

    @contextmanager
    def transaction(self):
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                yield db
                db.commit()
            except BaseException:
                db.rollback()
                raise

    def profile(self, profile_id=None):
        with self.connection() as db:
            if profile_id is None:
                profile_id = db.execute("SELECT value FROM settings WHERE key='movie_default'").fetchone()[0]
            row = db.execute('SELECT payload FROM profiles WHERE id=?', (profile_id,)).fetchone()
            if not row:
                raise LookupError('Quality profile not found')
            return json.loads(row[0])

    def batch(self, request_key, tokens):
        with self.transaction() as db:
            row = db.execute('SELECT * FROM batches WHERE request_key=?', (request_key,)).fetchone()
            serialized = json.dumps(tokens)
            if row:
                if row['tokens'] != serialized:
                    raise ValueError('Batch key belongs to a different selection')
                return json.loads(row['payload'])
            result = {'request_key': request_key, 'items': []}
            db.execute('INSERT INTO batches VALUES(?,?,?,?)', (request_key, serialized, json.dumps(result), self.clock()))
            return result

    def save_batch(self, result):
        with self.transaction() as db:
            db.execute('UPDATE batches SET payload=? WHERE request_key=?', (json.dumps(result), result['request_key']))

    def profiles(self):
        with self.connection() as db:
            return [json.loads(row[0]) for row in db.execute('SELECT payload FROM profiles ORDER BY name')]

    def save_profile(self, profile, *, make_default=False):
        value = validate_profile(profile)
        with self.transaction() as db:
            existing = db.execute('SELECT version FROM profiles WHERE id=?', (value['id'],)).fetchone()
            value['version'] = existing[0] + 1 if existing else 1
            db.execute('INSERT INTO profiles VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,payload=excluded.payload,version=excluded.version', (value['id'], value['name'], json.dumps(value), value['version']))
            if make_default:
                db.execute("UPDATE settings SET value=? WHERE key='movie_default'", (value['id'],))
        return value

    def delete_profile(self, profile_id, replacement=None):
        with self.transaction() as db:
            referenced = db.execute('SELECT 1 FROM monitors WHERE profile_id=? UNION SELECT 1 FROM intents WHERE profile_id=? UNION SELECT 1 FROM settings WHERE value=?', (profile_id, profile_id, profile_id)).fetchone()
            if referenced:
                if not replacement or replacement == profile_id or not db.execute('SELECT 1 FROM profiles WHERE id=?', (replacement,)).fetchone():
                    raise ValueError('A referenced profile must be reassigned before deletion')
                for table in ('monitors', 'intents'):
                    db.execute(f'UPDATE {table} SET profile_id=? WHERE profile_id=?', (replacement, profile_id))
                db.execute('UPDATE settings SET value=? WHERE value=?', (replacement, profile_id))
            db.execute('DELETE FROM profiles WHERE id=?', (profile_id,))

    def record_decision(self, decision):
        with self.transaction() as db:
            db.execute('INSERT INTO decisions VALUES(?,?,?,?) ON CONFLICT(token) DO UPDATE SET created_at=excluded.created_at', (decision['decision_token'], decision['target'], json.dumps(decision), self.clock()))

    def decision(self, token, max_age=900):
        with self.connection() as db:
            row = db.execute('SELECT * FROM decisions WHERE token=?', (token,)).fetchone()
        if not row or self.clock() - row['created_at'] > max_age:
            raise ValueError('Decision expired; search and review again')
        return json.loads(row['payload'])

    def intent(self, request_key, decision):
        with self.transaction() as db:
            existing = db.execute('SELECT * FROM intents WHERE request_key=?', (request_key,)).fetchone()
            if existing:
                if existing['decision_token'] != decision['decision_token']:
                    raise ValueError('Idempotency key belongs to a different decision')
                return dict(existing)
            identity = uuid.uuid4().hex
            try:
                db.execute('INSERT INTO intents VALUES(?,?,?,?,?,?,?,?)', (identity, request_key, decision['target'], decision['profile_id'], decision['decision_token'], decision['candidate']['info_hash'], 'selected', self.clock()))
                claims = [f'tv:episode:{episode_id}' for episode_id in decision.get('covered_episodes', [])] or [decision['target']]
                for target in claims:
                    db.execute('INSERT INTO intent_claims VALUES(?,?)', (target, identity))
            except sqlite3.IntegrityError as error:
                raise ValueError('An acquisition is already outstanding for this target') from error
            return dict(db.execute('SELECT * FROM intents WHERE id=?', (identity,)).fetchone())

    def event(self, intent_id, event, payload=None, *, state=None):
        with self.transaction() as db:
            db.execute('INSERT INTO events(intent_id,event,payload,created_at) VALUES(?,?,?,?)', (intent_id, event, json.dumps(payload or {}), self.clock()))
            if state:
                db.execute('UPDATE intents SET state=? WHERE id=?', (state, intent_id))
                if state in {'ready', 'cancelled', 'failed_terminal'}:
                    db.execute('DELETE FROM intent_claims WHERE intent_id=?', (intent_id,))

    def block(self, target, info_hash, reason, ttl=86400):
        with self.transaction() as db:
            db.execute('INSERT OR REPLACE INTO blocklist VALUES(?,?,?,?)', (target, info_hash, reason, self.clock()+ttl))

    def blocked(self, target, info_hash):
        with self.connection() as db:
            return bool(db.execute('SELECT 1 FROM blocklist WHERE target=? AND info_hash=? AND expires_at>?', (target, info_hash, self.clock())).fetchone())

    def lease(self, work_key, owner, ttl=60, reserved_bytes=0, available_bytes=None):
        with self.transaction() as db:
            now = self.clock()
            db.execute('DELETE FROM leases WHERE expires_at<=?', (now,))
            previous = db.execute('SELECT * FROM leases WHERE work_key=?', (work_key,)).fetchone()
            if previous and previous['owner'] != owner:
                return False
            reserved = db.execute('SELECT COALESCE(SUM(reserved_bytes),0) FROM leases WHERE work_key<>?', (work_key,)).fetchone()[0]
            if available_bytes is not None and reserved + reserved_bytes > available_bytes:
                return False
            db.execute('INSERT OR REPLACE INTO leases VALUES(?,?,?,?)', (work_key, owner, now+ttl, reserved_bytes))
            return True

    def release_lease(self, work_key, owner):
        with self.transaction() as db:
            db.execute('DELETE FROM leases WHERE work_key=? AND owner=?', (work_key, owner))

    def audit(self, jobs=None):
        with self.connection() as db:
            orphans = {
                'intent_decisions': db.execute('SELECT COUNT(*) FROM intents i LEFT JOIN decisions d ON d.token=i.decision_token WHERE d.token IS NULL').fetchone()[0],
                'intent_profiles': db.execute('SELECT COUNT(*) FROM intents i LEFT JOIN profiles p ON p.id=i.profile_id WHERE p.id IS NULL').fetchone()[0],
                'claims': db.execute('SELECT COUNT(*) FROM intent_claims c LEFT JOIN intents i ON i.id=c.intent_id WHERE i.id IS NULL').fetchone()[0],
                'events': db.execute('SELECT COUNT(*) FROM events e LEFT JOIN intents i ON i.id=e.intent_id WHERE i.id IS NULL').fetchone()[0],
            }
            intents = {row['id']: row['info_hash'] for row in db.execute('SELECT id,info_hash FROM intents')}
            result = {'integrity': db.execute('PRAGMA integrity_check').fetchone()[0],
                      'foreign_keys': [tuple(row) for row in db.execute('PRAGMA foreign_key_check')],
                      'schema_version': db.execute('PRAGMA user_version').fetchone()[0], 'orphans': orphans}
        if jobs is not None:
            values = jobs.all() if hasattr(jobs, 'all') else dict(jobs)
            result['orphans']['transfer_jobs'] = sum(1 for job in values.values() if job.get('acquisition_id') and job['acquisition_id'] not in intents)
            result['orphans']['acquisition_links'] = sum(1 for intent_id, info_hash in intents.items()
                                                          if info_hash not in values or values[info_hash].get('acquisition_id') != intent_id)
        return result
