"""One transactional awards owner, separate from CP catalog and provider data."""
from contextlib import closing, contextmanager
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import time
import uuid

ORGANIZATIONS = ('oscar', 'golden_globe')


class AwardsError(ValueError):
    pass


class AwardsUnavailable(RuntimeError):
    pass


class GenerationConflict(AwardsError):
    def __init__(self, generation):
        super().__init__('awards_generation_changed')
        self.generation = generation


@dataclass(frozen=True)
class Lease:
    organization: str
    ceremony: int
    ceremony_year: int
    token: str
    expires_at: datetime


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def _hash(value):
    return hashlib.sha256((_json(value) + '\n').encode('utf-8')).hexdigest()


def _positive(value):
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _utc(value):
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise AwardsError('aware_utc_timestamp_required')
    return value.astimezone(timezone.utc).isoformat()


def empty_snapshot():
    return {'schema_version': 1, 'ready': False, 'awards_generation': 0,
            'coverage': {org: {'status': 'pending', 'last_committed_year': None} for org in ORGANIZATIONS},
            'movies': {}, 'people': {}}


SCHEMA = """
CREATE TABLE awards_meta(id INTEGER PRIMARY KEY CHECK(id=1), generation INTEGER NOT NULL,
                        coverage TEXT NOT NULL, seed_hash TEXT);
INSERT INTO awards_meta VALUES(1,0,'{}',NULL);
CREATE TABLE identity_mappings(entity_id TEXT PRIMARY KEY, namespace TEXT NOT NULL CHECK(namespace IN ('movie','person')),
 imdb_id TEXT NOT NULL, tmdb_id INTEGER NOT NULL CHECK(tmdb_id>0), evidence TEXT NOT NULL, facts TEXT NOT NULL,
 UNIQUE(namespace,imdb_id), UNIQUE(namespace,tmdb_id));
CREATE TABLE ceremony_imports(organization TEXT NOT NULL, ceremony INTEGER NOT NULL, ceremony_year INTEGER NOT NULL,
 content_hash TEXT NOT NULL, validation TEXT NOT NULL, committed_at TEXT NOT NULL,
 PRIMARY KEY(organization,ceremony));
CREATE TABLE film_contributions(organization TEXT NOT NULL, ceremony INTEGER NOT NULL, film_identity TEXT NOT NULL,
 wins INTEGER NOT NULL CHECK(wins>0), PRIMARY KEY(organization,ceremony,film_identity),
 FOREIGN KEY(organization,ceremony) REFERENCES ceremony_imports ON DELETE CASCADE,
 FOREIGN KEY(film_identity) REFERENCES identity_mappings(entity_id));
CREATE TABLE person_wins(win_id TEXT PRIMARY KEY, organization TEXT NOT NULL, ceremony INTEGER NOT NULL,
 person_identity TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('actor','director')),
 award_instance TEXT NOT NULL, category TEXT NOT NULL, evidence TEXT NOT NULL,
 UNIQUE(organization,ceremony,person_identity,role,award_instance),
 FOREIGN KEY(organization,ceremony) REFERENCES ceremony_imports ON DELETE CASCADE,
 FOREIGN KEY(person_identity) REFERENCES identity_mappings(entity_id));
CREATE TABLE person_win_films(win_id TEXT NOT NULL REFERENCES person_wins ON DELETE CASCADE,
 film_identity TEXT NOT NULL REFERENCES identity_mappings(entity_id), PRIMARY KEY(win_id,film_identity));
CREATE TABLE refresh_state(organization TEXT NOT NULL, ceremony INTEGER NOT NULL, ceremony_year INTEGER NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('awaiting_month','pending','checking','complete')),
 last_attempt TEXT, next_due TEXT, reason TEXT, lease_token TEXT UNIQUE, lease_expiry TEXT,
 PRIMARY KEY(organization,ceremony));
PRAGMA user_version=1;
"""


class MovieAwardsStore:
    def __init__(self, path, *, clock=None):
        self.path = Path(path)
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    @contextmanager
    def _read(self):
        if not self.path.is_file():
            yield None
            return
        db = sqlite3.connect(self.path.resolve().as_uri() + '?mode=ro', uri=True, timeout=5)
        db.row_factory = sqlite3.Row
        try:
            if db.execute('PRAGMA user_version').fetchone()[0] != 1:
                raise AwardsUnavailable('unsupported_awards_schema')
            db.execute('BEGIN')
            yield db
        finally:
            db.close()

    @contextmanager
    def _write(self):
        if self.path.exists():
            with closing(sqlite3.connect(self.path.resolve().as_uri() + '?mode=ro', uri=True, timeout=5)) as check:
                version = check.execute('PRAGMA user_version').fetchone()[0]
                if version not in (0, 1) or (version == 0 and check.execute("SELECT 1 FROM sqlite_master WHERE type='table' LIMIT 1").fetchone()):
                    raise AwardsUnavailable('unsupported_awards_schema')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        try:
            db.execute('PRAGMA foreign_keys=ON')
            db.execute('PRAGMA busy_timeout=5000')
            deadline = time.monotonic() + 5
            while True:
                try:
                    if db.execute('PRAGMA journal_mode').fetchone()[0] != 'wal':
                        db.execute('PRAGMA journal_mode=WAL')
                    break
                except sqlite3.OperationalError as error:
                    # SQLite's journal-mode transition can report BUSY without
                    # honoring busy_timeout when two fresh owners initialize.
                    if (getattr(error, 'sqlite_errorcode', 0) & 255) not in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED) or time.monotonic() >= deadline:
                        raise
                    time.sleep(0.05)
            db.execute('BEGIN IMMEDIATE')
            # Recheck only after acquiring SQLite's writer lock: another process
            # may have installed the schema while this owner waited.
            version = db.execute('PRAGMA user_version').fetchone()[0]
            if version == 0:
                if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' LIMIT 1").fetchone():
                    raise AwardsUnavailable('unsupported_awards_schema')
                for statement in SCHEMA.split(';'):
                    if statement.strip():
                        db.execute(statement)
            elif version != 1:
                raise AwardsUnavailable('unsupported_awards_schema')
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _coverage(db):
        return json.loads(db.execute('SELECT coverage FROM awards_meta WHERE id=1').fetchone()[0])

    @staticmethod
    def _generation(db):
        return db.execute('SELECT generation FROM awards_meta WHERE id=1').fetchone()[0]

    @staticmethod
    def _candidate(contribution, identities):
        value = asdict(contribution) if is_dataclass(contribution) else dict(contribution)
        if (value.get('organization') not in ORGANIZATIONS or not _positive(value.get('ceremony'))
                or not _positive(value.get('ceremony_year')) or value['ceremony_year'] < 1929
                or not isinstance(value.get('films'), dict) or not value['films']):
            raise AwardsError('invalid_ceremony_contribution')
        for film, count in value['films'].items():
            if film not in identities or not film.startswith('movie:imdb:') or not _positive(count):
                raise AwardsError('invalid_film_contribution')
        keys, instances = set(), {}
        for win in value.get('person_wins', []):
            if (win.get('person') not in identities or not win['person'].startswith('person:imdb:')
                    or win.get('role') not in ('actor', 'director') or not win.get('award_instance')
                    or not win.get('category') or not win.get('evidence') or not win.get('films')
                    or any(film not in value['films'] for film in win['films'])):
                raise AwardsError('invalid_person_win')
            key = win['person'], win['role'], win['award_instance']
            if key in keys:
                raise AwardsError('duplicate_person_win')
            keys.add(key)
            for film in win['films']:
                instances.setdefault(film, set()).add(win['award_instance'])
        if any(len(keys) > value['films'][film] for film, keys in instances.items()):
            raise AwardsError('person_wins_exceed_film_awards')
        return {k: value[k] for k in ('organization', 'ceremony', 'ceremony_year', 'films', 'person_wins')}

    @staticmethod
    def _replace(db, value, validation, now):
        org, ceremony = value['organization'], value['ceremony']
        digest = _hash({'contribution': value, 'validation': validation})
        current = db.execute('SELECT content_hash FROM ceremony_imports WHERE organization=? AND ceremony=?', (org, ceremony)).fetchone()
        if current and current[0] == digest:
            return False
        db.execute('DELETE FROM ceremony_imports WHERE organization=? AND ceremony=?', (org, ceremony))
        db.execute('INSERT INTO ceremony_imports VALUES(?,?,?,?,?,?)', (org, ceremony, value['ceremony_year'], digest, _json(validation), now))
        db.executemany('INSERT INTO film_contributions VALUES(?,?,?,?)', [(org, ceremony, film, wins) for film, wins in value['films'].items()])
        for win in value['person_wins']:
            identifier = _hash([org, ceremony, win['person'], win['role'], win['award_instance']])
            db.execute('INSERT INTO person_wins VALUES(?,?,?,?,?,?,?,?)', (identifier, org, ceremony, win['person'], win['role'], win['award_instance'], win['category'], _json(win['evidence'])))
            db.executemany('INSERT INTO person_win_films VALUES(?,?)', [(identifier, film) for film in sorted(set(win['films']))])
        db.execute("INSERT INTO refresh_state(organization,ceremony,ceremony_year,status) VALUES(?,?,?,'complete') ON CONFLICT(organization,ceremony) DO UPDATE SET status='complete',reason=NULL,next_due=NULL,lease_token=NULL,lease_expiry=NULL", (org, ceremony, value['ceremony_year']))
        return True

    def install_seed(self, seed, manifest):
        if (seed.get('schema_version') != 1 or manifest.get('schema_version') != 1
                or manifest.get('ready') is not True or manifest.get('seed_sha256') != _hash(seed)):
            raise AwardsError('invalid_seed_schema_or_hash')
        identities, reverses, prepared = {}, set(), []
        for item in seed.get('identity_mappings', []):
            ns, imdb, tmdb = item.get('namespace'), item.get('imdb_id'), item.get('tmdb_id')
            if ns not in ('movie', 'person') or not re.fullmatch(('tt' if ns == 'movie' else 'nm') + r'\d+', imdb or '') or not _positive(tmdb) or not item.get('evidence'):
                raise AwardsError('invalid_seed_identity')
            entity = f'{ns}:imdb:{imdb}'
            if entity in identities or (ns, tmdb) in reverses:
                raise AwardsError('seed_identity_conflict')
            identities[entity] = item
            reverses.add((ns, tmdb))
        complete = {org: bounds for org, bounds in seed.get('coverage', {}).items() if bounds.get('status') == 'complete'}
        if not complete or any(org not in ORGANIZATIONS for org in seed.get('coverage', {})):
            raise AwardsError('seed_historical_coverage_unavailable')
        seen = set()
        for contribution in seed.get('ceremonies', []):
            value = self._candidate(contribution, identities)
            key = value['organization'], value['ceremony']
            validation = contribution.get('validation', {})
            if key in seen or key[0] not in complete or validation.get('crosscheck', {}).get('crosscheck_agrees') is not True or not validation.get('evidence', {}).get('revision'):
                raise AwardsError('unverified_seed_ceremony')
            seen.add(key)
            prepared.append((value, validation))
        for org, bounds in complete.items():
            first, last = bounds.get('first_ceremony'), bounds.get('last_ceremony')
            if first != 1 or not _positive(last) or {cer for organization, cer in seen if organization == org} != set(range(first, last + 1)):
                raise AwardsError('incomplete_seed_history')
        now = _utc(self.clock())
        with self._write() as db:
            changed = False
            for entity, item in identities.items():
                previous = db.execute('SELECT entity_id,imdb_id,tmdb_id FROM identity_mappings WHERE (namespace=? AND imdb_id=?) OR (namespace=? AND tmdb_id=?)', (item['namespace'], item['imdb_id'], item['namespace'], item['tmdb_id'])).fetchall()
                if any(row['entity_id'] != entity or row['tmdb_id'] != item['tmdb_id'] for row in previous):
                    raise AwardsError('installed_identity_conflict')
                if not previous:
                    db.execute('INSERT INTO identity_mappings VALUES(?,?,?,?,?,?)', (entity, item['namespace'], item['imdb_id'], item['tmdb_id'], _json(item['evidence']), _json(item.get('facts', {}))))
                    changed = True
            for value, validation in prepared:
                # Bootstrap never rewrites an existing import. Corrections use
                # explicit validated publication with an authorized lease.
                if not db.execute('SELECT 1 FROM ceremony_imports WHERE organization=? AND ceremony=?', (value['organization'], value['ceremony'])).fetchone():
                    changed |= self._replace(db, value, validation, now)
            coverage = self._coverage(db)
            for org, bounds in complete.items():
                latest = db.execute('SELECT MAX(ceremony),MAX(ceremony_year) FROM ceremony_imports WHERE organization=?', (org,)).fetchone()
                updated = {**bounds, 'last_ceremony': latest[0], 'last_committed_year': latest[1]}
                if coverage.get(org) != updated:
                    coverage[org] = updated; changed = True
            db.execute('UPDATE awards_meta SET coverage=?,seed_hash=?,generation=generation+? WHERE id=1', (_json(coverage), manifest['seed_sha256'], int(changed)))
            return self._generation(db)

    def read_snapshot(self):
        with self._read() as db:
            if db is None:
                return empty_snapshot()
            coverage = self._coverage(db)
            snapshot = empty_snapshot()
            snapshot.update(ready=any(v.get('status') == 'complete' for v in coverage.values()), awards_generation=self._generation(db))
            snapshot['coverage'].update(coverage)
            film_totals = {(r[0], r[1]): r[2] for r in db.execute('SELECT film_identity,organization,SUM(wins) FROM film_contributions GROUP BY film_identity,organization')}
            person_totals = {(r[0], r[1], r[2]): r[3] for r in db.execute('SELECT person_identity,role,organization,COUNT(*) FROM person_wins GROUP BY person_identity,role,organization')}
            for row in db.execute('SELECT entity_id,namespace,imdb_id,tmdb_id FROM identity_mappings'):
                if row['namespace'] == 'movie':
                    value = {'entity_id': row['entity_id'], **{org: film_totals.get((row['entity_id'], org), 0) if coverage.get(org, {}).get('status') == 'complete' else None for org in ORGANIZATIONS}}
                    snapshot['movies'][f"tmdb:{row['tmdb_id']}"] = value
                    snapshot['movies'][f"imdb:{row['imdb_id']}"] = value
                else:
                    snapshot['people'][f"tmdb:{row['tmdb_id']}"] = {role: {org: person_totals.get((row['entity_id'], role, org), 0) if coverage.get(org, {}).get('status') == 'complete' else None for org in ORGANIZATIONS} for role in ('actor', 'director')}
            return snapshot

    def person_films(self, person_id, role, award, page, page_size, generation=None):
        if not _positive(person_id) or role not in ('actor', 'director') or award not in ORGANIZATIONS or not _positive(page) or not _positive(page_size) or page_size > 100:
            raise AwardsError('invalid_person_awards_query')
        with self._read() as db:
            if db is None or self._coverage(db).get(award, {}).get('status') != 'complete':
                raise AwardsUnavailable('historical_awards_coverage_pending')
            active = self._generation(db)
            if generation is not None and generation != active:
                raise GenerationConflict(active)
            person = db.execute("SELECT entity_id FROM identity_mappings WHERE namespace='person' AND tmdb_id=?", (person_id,)).fetchone()
            if not person:
                raise AwardsUnavailable('person_identity_unavailable')
            wins = db.execute('SELECT COUNT(*) FROM person_wins WHERE person_identity=? AND role=? AND organization=?', (person[0], role, award)).fetchone()[0]
            rows = db.execute('SELECT m.tmdb_id,m.imdb_id,m.facts,MAX(c.ceremony_year) AS latest_year FROM person_wins w JOIN person_win_films f ON f.win_id=w.win_id JOIN identity_mappings m ON m.entity_id=f.film_identity JOIN ceremony_imports c ON c.organization=w.organization AND c.ceremony=w.ceremony WHERE w.person_identity=? AND w.role=? AND w.organization=? GROUP BY m.entity_id', (person[0], role, award)).fetchall()
            movies = [{**json.loads(r['facts']), 'id': r['tmdb_id'], 'imdb_id': r['imdb_id'], 'latest_award_year': r['latest_year']} for r in rows]
            movies.sort(key=lambda row: (-row['latest_award_year'], str(row.get('title', '')).casefold(), row['id']))
            total = len(movies); pages = max(1, (total + page_size - 1) // page_size)
            return {'results': movies[(page - 1) * page_size:page * page_size], 'page': page, 'page_size': page_size,
                    'total_pages': pages, 'total_results': total, 'has_previous': page > 1,
                    'has_next': page < pages, 'award_wins': wins, 'awards_generation': active}

    def read_status(self):
        with self._read() as db:
            if db is None:
                return {**empty_snapshot(), 'refresh': [], 'diagnostic': 'awards_store_missing'}
            return {'schema_version': 1, 'awards_generation': self._generation(db), 'coverage': self._coverage(db),
                    'refresh': [dict(row) for row in db.execute('SELECT organization,ceremony,ceremony_year,status,last_attempt,next_due,reason FROM refresh_state ORDER BY organization,ceremony')]}

    def ensure_refresh_state(self, organization, ceremony, year, next_due, *, status='pending', force=False):
        if organization not in ORGANIZATIONS or not _positive(ceremony) or not _positive(year) or status not in ('pending', 'awaiting_month'):
            raise AwardsError('invalid_refresh_job')
        with self._write() as db:
            current = db.execute('SELECT status FROM refresh_state WHERE organization=? AND ceremony=?', (organization, ceremony)).fetchone()
            if current and (not force or current[0] == 'checking'):
                return
            db.execute('INSERT INTO refresh_state(organization,ceremony,ceremony_year,status,next_due) VALUES(?,?,?,?,?) ON CONFLICT(organization,ceremony) DO UPDATE SET status=excluded.status,next_due=excluded.next_due,reason=NULL,lease_token=NULL,lease_expiry=NULL', (organization, ceremony, year, status, _utc(next_due)))

    def claim_due(self, organization, ceremony, now_utc):
        now = _utc(now_utc)
        with self._write() as db:
            row = db.execute('SELECT * FROM refresh_state WHERE organization=? AND ceremony=?', (organization, ceremony)).fetchone()
            if not row or row['status'] in ('complete', 'awaiting_month') or (row['next_due'] and row['next_due'] > now) or (row['status'] == 'checking' and row['lease_expiry'] > now):
                return None
            token = uuid.uuid4().hex; expiry = now_utc.astimezone(timezone.utc) + timedelta(minutes=15)
            db.execute("UPDATE refresh_state SET status='checking',last_attempt=?,lease_token=?,lease_expiry=? WHERE organization=? AND ceremony=?", (now, token, _utc(expiry), organization, ceremony))
            return Lease(organization, ceremony, row['ceremony_year'], token, expiry)

    def record_pending(self, lease_token, reason, next_due_utc):
        with self._write() as db:
            db.execute("UPDATE refresh_state SET status='pending',reason=?,next_due=?,lease_token=NULL,lease_expiry=NULL WHERE lease_token=? AND status='checking'", (str(reason)[:256], _utc(next_due_utc), lease_token))

    def publish_ceremony(self, contribution, evidence, lease_token):
        if evidence.complete is not True or evidence.diagnostics or evidence.evidence.get('crosscheck_agrees') is not True or not evidence.evidence.get('revision'):
            raise AwardsError('incomplete_ceremony_validation')
        with self._read() as read:
            if read is None:
                raise AwardsUnavailable('awards_store_missing')
            identities = {r[0] for r in read.execute('SELECT entity_id FROM identity_mappings')}
        new_mappings = evidence.evidence.get('identity_mappings', [])
        for item in new_mappings:
            ns, imdb, tmdb = item.get('namespace'), item.get('imdb_id'), item.get('tmdb_id')
            prefix = 'tt' if ns == 'movie' else 'nm'
            if ns not in ('movie', 'person') or not _positive(tmdb) or not re.fullmatch(prefix + r'\d+', imdb or '') or not item.get('evidence'):
                raise AwardsError('invalid_mapping_evidence')
            identities.add(f'{ns}:imdb:{imdb}')
        value = self._candidate(contribution, identities); validation = asdict(evidence)
        digest = _hash({'contribution': value, 'validation': validation})
        org, ceremony = value['organization'], value['ceremony']
        with self._write() as db:
            current = db.execute('SELECT content_hash FROM ceremony_imports WHERE organization=? AND ceremony=?', (org, ceremony)).fetchone()
            if current and current[0] == digest:
                return self._generation(db)
            if self._coverage(db).get(org, {}).get('status') != 'complete':
                raise AwardsUnavailable('historical_awards_coverage_pending')
            if ceremony > self._coverage(db)[org]['last_ceremony'] + 1:
                raise AwardsError('earlier_ceremony_pending')
            lease = db.execute("SELECT * FROM refresh_state WHERE lease_token=? AND status='checking'", (lease_token,)).fetchone()
            if not lease or (lease['organization'], lease['ceremony'], lease['ceremony_year']) != (org, ceremony, value['ceremony_year']) or lease['lease_expiry'] <= _utc(self.clock()):
                raise AwardsError('invalid_or_expired_awards_lease')
            for item in new_mappings:
                ns, imdb, tmdb = item['namespace'], item['imdb_id'], item['tmdb_id']
                entity = f'{ns}:imdb:{imdb}'
                previous = db.execute('SELECT entity_id,tmdb_id FROM identity_mappings WHERE (namespace=? AND imdb_id=?) OR (namespace=? AND tmdb_id=?)', (ns, imdb, ns, tmdb)).fetchall()
                if any(row['entity_id'] != entity or row['tmdb_id'] != tmdb for row in previous):
                    raise AwardsError('installed_identity_conflict')
                if not previous:
                    db.execute('INSERT INTO identity_mappings VALUES(?,?,?,?,?,?)', (entity, ns, imdb, tmdb, _json(item['evidence']), _json(item.get('facts', {}))))
            self._replace(db, value, validation, _utc(self.clock()))
            coverage = self._coverage(db)
            latest = db.execute('SELECT MAX(ceremony),MAX(ceremony_year) FROM ceremony_imports WHERE organization=?', (org,)).fetchone()
            coverage[org].update(last_ceremony=latest[0], last_committed_year=latest[1])
            db.execute('UPDATE awards_meta SET generation=generation+1,coverage=? WHERE id=1', (_json(coverage),))
            return self._generation(db)

    def read_identity_mappings(self):
        with self._read() as db:
            return [] if db is None else [
                {**dict(row), 'evidence': json.loads(row['evidence']), 'facts': json.loads(row['facts'])}
                for row in db.execute('SELECT namespace,imdb_id,tmdb_id,evidence,facts FROM identity_mappings')]
