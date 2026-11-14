"""Lazy GPT operation state. Catalogue, acquisition and mutation truth stay elsewhere."""
from contextlib import contextmanager, closing
from dataclasses import asdict
import hashlib
from itertools import groupby
import base64
import binascii
import json
import os
from pathlib import Path
import sqlite3
import threading
import time
from urllib.parse import quote
import uuid

from services.ai_provider import AISelection, canonical_count
from services.chatgpt_skills import IPTV_BULK_PROTOCOL_HASH
from services.iptv_tmdb import BULK_SEARCH_LIMIT_REASON
from services.process_liveness import pid_alive as _pid_alive


STATES = frozenset(('queued', 'running', 'awaiting_clarification', 'awaiting_confirmation', 'paused_budget',
                    'paused', 'completed', 'partial', 'failed', 'cancelled', 'interrupted'))
COVERAGE = frozenset(('complete', 'partial', 'unknown'))
BULK_MAX_CALLS = 10_000
BULK_OUTCOMES = ('verified', 'unmatched', 'categorized', 'review', 'failed')
BULK_APPLY_ACTIVE = frozenset(('running', 'stopping', 'interrupted'))
_STALE_CATALOG_MESSAGES = ('iptv_selection_changed', 'The provider catalog changed. Start a new review.')
_APPLY_STATE = "coalesce(json_extract(payload,'$.apply_state'),'')"
_OUTCOME = "json_extract(payload,'$.outcome')"
_SEARCH_RECHECK = f"""{_OUTCOME}='review' AND json_extract(payload,'$.category')='film'
    AND {_APPLY_STATE} IN ('','stale') AND json_type(payload,'$.evidence.interpretation')='object'
    AND json_type(payload,'$.evidence.identity')='object'
    AND coalesce(json_extract(payload,'$.evidence.search_recheck'),0)=0
    AND (json_extract(payload,'$.evidence.review_code')='recovery_search_limited'
         OR json_extract(payload,'$.review_reason') IN (?, ?, ?))"""
_SEARCH_LIMIT_MESSAGES = (BULK_SEARCH_LIMIT_REASON,
    'Candidate search limit reached before competing identities could be ruled out.',
    'The candidate search limit was reached before rivals could be ruled out.')
_VERIFIED_FILM = f"""({_OUTCOME}='verified' AND json_extract(payload,'$.category')='film'
    AND json_type(payload,'$.candidate_tmdb_id')='integer' AND json_extract(payload,'$.candidate_tmdb_id')>0
    AND coalesce(json_extract(payload,'$.match_manual_lock'),0)=0)"""
_BULK_REVIEW = {
    'pending_matches': f"{_VERIFIED_FILM} AND {_APPLY_STATE}=''",
    'applied': f"{_APPLY_STATE}='applied'",
    'needs_attention': f"({_OUTCOME} IN ('unmatched','review','failed') AND {_APPLY_STATE}<>'applied') OR {_APPLY_STATE} IN ('locked','skipped','failed','stale')",
    'classifications': f"{_OUTCOME} IN ('categorized','unmatched','review') AND {_APPLY_STATE}='' "
                       "AND json_extract(payload,'$.category') NOT IN ('unclassified',json_extract(payload,'$.previous_category')) "
                       "AND json_extract(payload,'$.classification_confidence')>=0.9 "
                       "AND coalesce(json_extract(payload,'$.locked'),0)=0 AND coalesce(json_extract(payload,'$.match_manual_lock'),0)=0",
    'retry_failed': f"{_VERIFIED_FILM} AND {_APPLY_STATE}='failed' AND json_extract(payload,'$.apply_retryable')=1",
}
_APPLY_VIEWS = {'verified_pending': 'pending_matches', 'retry_failed': 'retry_failed'}


class AIJobError(RuntimeError):
    def __init__(self, code, status=409):
        self.code, self.status = code, status
        super().__init__(code)


def _json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def _inference_budget(request, cursor):
    return cursor.get('bulk_budget', request.get('bulk_call_budget', 24))


def bulk_catalog_generation(job):
    return job['cursor'].get('bulk_catalog_generation', job['request']['selection_snapshot']['catalog_generation'])


def supports_bulk_catalog_resume(request):
    return (bool(request.get('bulk_auto_apply')) and not request.get('bulk_recovery_protocol_hash')
            and request.get('bulk_protocol_hash') == IPTV_BULK_PROTOCOL_HASH)


def _stale_catalog_failure(state, message):
    return state == 'failed' and message in _STALE_CATALOG_MESSAGES


def _unfinished_search_recheck(cursor):
    recheck = cursor.get('bulk_search_recheck')
    return bool(recheck and recheck['processed'] < len(recheck['keys']))


def bulk_failed_after_sync(job):
    return (supports_bulk_catalog_resume(job['request']) and _stale_catalog_failure(job['state'], job.get('message'))
            and (job['accepted_count'] < len(job['request']['selection_snapshot']['source_keys'])
                 or _unfinished_search_recheck(job['cursor'])
                 or bool(job['cursor'].get('bulk_automatic_pending'))))


def bulk_extra_calls(request, cursor):
    size = request.get('titles_per_request', 100)
    work = cursor.get('bulk_work', {})
    remaining = work.get('source_count', len(request['selection_snapshot']['source_keys'])) - work.get('offset', 0)
    pending_calls = 0
    for attempts, rows in groupby(work.get('pending', []), key=lambda item: item[1]):
        capacity = min(size, 50) if attempts else size
        pending_calls += (sum(1 for _ in rows) + capacity - 1) // capacity
    initial = (remaining + size - 1) // size
    if request.get('bulk_recovery_protocol_hash'):
        recovery = len(work.get('recovery', {}).get('pending', []))
        pending_calls = 3 * (pending_calls + initial + 2 * ((remaining + min(size, 50) - 1) // min(size, 50)))
        return min(BULK_MAX_CALLS - _inference_budget(request, cursor), pending_calls + remaining + recovery)
    return min(BULK_MAX_CALLS - _inference_budget(request, cursor), pending_calls + initial)


SCHEMA = '''
BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS sessions (
 id TEXT PRIMARY KEY, account_id TEXT NOT NULL, turns TEXT NOT NULL, constraints_json TEXT NOT NULL,
 created REAL NOT NULL, updated REAL NOT NULL);
CREATE TABLE IF NOT EXISTS jobs (
 id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id), account_id TEXT NOT NULL,
 session_key TEXT NOT NULL, feature TEXT NOT NULL, selection_json TEXT NOT NULL, request_json TEXT NOT NULL,
 request_key TEXT NOT NULL, digest TEXT NOT NULL, target TEXT, state TEXT NOT NULL, coverage TEXT NOT NULL,
 revision INTEGER NOT NULL DEFAULT 0, run_calls INTEGER NOT NULL DEFAULT 0, cursor_json TEXT NOT NULL DEFAULT '{}',
 message TEXT NOT NULL DEFAULT '', output_json TEXT, owner_pid INTEGER, last_continue_key TEXT,
 created REAL NOT NULL, updated REAL NOT NULL,
 UNIQUE(account_id,session_key,feature,request_key));
CREATE TABLE IF NOT EXISTS result_items (
 job_id TEXT NOT NULL REFERENCES jobs(id), domain TEXT NOT NULL, identity TEXT NOT NULL,
 position INTEGER NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(job_id,domain,identity));
CREATE INDEX IF NOT EXISTS result_page ON result_items(job_id,position);
CREATE TABLE IF NOT EXISTS events (
 sequence INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL REFERENCES jobs(id),
 kind TEXT NOT NULL, payload TEXT NOT NULL, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS action_receipts (
 scope_id TEXT NOT NULL, request_key TEXT NOT NULL, digest TEXT NOT NULL, state TEXT NOT NULL,
 owner_reference TEXT NOT NULL, updated REAL NOT NULL, PRIMARY KEY(scope_id,request_key));
CREATE TABLE IF NOT EXISTS inference_leases (
 id TEXT PRIMARY KEY, job_id TEXT NOT NULL, owner_pid INTEGER NOT NULL, owner_id TEXT NOT NULL, expires REAL NOT NULL);
PRAGMA user_version=1;
COMMIT;
'''


class AIJobStore:
    def __init__(self, user_data_dir, *, clock=time.time, process_alive=_pid_alive):
        self.path = Path(user_data_dir).resolve() / 'ai' / 'ai.sqlite'
        self.clock, self.process_alive = clock, process_alive
        self.owner_id = uuid.uuid4().hex
        self._schema_lock = threading.Lock()
        self._initialized = False
        # Live display hints only. Durable state/revisions remain authoritative.
        self._progress_lock = threading.Lock()
        self._progress = {}

    def progress_reporter(self, job_id):
        with self._progress_lock:
            entry = self._progress.get(job_id)

        def report(phase):
            if phase not in ('preparing', 'connecting', 'retrieving', 'matching', 'waiting_slot', 'backoff'):
                return
            with self._progress_lock:
                if entry is not None and self._progress.get(job_id) is entry:
                    entry['phase'] = phase
        return report

    def _clear_progress(self, job_id):
        with self._progress_lock:
            self._progress.pop(job_id, None)

    def _initialize(self):
        with self._schema_lock:
            if self._initialized:
                return
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with closing(sqlite3.connect(self.path, timeout=30)) as connection:
                version = connection.execute('PRAGMA user_version').fetchone()[0]
                if version not in (0, 1):
                    raise AIJobError('ai_store_migration_required')
                if version == 0:
                    if (connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchone()
                            and connection.execute('PRAGMA user_version').fetchone()[0] != 1):
                        raise AIJobError('unrecognized_ai_store')
                    connection.execute('PRAGMA journal_mode=WAL')
                    connection.executescript(SCHEMA)
            self._initialized = True

    @contextmanager
    def _connection(self, *, write=False):
        if write:
            self._initialize()
            connection = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        else:
            if not self.path.is_file():
                raise AIJobError('job_not_found', 404)
            connection = sqlite3.connect('file:' + quote(self.path.as_posix(), safe='/:') + '?mode=ro',
                                         uri=True, timeout=30, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA foreign_keys=ON')
        try:
            if write:
                connection.execute('BEGIN IMMEDIATE')
            yield connection
            if write:
                connection.commit()
        except BaseException:
            if write:
                connection.rollback()
            raise
        finally:
            connection.close()

    def _job(self, connection, job_id):
        row = connection.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
        if not row:
            raise AIJobError('job_not_found', 404)
        return row

    def _session(self, connection, session_id, account_id):
        row = connection.execute('SELECT * FROM sessions WHERE id=?', (session_id,)).fetchone()
        if not row or row['account_id'] != account_id:
            raise AIJobError('session_account_mismatch')
        if self.clock() - row['updated'] >= 7 * 86400:
            raise AIJobError('new_session_required', 410)
        return row

    def create(self, feature, selection, request, request_key):
        if selection.provider != 'chatgpt' or selection.feature != feature or not selection.account_id:
            raise AIJobError('invalid_selection', 400)
        if not isinstance(request_key, str) or not 1 <= len(request_key) <= 160:
            raise AIJobError('invalid_request_key', 400)
        request = dict(request)
        bulk = 'bulk_call_budget' in request
        if bulk and (feature != 'F5' or not selection.domain_id or request.get('parent_job_id')
                     or type(request['bulk_call_budget']) is not int
                     or not 1 <= request['bulk_call_budget'] <= BULK_MAX_CALLS
                     or not request.get('selection_snapshot', {}).get('source_keys')):
            raise AIJobError('invalid_bulk_request', 400)
        if feature == 'F1':
            if 'count' not in request:
                raise AIJobError('count_required', 400)
            request['count'] = canonical_count(request['count'])
        selection_json, request_json = _json(selection.public()), _json(request)
        digest = hashlib.sha256((selection_json + request_json).encode()).hexdigest()
        client_session = request.get('session_id') or 'new'
        with self._connection(write=True) as connection:
            existing = connection.execute('SELECT id,digest FROM jobs WHERE account_id=? AND session_key=? AND feature=? AND request_key=?',
                (selection.account_id, client_session, feature, request_key)).fetchone()
            if existing:
                if existing['digest'] != digest:
                    raise AIJobError('request_key_conflict')
                job_id = existing['id']
            else:
                if bulk:
                    self._guard_bulk_slot(connection, selection.account_id, selection.domain_id)
                session_id = request.get('session_id')
                now = self.clock()
                if session_id:
                    self._session(connection, session_id, selection.account_id)
                    if not request.get('parent_job_id') and connection.execute(
                            "SELECT 1 FROM jobs WHERE session_id=? AND state IN ('queued','running') LIMIT 1", (session_id,)).fetchone():
                        raise AIJobError('session_busy; wait for the current turn or use another session')
                else:
                    session_id = uuid.uuid4().hex
                    connection.execute('INSERT INTO sessions VALUES (?,?,?,?,?,?)',
                        (session_id, selection.account_id, '[]', '{}', now, now))
                if request.get('parent_job_id'):
                    parent = self._job(connection, request['parent_job_id'])
                    parent_selection = json.loads(parent['selection_json'])
                    if (parent['session_id'] != session_id or parent['account_id'] != selection.account_id
                            or parent['feature'] != 'F2' or parent['state'] != 'running'
                            or parent_selection['model'] != selection.model):
                        raise AIJobError('invalid_parent_job')
                if feature in ('F4', 'F5'):
                    self._mark_evidence(connection, session_id, selection.account_id, 'iptv_titles')
                job_id = uuid.uuid4().hex
                connection.execute('''INSERT INTO jobs
                    (id,session_id,account_id,session_key,feature,selection_json,request_json,request_key,digest,target,
                     state,coverage,created,updated) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                    (job_id, session_id, selection.account_id, client_session, feature, selection_json, request_json,
                     request_key, digest, request.get('count'), 'queued', 'unknown', now, now))
                if bulk:
                    connection.execute('UPDATE jobs SET owner_pid=? WHERE id=?', (os.getpid(), job_id))
        return self.snapshot(job_id)

    @staticmethod
    def _guard_bulk_slot(connection, account_id, provider_id, *, except_id=''):
        if connection.execute("""SELECT 1 FROM jobs WHERE account_id=? AND feature='F5' AND id<>?
                AND (state IN ('queued','running','paused','paused_budget','interrupted')
                     OR json_extract(cursor_json,'$.bulk_apply.state') IN ('running','stopping','interrupted'))
                AND json_extract(request_json,'$.bulk_call_budget') IS NOT NULL
                AND json_extract(selection_json,'$.domain_id')=? LIMIT 1""",
                (account_id, except_id, provider_id)).fetchone():
            raise AIJobError('bulk_job_already_active')

    def snapshot(self, job_id, *, page=1, page_size=20, cursor=None, review_view=None):
        if isinstance(page, bool) or not isinstance(page, int) or page < 1 or not isinstance(page_size, int) or not 1 <= page_size <= 100:
            raise AIJobError('invalid_page', 400)
        if cursor is not None:
            try:
                token = json.loads(base64.urlsafe_b64decode(cursor + '=' * (-len(cursor) % 4)))
                offset = token['offset']
                if (token['job_id'] != job_id or token['page_size'] != page_size or type(offset) is not int
                        or offset < 0 or offset > 2**63 - 1 or offset % page_size or page not in (1, offset // page_size + 1)):
                    raise ValueError('Cursor binding mismatch')
                page = offset // page_size + 1
            except (ValueError, TypeError, KeyError, binascii.Error, UnicodeError):
                raise AIJobError('invalid_page_cursor', 400) from None
        with self._connection() as connection:
            connection.execute('BEGIN')  # Job metadata, counters and result page share one checkpoint.
            row = self._job(connection, job_id)
            request = json.loads(row['request_json'])
            filters = {}
            if review_view is not None:
                if review_view not in _BULK_REVIEW or review_view == 'retry_failed' or 'bulk_call_budget' not in request or cursor:
                    raise AIJobError('invalid_bulk_review_view', 400)
                counts_sql = ', '.join(f"count(CASE WHEN domain='iptv' AND ({condition}) THEN 1 END) AS {name}"
                                       for name, condition in _BULK_REVIEW.items())
                counts = connection.execute(f'SELECT count(*) AS total, {counts_sql} FROM result_items WHERE job_id=?',
                                            (job_id,)).fetchone()
                count = counts['total']
                view_count = counts[review_view]
                page = min(page, max(1, (view_count + page_size - 1) // page_size))
                filters = {'review_counts': {name: counts[name] for name in _BULK_REVIEW}, 'review_view': review_view}
                predicate = f" AND domain='iptv' AND ({_BULK_REVIEW[review_view]})"
            else:
                view_count = count = connection.execute('SELECT count(*) FROM result_items WHERE job_id=?', (job_id,)).fetchone()[0]
                predicate = ''
            items = connection.execute('SELECT domain,identity,payload FROM result_items WHERE job_id=?'
                f'{predicate} ORDER BY position LIMIT ? OFFSET ?',
                (job_id, page_size, (page - 1) * page_size)).fetchall()
            state = row['state']
            if (state == 'running' or (state == 'queued' and 'bulk_call_budget' in request)) and (
                    row['owner_pid'] and not self.process_alive(row['owner_pid'])):
                state = 'interrupted'  # Read-only observation, not replay or a polling write.
            with self._progress_lock:
                phase = (self._progress.get(job_id, {}).get('phase')
                         if state == 'running' and row['owner_pid'] == os.getpid() else None)
            checkpoint = json.loads(row['cursor_json'])
            apply = self._observed_bulk_apply(checkpoint)
            recheck_count = 0
            if state == 'completed' and supports_bulk_catalog_resume(request):
                recheck_count = connection.execute(f"SELECT count(*) FROM result_items WHERE job_id=? AND domain='iptv' AND {_SEARCH_RECHECK}",
                    (job_id, *_SEARCH_LIMIT_MESSAGES)).fetchone()[0]
            return {'id': row['id'], 'session_id': row['session_id'], 'feature': row['feature'],
                'selection': json.loads(row['selection_json']), 'request': request,
                'requested_count': row['target'], 'accepted_count': count, 'state': state, 'progress_phase': phase,
                'coverage': row['coverage'], 'revision': row['revision'], 'run_calls': row['run_calls'],
                'inference_budget': _inference_budget(request, checkpoint), 'cursor': checkpoint, 'message': row['message'],
                'output': json.loads(row['output_json']) if row['output_json'] else None,
                **({'search_recheck_candidates': recheck_count} if 'bulk_call_budget' in request else {}),
                'page': page, 'page_size': page_size, 'has_more': page * page_size < view_count,
                'next_cursor': base64.urlsafe_b64encode(_json({'job_id': job_id, 'page_size': page_size,
                    'offset': page * page_size}).encode()).decode().rstrip('=') if not filters and page * page_size < count else None,
                **filters, **({'bulk_apply': apply} if apply else {}),
                'results': [dict(json.loads(item['payload']), result_domain=item['domain'], result_identity=item['identity']) for item in items]}

    def latest_bulk_job(self, account_id, provider_id, **page):
        if not self.path.is_file():
            return None
        with self._connection() as connection:
            row = connection.execute("""SELECT id FROM jobs WHERE account_id=? AND feature='F5'
                AND json_extract(request_json,'$.bulk_call_budget') IS NOT NULL
                AND json_extract(selection_json,'$.domain_id')=? ORDER BY created DESC,rowid DESC LIMIT 1""",
                (account_id, provider_id)).fetchone()
        return self.snapshot(row['id'], **page) if row else None

    def _observed_bulk_apply(self, cursor):
        apply = cursor.get('bulk_apply')
        if apply and apply['state'] in ('running', 'stopping') and not self.process_alive(apply['owner_pid']):
            return {**apply, 'state': 'interrupted', 'reason': 'CP stopped before Apply finished.'}
        return apply

    def _guard_bulk_apply(self, cursor):
        apply = self._observed_bulk_apply(cursor)
        if ((apply and apply['state'] in BULK_APPLY_ACTIVE) or
                ((owner := cursor.get('bulk_explicit_owner')) and self.process_alive(owner))):
            raise AIJobError('bulk_apply_active')

    def _guard_bulk_review(self, row, cursor):
        if row['state'] in ('queued', 'running') and (not row['owner_pid'] or self.process_alive(row['owner_pid'])):
            raise AIJobError('bulk_review_unavailable')
        self._guard_bulk_apply(cursor)

    def _save_bulk_cursor(self, connection, job_id, cursor):
        connection.execute('UPDATE jobs SET cursor_json=?,revision=revision+1,updated=? WHERE id=?',
                           (_json(cursor), self.clock(), job_id))

    def _new_bulk_apply(self, connection, job_id, cursor, confirmation, cutoff, *, automatic=False, start=-1):
        previous = cursor.get('bulk_apply')
        if previous:
            connection.execute('INSERT INTO events(job_id,kind,payload,created) VALUES (?,?,?,?)',
                               (job_id, 'bulk_apply', _json(previous), self.clock()))
        apply = {**confirmation, 'id': uuid.uuid4().hex, 'owner_pid': os.getpid(), 'state': 'running',
                 'position': start, 'cutoff': cutoff, 'counts': dict.fromkeys(('applied', 'locked', 'skipped', 'failed'), 0)}
        if automatic:
            apply['automatic'] = True
        cursor['bulk_apply'] = apply
        self._save_bulk_cursor(connection, job_id, cursor)
        return apply

    def claim_automatic_bulk_apply(self, job_id, *, reconcile_cancelled=False):
        with self._connection(write=True) as connection:
            row = self._job(connection, job_id)
            cursor = json.loads(row['cursor_json'])
            if not (reconcile_cancelled and row['state'] == 'cancelled') and (
                    row['state'] != 'running' or row['owner_pid'] != os.getpid()):
                raise AIJobError('job_not_running')
            if cursor.get('bulk_pause_requested') and not reconcile_cancelled:
                raise AIJobError('bulk_pause_requested')
            if not json.loads(row['request_json']).get('bulk_auto_apply'):
                raise AIJobError('bulk_review_unavailable')
            previous = self._observed_bulk_apply(cursor)
            if previous and previous.get('automatic') and previous['state'] == 'interrupted':
                previous.update(state='running', reason='', owner_pid=os.getpid())
                cursor['bulk_apply'] = previous
                self._save_bulk_cursor(connection, job_id, cursor)
                return previous
            if reconcile_cancelled:
                return None
            self._guard_bulk_apply(cursor)
            count = cursor.get('bulk_automatic_pending', 0)
            if not count:
                return None
            first, last = cursor['bulk_automatic_range']
            return self._new_bulk_apply(connection, job_id, cursor,
                {'request_key': uuid.uuid4().hex, 'scope': 'verified_pending', 'revision': row['revision'],
                 'total': count}, last, automatic=True, start=first - 1)

    def claim_bulk_apply(self, job_id, scope, revision, count, request_key, *, validate=lambda: None):
        if (not isinstance(scope, str) or scope not in _APPLY_VIEWS or
                type(revision) is not int or type(count) is not int or count < 1
                or not isinstance(request_key, str) or not 1 <= len(request_key) <= 160):
            raise AIJobError('invalid_bulk_apply', 400)
        confirmation = {'request_key': request_key, 'scope': scope, 'revision': revision, 'total': count}
        with self._connection(write=True) as connection:
            row = self._job(connection, job_id)
            cursor = json.loads(row['cursor_json'])
            previous = self._observed_bulk_apply(cursor)
            if not previous or previous['request_key'] != request_key:
                archived = connection.execute("""SELECT payload FROM events WHERE job_id=? AND kind='bulk_apply'
                    AND json_extract(payload,'$.request_key')=? LIMIT 1""", (job_id, request_key)).fetchone()
                existing = json.loads(archived[0]) if archived else None
            else:
                existing = previous
            if existing:
                if any(existing[key] != value for key, value in confirmation.items()):
                    raise AIJobError('request_key_conflict')
                return existing, False
            self._guard_bulk_review(row, cursor)
            if scope == 'verified_pending' and json.loads(row['request_json']).get('bulk_auto_apply'):
                raise AIJobError('bulk_apply_is_automatic')
            validate()
            predicate = _BULK_REVIEW[_APPLY_VIEWS[scope]]
            actual, cutoff = connection.execute(f"""SELECT count(*),max(position) FROM result_items
                WHERE job_id=? AND domain='iptv' AND ({predicate})""", (job_id,)).fetchone()
            if revision != row['revision'] or count != actual:
                error = AIJobError('stale_bulk_apply')
                error.details = {'actual_count': actual, 'revision': row['revision'],
                                 'message': f'This job changed. Review the current count of {actual:,} and confirm again.'}
                raise error
            return self._new_bulk_apply(connection, job_id, cursor, confirmation, cutoff), True

    def control_bulk_apply(self, job_id, apply_id, action, revision, request_key):
        if type(revision) is not int or not isinstance(request_key, str) or not 1 <= len(request_key) <= 160:
            raise AIJobError('invalid_bulk_apply', 400)
        confirmation = {'id': apply_id, 'action': action, 'revision': revision, 'request_key': request_key}
        with self._connection(write=True) as connection:
            row = self._job(connection, job_id)
            cursor = json.loads(row['cursor_json'])
            existing = connection.execute("""SELECT payload FROM events WHERE job_id=? AND kind='bulk_apply_control'
                AND json_extract(payload,'$.request_key')=? LIMIT 1""", (job_id, request_key)).fetchone()
            if existing:
                saved = json.loads(existing[0])
                if any(saved[key] != value for key, value in confirmation.items()):
                    raise AIJobError('request_key_conflict')
                return saved['apply'], False
            apply = self._observed_bulk_apply(cursor)
            if not apply or apply['id'] != apply_id or row['revision'] != revision:
                raise AIJobError('stale_bulk_apply')
            if apply.get('automatic'):
                raise AIJobError('bulk_apply_is_automatic')
            state = apply['state']
            if action == 'resume' and state == 'interrupted':
                apply.update(state='stopping' if apply.get('stop_requested') else 'running', reason='')
            elif action == 'stop' and state in ('running', 'interrupted'):
                apply.update(state='stopping', stop_requested=True, reason='')
            else:
                raise AIJobError('invalid_bulk_apply_transition')
            apply['owner_pid'] = os.getpid()
            cursor['bulk_apply'] = apply
            self._save_bulk_cursor(connection, job_id, cursor)
            connection.execute('INSERT INTO events(job_id,kind,payload,created) VALUES (?,?,?,?)',
                               (job_id, 'bulk_apply_control', _json({**confirmation, 'apply': apply}), self.clock()))
            return apply, state == 'interrupted'

    @contextmanager
    def bulk_apply_stop_reader(self, job_id, apply_id):
        # Each autocommit SELECT observes a concurrent Stop without reopening SQLite per source.
        with self._connection() as connection:
            def stopping():
                row = connection.execute("""SELECT json_extract(cursor_json,'$.bulk_apply.state') FROM jobs
                    WHERE id=? AND json_extract(cursor_json,'$.bulk_apply.id')=?""", (job_id, apply_id)).fetchone()
                return not row or row[0] != 'running'
            yield stopping

    def bulk_apply_chunk(self, job_id, apply):
        predicate = _BULK_REVIEW[_APPLY_VIEWS[apply['scope']]]
        with self._connection() as connection:
            return [dict(json.loads(row['payload']), result_position=row['position']) for row in connection.execute(
                f"""SELECT position,payload FROM result_items WHERE job_id=? AND domain='iptv' AND position>? AND position<=?
                    AND ({predicate}) AND coalesce(json_extract(payload,'$.apply_id'),'')<>?
                    ORDER BY position LIMIT 100""", (job_id, apply['position'], apply['cutoff'], apply['id']))]

    def checkpoint_bulk_apply(self, job_id, apply_id, rows=(), *, state=None, reason='', advance=True):
        with self._connection(write=True) as connection:
            row = self._job(connection, job_id)
            cursor = json.loads(row['cursor_json'])
            apply = cursor['bulk_apply']
            if apply['id'] != apply_id or apply['state'] not in ('running', 'stopping'):
                raise AIJobError('stale_bulk_apply')
            self._record_bulk_apply_outcomes(connection, job_id, cursor, apply, rows, advance=advance)
            if state:
                if state == 'completed' and apply.get('stop_requested'):
                    state = 'stopped'
                apply.update(state=state, reason=reason)
            self._save_bulk_cursor(connection, job_id, cursor)
            return apply

    @staticmethod
    def _record_bulk_apply_outcomes(connection, job_id, cursor, apply, rows, *, advance):
        for proposal, outcome, message, retryable in rows:
            connection.execute("""UPDATE result_items SET payload=json_set(payload,'$.apply_state',?,
                '$.apply_reason',?,'$.apply_retryable',json(?),'$.apply_id',?)
                WHERE job_id=? AND domain='iptv' AND identity=?""",
                (outcome, message, _json(retryable), apply['id'], job_id, proposal['source_key']))
            apply['counts'][outcome] += 1
            if apply.get('automatic'):
                cursor['bulk_automatic_pending'] = max(0, cursor.get('bulk_automatic_pending', 0) - 1)
                if not cursor['bulk_automatic_pending']:
                    cursor.pop('bulk_automatic_range', None)
                counts = cursor.setdefault('bulk_automatic_counts', dict.fromkeys(apply['counts'], 0))
                counts[outcome] += 1
            elif apply['scope'] == 'retry_failed' and proposal.get('bulk_automatic') and outcome != 'failed':
                counts = cursor['bulk_automatic_counts']
                counts['failed'] -= 1
                counts[outcome] += 1
            if advance:
                apply['position'] = proposal['result_position']

    @contextmanager
    def explicit_bulk_apply(self, job_id):
        with self._connection(write=True) as connection:
            row = self._job(connection, job_id)
            cursor = json.loads(row['cursor_json'])
            self._guard_bulk_review(row, cursor)
            cursor['bulk_explicit_owner'] = os.getpid()
            self._save_bulk_cursor(connection, job_id, cursor)
        try:
            yield
        finally:
            with self._connection(write=True) as connection:
                cursor = json.loads(self._job(connection, job_id)['cursor_json'])
                cursor.pop('bulk_explicit_owner', None)
                self._save_bulk_cursor(connection, job_id, cursor)

    def bulk_proposals(self, job_id, source_keys):
        if (not isinstance(source_keys, list) or not 1 <= len(source_keys) <= 100 or
                any(not isinstance(key, str) or len(key) > 160 for key in source_keys)):
            raise AIJobError('invalid_bulk_proposals', 400)
        keys = list(dict.fromkeys(source_keys))
        with self._connection() as connection:
            rows = connection.execute(f"""SELECT payload FROM result_items WHERE job_id=?
                AND domain='iptv' AND identity IN ({','.join('?' for _ in keys)})""", (job_id, *keys)).fetchall()
        if len(rows) != len(keys):
            raise AIJobError('invalid_bulk_proposals', 400)
        return [json.loads(row['payload']) for row in rows]

    def bulk_work_sources(self, job):
        keys = job['request']['selection_snapshot']['source_keys']
        cutoff = job['cursor'].get('bulk_work', {}).get('source_cutoff')
        if cutoff is None:
            return keys
        with self._connection() as connection:
            settled = {row[0] for row in connection.execute("""SELECT identity FROM result_items
                WHERE job_id=? AND domain='iptv' AND position<?""", (job['id'], cutoff))}
        return [key for key in keys if key not in settled]

    def mark_bulk_applied(self, job_id, source_keys):
        if not source_keys:
            return
        with self._connection(write=True) as connection:
            connection.executemany("""UPDATE result_items SET payload=json_set(payload,'$.apply_state','applied')
                WHERE job_id=? AND domain='iptv' AND identity=?""", ((job_id, key) for key in source_keys))
            connection.execute('UPDATE jobs SET revision=revision+1 WHERE id=?', (job_id,))

    def start_run(self, job_id, revision):
        with self._connection(write=True) as connection:
            row = self._job(connection, job_id)
            if row['revision'] != revision or row['state'] != 'queued':
                raise AIJobError('stale_job_revision')
            connection.execute("UPDATE jobs SET state='running',owner_pid=?,revision=revision+1,updated=? WHERE id=?",
                               (os.getpid(), self.clock(), job_id))
        with self._progress_lock:
            self._progress[job_id] = {'phase': 'preparing', 'account_id': row['account_id']}
        return self.snapshot(job_id)

    def prepare_action(self, job_id, kind, payload, *, request_key, depends_on=(), lifetime=900):
        """Persist a domain owner's prepared reference, never permission to execute it."""
        if not isinstance(request_key, str) or not 1 <= len(request_key) <= 160:
            raise AIJobError('invalid_request_key', 400)
        if not isinstance(kind, str) or not kind or not isinstance(payload, dict):
            raise AIJobError('invalid_action', 400)
        dependencies = list(dict.fromkeys(depends_on))
        digest = hashlib.sha256(_json([kind, payload, dependencies]).encode()).hexdigest()
        with self._connection(write=True) as connection:
            job = self._job(connection, job_id)
            self._session(connection, job['session_id'], job['account_id'])
            if job['state'] != 'running':
                raise AIJobError('job_not_running')
            existing = connection.execute('SELECT * FROM action_receipts WHERE scope_id=? AND request_key=?',
                                          (job_id, request_key)).fetchone()
            if existing:
                if existing['digest'] != digest:
                    raise AIJobError('request_key_conflict')
                return json.loads(existing['owner_reference'])
            self._require_settled_actions(connection, job['session_id'])
            for identity in dependencies:
                dependency = self._action(connection, identity)
                if dependency['session_id'] != job['session_id'] or dependency['account_id'] != job['account_id']:
                    raise AIJobError('foreign_action_dependency')
            now = self.clock()
            action = {'action_id': uuid.uuid4().hex, 'job_id': job_id, 'session_id': job['session_id'],
                'account_id': job['account_id'], 'selection': json.loads(job['selection_json']),
                'kind': kind, 'payload': payload, 'depends_on': dependencies, 'state': 'prepared',
                'revision': 0, 'expires': now + lifetime, 'outcome': None}
            connection.execute('INSERT INTO action_receipts VALUES (?,?,?,?,?,?)',
                (job_id, request_key, digest, 'prepared', _json(action), now))
        return action

    def _action(self, connection, action_id):
        row = connection.execute("SELECT owner_reference FROM action_receipts WHERE json_extract(owner_reference,'$.action_id')=?",
                                 (action_id,)).fetchone()
        if not row:
            raise AIJobError('action_not_found', 404)
        return json.loads(row['owner_reference'])

    def save_result_set(self, job_id, result_set):
        from services.ai_catalog import ResultSet
        from dataclasses import fields
        if not isinstance(result_set, ResultSet):
            raise AIJobError('invalid_result_set', 400)
        payload = {field.name: getattr(result_set, field.name) for field in fields(ResultSet)}
        payload['movies'] = [dict(movie) for movie in result_set.movies]
        encoded = _json(payload)
        with self._connection(write=True) as connection:
            job = self._job(connection, job_id)
            if job['state'] != 'running':
                raise AIJobError('job_not_running')
            existing = connection.execute("""SELECT e.payload FROM events e JOIN jobs j ON j.id=e.job_id
                WHERE j.session_id=? AND e.kind='result_set' AND json_extract(e.payload,'$.id')=?""",
                (job['session_id'], result_set.id)).fetchone()
            if existing:
                if existing['payload'] != encoded:
                    raise AIJobError('immutable_result_set')
                return
            connection.execute('INSERT INTO events(job_id,kind,payload,created) VALUES (?,?,?,?)',
                               (job_id, 'result_set', encoded, self.clock()))

    def result_sets(self, session_id, account_id):
        from services.ai_catalog import ResultSet
        from types import MappingProxyType
        with self._connection() as connection:
            self._session(connection, session_id, account_id)
            rows = connection.execute("""SELECT e.payload FROM events e JOIN jobs j ON j.id=e.job_id
                WHERE j.session_id=? AND e.kind='result_set' ORDER BY e.sequence""", (session_id,)).fetchall()
            result = {}
            for row in rows:
                value = json.loads(row['payload'])
                value['movies'] = tuple(MappingProxyType(movie) for movie in value['movies'])
                value['local_files'] = tuple(value['local_files'])
                value['library_roots'] = tuple(value['library_roots'])
                result[value['id']] = ResultSet(**value)
            return result

    def save_checkpoint(self, job_id, key, payload):
        with self._connection(write=True) as connection:
            row = self._job(connection, job_id)
            if row['state'] != 'running':
                raise AIJobError('job_not_running')
            cursor = json.loads(row['cursor_json'])
            cursor[key] = payload
            connection.execute('UPDATE jobs SET cursor_json=?,revision=revision+1,updated=? WHERE id=?',
                               (_json(cursor), self.clock(), job_id))

    def action(self, action_id, account_id):
        with self._connection() as connection:
            action = self._action(connection, action_id)
            if action['account_id'] != account_id:
                raise AIJobError('action_account_mismatch')
            self._session(connection, action['session_id'], account_id)
            return action

    @staticmethod
    def _require_settled_actions(connection, session_id):
        if connection.execute("""SELECT 1 FROM action_receipts
            WHERE json_extract(owner_reference,'$.session_id')=? AND state IN ('uncertain','executing') LIMIT 1""",
            (session_id,)).fetchone():
            raise AIJobError('action_outcome_requires_review')

    def _save_action(self, connection, action):
        connection.execute("UPDATE action_receipts SET state=?,owner_reference=?,updated=? WHERE scope_id=? AND json_extract(owner_reference,'$.action_id')=?",
            (action['state'], _json(action), self.clock(), action['job_id'], action['action_id']))

    def claim_action(self, action_id, revision, *, confirmation=None):
        with self._connection(write=True) as connection:
            action = self._action(connection, action_id)
            self._session(connection, action['session_id'], action['account_id'])
            if 'confirmation' in action and action['confirmation'] != confirmation:
                raise AIJobError('request_key_conflict')
            # A repeated browser submission returns the authoritative receipt, never another write.
            if action['state'] == 'completed':
                return dict(action, already_completed=True)
            if action['state'] != 'prepared':
                raise AIJobError('action_outcome_requires_review')
            self._require_settled_actions(connection, action['session_id'])
            job = self._job(connection, action['job_id'])
            if job['state'] in ('cancelled', 'interrupted'):
                raise AIJobError('action_cancelled')
            if action['revision'] != revision or action['expires'] <= self.clock():
                raise AIJobError('stale_action_revision')
            receipts = [self._action(connection, identity) for identity in action['depends_on']]
            if any(row['state'] != 'completed' for row in receipts):
                raise AIJobError('action_dependency_not_completed')
            action.update(state='executing', revision=action['revision'] + 1,
                          confirmation=confirmation,
                          dependency_receipts=[{'action_id': row['action_id'], 'outcome': row['outcome']} for row in receipts])
            self._save_action(connection, action)
        return action

    def complete_action(self, action_id, revision, outcome, *, state):
        if state not in ('completed', 'failed', 'uncertain', 'partial') or not isinstance(outcome, dict):
            raise AIJobError('invalid_action_outcome', 400)
        with self._connection(write=True) as connection:
            action = self._action(connection, action_id)
            if action['state'] != 'executing' or action['revision'] != revision:
                raise AIJobError('stale_action_revision')
            action.update(state=state, outcome=outcome, revision=revision + 1)
            self._save_action(connection, action)
        return action

    def refresh_action(self, action_id, revision, payload):
        with self._connection(write=True) as connection:
            action = self._action(connection, action_id)
            if action['state'] != 'prepared' or action['revision'] != revision or action['expires'] <= self.clock():
                raise AIJobError('stale_action_revision')
            action.update(payload=payload, revision=revision + 1)
            self._save_action(connection, action)
        return action

    def cancel_action(self, action_id, revision):
        with self._connection(write=True) as connection:
            action = self._action(connection, action_id)
            if action['state'] == 'cancelled':
                return action
            if action['state'] != 'prepared' or action['revision'] != revision:
                raise AIJobError('stale_action_revision')
            action.update(state='cancelled', revision=revision + 1, outcome={'message': 'Action cancelled before execution.'})
            self._save_action(connection, action)
        self.finalize_actions(action['job_id'])
        return action

    def finalize_actions(self, job_id):
        with self._connection(write=True) as connection:
            origin = self._job(connection, job_id)
            for job in connection.execute('SELECT * FROM jobs WHERE session_id=?', (origin['session_id'],)).fetchall():
                if job['state'] in ('running', 'queued', 'cancelled', 'interrupted'):
                    continue
                actions = {row['action_id']: row for row in (json.loads(row['owner_reference']) for row in connection.execute(
                    'SELECT owner_reference FROM action_receipts WHERE scope_id=?', (job['id'],)))}
                for reference in json.loads(job['cursor_json']).get('agent', {}).get('prepared', []):
                    action = self._action(connection, reference['action_id'])
                    if action['session_id'] == origin['session_id'] and action['account_id'] == origin['account_id']:
                        actions[action['action_id']] = action
                actions = list(actions.values())
                if not actions or any(row['state'] in ('prepared', 'executing') for row in actions):
                    continue
                complete = all(row['state'] == 'completed' for row in actions) and job['coverage'] != 'partial'
                state = 'completed' if complete else 'cancelled' if all(row['state'] == 'cancelled' for row in actions) else 'partial'
                output = json.loads(job['output_json']) if job['output_json'] else {}
                output['action_receipts'] = [{'action_id': row['action_id'], 'state': row['state']} for row in actions]
                connection.execute('UPDATE jobs SET state=?,output_json=?,revision=revision+1,updated=? WHERE id=?',
                    (state, _json(output), self.clock(), job['id']))

    def reserve_inference(self, job_id, *, recovery_batch=None):
        paused = False
        with self._connection(write=True) as connection:
            row = self._job(connection, job_id)
            if row['state'] != 'running' or row['owner_pid'] != os.getpid():
                raise AIJobError('job_not_running')
            budgets = [row]
            request = json.loads(row['request_json'])
            cursor = json.loads(row['cursor_json'])
            bulk = 'bulk_call_budget' in request
            if bulk and cursor.get('bulk_pause_requested'):
                raise AIJobError('bulk_pause_requested')
            parent_id = request.get('parent_job_id')
            if parent_id:
                parent = self._job(connection, parent_id)
                if parent['state'] != 'running':
                    raise AIJobError('job_not_running')
                budgets.append(parent)
            limit = _inference_budget(request, cursor)
            if any(budget['run_calls'] >= limit for budget in budgets):
                paused = True
                message = ('ChatGPT call budget reached. Add calls to resume.' if bulk else
                           'Inference budget reached; Continue starts the next run.')
                for budget in budgets:
                    connection.execute("UPDATE jobs SET state='paused_budget',revision=revision+1,message=?,updated=? WHERE id=?",
                                       (message, self.clock(), budget['id']))
                    self._clear_progress(budget['id'])
            else:
                if recovery_batch is not None:
                    work = cursor.get('bulk_work', {})
                    recovery = work.get('recovery', {})
                    indices = [entry['index'] for entry in recovery_batch]
                    if (not request.get('bulk_recovery_protocol_hash') or recovery.get('in_flight') or
                            not indices or len(indices) != len(set(indices)) or
                            recovery.get('pending', [])[:len(indices)] != indices):
                        raise AIJobError('invalid_recovery_admission')
                    del recovery['pending'][:len(indices)]
                    recovery['in_flight'] = recovery_batch
                    recovery['requests'] += 1
                    recovery['admitted'] += len(indices)
                    work['phase'] = 'recovery_comparing'
                    self._save_bulk_cursor(connection, job_id, cursor)
                for budget in budgets:
                    connection.execute('UPDATE jobs SET run_calls=run_calls+1,revision=revision+1,updated=? WHERE id=?',
                                       (self.clock(), budget['id']))
        if paused:
            raise AIJobError('paused_budget')

    def add_results(self, job_id, results, *, cursor=None, limit_to_target=False, bulk_work=None,
                    replace_bulk_results=False, settle_cancelled=False, recheck_work=None):
        with self._connection(write=True) as connection:
            row = self._job(connection, job_id)
            if row['state'] != 'running' and not (settle_cancelled and row['state'] == 'cancelled' and
                    all(result['card']['outcome'] != 'verified' for result in results)):
                raise AIJobError('job_not_running')
            checkpoint = json.loads(row['cursor_json'])
            if bulk_work is not None:
                counts = checkpoint.setdefault('bulk_counts', dict.fromkeys(BULK_OUTCOMES, 0))
                checkpoint['bulk_work'] = bulk_work
                if recheck_work is not None:
                    checkpoint['bulk_search_recheck'] = recheck_work
                checkpoint['checkpoint_at'] = self.clock()
                position = accepted = sum(counts.values())
                request = json.loads(row['request_json'])
            else:
                request = json.loads(row['request_json'])
                accepted = connection.execute('SELECT count(*) FROM result_items WHERE job_id=?', (job_id,)).fetchone()[0]
                position = connection.execute('SELECT COALESCE(MAX(position),-1)+1 FROM result_items WHERE job_id=?', (job_id,)).fetchone()[0]
            for result in results:
                if limit_to_target and row['target'] is not None and (len(str(accepted)), str(accepted)) >= (len(row['target']), row['target']):
                    break
                domain, identity, card = result['domain'], result['identity'], result['card']
                if not isinstance(identity, str) or not identity or not isinstance(domain, str) or not domain or not isinstance(card, dict):
                    raise AIJobError('invalid_result_identity', 400)
                if row['feature'] == 'F1' and not request.get('include_previous', False):
                    prior = connection.execute('''SELECT 1 FROM result_items r JOIN jobs j ON j.id=r.job_id
                        WHERE j.session_id=? AND r.domain=? AND r.identity=? LIMIT 1''', (row['session_id'], domain, identity)).fetchone()
                    if prior:
                        continue
                if replace_bulk_results or recheck_work is not None:
                    previous = connection.execute('SELECT payload,position FROM result_items WHERE job_id=? AND domain=? AND identity=?',
                                                  (job_id, domain, identity)).fetchone()
                    if not previous:
                        raise AIJobError('missing_first_pass_result')
                    previous_position, previous = previous['position'], json.loads(previous['payload'])
                    allowed_apply_states = (None, '', 'stale') if recheck_work is not None else (None, '')
                    if previous.get('apply_state') not in allowed_apply_states or previous.get('evidence', {}).get('recovery'):
                        raise AIJobError('recovery_already_settled')
                    connection.execute('UPDATE result_items SET payload=? WHERE job_id=? AND domain=? AND identity=?',
                                       (_json(card), job_id, domain, identity))
                    counts[previous['outcome']] -= 1
                    counts[card['outcome']] += 1
                    self._track_bulk_automatic(checkpoint, card, previous_position)
                    continue
                inserted = connection.execute('INSERT OR IGNORE INTO result_items VALUES (?,?,?,?,?)',
                                               (job_id, domain, identity, position, _json(card)))
                if inserted.rowcount:
                    position += 1
                    accepted += 1
                    if bulk_work is not None:
                        counts[card['outcome']] += 1
                        self._track_bulk_automatic(checkpoint, card, position - 1)
            connection.execute('UPDATE jobs SET revision=revision+1,cursor_json=?,updated=? WHERE id=?',
                (_json(cursor if cursor is not None else checkpoint), self.clock(), job_id))
        if bulk_work is not None:
            return None
        return self.snapshot(job_id)

    @staticmethod
    def _track_bulk_automatic(checkpoint, card, position):
        if card.get('bulk_automatic') and card['outcome'] == 'verified':
            checkpoint['bulk_automatic_pending'] = checkpoint.get('bulk_automatic_pending', 0) + 1
            first, last = checkpoint.get('bulk_automatic_range', (position, position))
            checkpoint['bulk_automatic_range'] = [min(first, position), max(last, position)]

    def bulk_control(self, job_id):
        with self._connection() as connection:
            row = connection.execute("""SELECT state, json_extract(cursor_json,'$.bulk_pause_requested')
                FROM jobs WHERE id=?""", (job_id,)).fetchone()
        return row['state'], bool(row[1])

    def inference_evidence_scopes(self, job_id):
        with self._connection() as connection:
            row = self._job(connection, job_id)
            if 'bulk_call_budget' in json.loads(row['request_json']):
                return ['iptv_titles']
            session = self._session(connection, row['session_id'], row['account_id'])
            return json.loads(session['constraints_json']).get('evidence_scopes', [])

    def request_bulk_pause(self, job_id, run_number):
        with self._connection(write=True) as connection:
            row = self._job(connection, job_id)
            cursor = json.loads(row['cursor_json'])
            if ('bulk_call_budget' not in json.loads(row['request_json']) or type(run_number) is not int
                    or run_number != cursor.get('run_number', 0) or row['state'] not in ('queued', 'running')):
                raise AIJobError('stale_or_unpausable_job')
            state = row['state']
            message = 'Pausing at the next checkpoint.'
            if state == 'queued':
                state, message = 'paused', 'Paused by request.'
            else:
                cursor['bulk_pause_requested'] = True
            connection.execute('UPDATE jobs SET state=?,cursor_json=?,message=?,revision=revision+1,updated=? WHERE id=?',
                               (state, _json(cursor), message, self.clock(), job_id))
        return self.snapshot(job_id)

    def is_cancelled(self, job_id):
        with self._connection() as connection:
            row = self._job(connection, job_id)
            parent = json.loads(row['request_json']).get('parent_job_id')
            return row['state'] not in ('running', 'queued') or (parent is not None and
                self._job(connection, parent)['state'] not in ('running', 'queued'))

    def origin_jobs(self, job_id):
        with self._connection() as connection:
            identities = [row['id'] for row in connection.execute(
                "SELECT id FROM jobs WHERE json_extract(request_json,'$.origin_control_job_id')=?", (job_id,))]
        return [self.snapshot(identity) for identity in identities]

    def record_job_turn(self, job_id):
        with self._connection(write=True) as connection:
            row = self._job(connection, job_id)
            cursor = json.loads(row['cursor_json'])
            if not cursor.get('turn_recorded'):
                session = self._session(connection, row['session_id'], row['account_id'])
                turns = json.loads(session['turns'])
                turns.append({'role': 'user', 'content': json.loads(row['request_json'])['prompt']})
                durable = json.loads(session['constraints_json'])
                durable.setdefault('initial_request', turns[0]['content'])
                connection.execute('UPDATE sessions SET turns=?,constraints_json=?,updated=? WHERE id=?',
                    (_json(turns[-20:]), _json(durable), self.clock(), session['id']))
                cursor['turn_recorded'] = True
                connection.execute('UPDATE jobs SET cursor_json=?,revision=revision+1 WHERE id=?', (_json(cursor), job_id))

    def fix_scope(self, job_id, scope, *, target=None):
        with self._connection(write=True) as connection:
            row = self._job(connection, job_id)
            if row['state'] != 'running':
                raise AIJobError('job_not_running')
            cursor = json.loads(row['cursor_json'])
            target = canonical_count(target) if target is not None else row['target']
            if cursor.get('scope_fixed') and (cursor.get('scope') != scope or target != row['target']):
                raise AIJobError('scope_changed_during_operation')
            if cursor.get('scope_fixed'):
                return self.snapshot(job_id)
            cursor.update(scope_fixed=True, scope=scope)
            connection.execute('UPDATE jobs SET target=?,cursor_json=?,revision=revision+1,updated=? WHERE id=?',
                               (target, _json(cursor), self.clock(), job_id))
        return self.snapshot(job_id)

    def update_constraints(self, session_id, account_id, updates):
        with self._connection(write=True) as connection:
            row = self._session(connection, session_id, account_id)
            durable = json.loads(row['constraints_json'])
            durable.update(updates)
            connection.execute('UPDATE sessions SET constraints_json=?,updated=? WHERE id=?',
                               (_json(durable), self.clock(), session_id))

    def _mark_evidence(self, connection, session_id, account_id, scope):
        if scope not in ('iptv_titles', 'movie_identity_hints'):
            raise AIJobError('unknown_evidence_scope', 400)
        row = self._session(connection, session_id, account_id)
        durable = json.loads(row['constraints_json'])
        durable['evidence_scopes'] = sorted(set(durable.get('evidence_scopes', [])) | {scope})
        connection.execute('UPDATE sessions SET constraints_json=?,updated=? WHERE id=?',
                           (_json(durable), self.clock(), session_id))

    def mark_evidence_scope(self, session_id, account_id, scope):
        with self._connection(write=True) as connection:
            self._mark_evidence(connection, session_id, account_id, scope)

    def result_seen(self, session_id, domain, identity):
        with self._connection() as connection:
            return connection.execute('''SELECT 1 FROM result_items r JOIN jobs j ON j.id=r.job_id
                WHERE j.session_id=? AND r.domain=? AND r.identity=? LIMIT 1''', (session_id, domain, identity)).fetchone() is not None

    def recent_results(self, job_id, limit=20):
        with self._connection() as connection:
            return [json.loads(row['payload']) for row in connection.execute(
                'SELECT payload FROM result_items WHERE job_id=? ORDER BY position DESC LIMIT ?', (job_id, limit)).fetchall()][::-1]

    def finish(self, job_id, state, *, coverage='unknown', message='', output=None):
        if state not in STATES or coverage not in COVERAGE:
            raise AIJobError('invalid_job_state', 400)
        with self._connection(write=True) as connection:
            row = self._job(connection, job_id)
            if row['state'] in ('cancelled', 'paused', 'paused_budget', 'interrupted'):
                return self.snapshot(job_id)
            cursor = json.loads(row['cursor_json'])
            if state == 'completed' and cursor.get('bulk_pause_requested'):
                state, coverage, message = 'paused', 'partial', 'Paused by request.'
            if state == 'completed' and cursor.get('bulk_automatic_pending'):
                state, coverage, message = 'interrupted', 'partial', 'Verified matches still need to be applied.'
            connection.execute('UPDATE jobs SET state=?,coverage=?,message=?,output_json=?,revision=revision+1,updated=? WHERE id=?',
                               (state, coverage, message, _json(output) if output is not None else None, self.clock(), job_id))
        self._clear_progress(job_id)
        return self.snapshot(job_id)

    def cancel(self, job_id, revision, *, run_number=None):
        with self._connection(write=True) as connection:
            row = self._job(connection, job_id)
            # Progress advances revisions while a request is in flight. Cancellation
            # may target that run, but must never cancel a later explicit Continue.
            same_run = (type(run_number) is int and run_number >= 0
                        and json.loads(row['cursor_json']).get('run_number', 0) == run_number)
            if (run_number is not None and not same_run) or (run_number is None and row['revision'] != revision):
                raise AIJobError('stale_job_revision')
            if row['state'] not in ('completed', 'cancelled'):
                message = '' if 'bulk_call_budget' in json.loads(row['request_json']) else row['message']
                connection.execute("UPDATE jobs SET state='cancelled',message=?,revision=revision+1,updated=? WHERE id=?",
                                   (message, self.clock(), job_id))
                self._cancel_prepared_actions(connection, job_id=job_id, message='Future work cancelled before execution.')
        self.finalize_actions(job_id)
        self._clear_progress(job_id)
        return self.snapshot(job_id)

    def continue_job(self, job_id, revision, request_key, *, extra_calls=None, refresh_catalog=None,
                     recheck_search_limits=False):
        if not isinstance(request_key, str) or not 1 <= len(request_key) <= 160:
            raise AIJobError('invalid_request_key', 400)
        with self._connection(write=True) as connection:
            row = self._job(connection, job_id)
            request = json.loads(row['request_json'])
            bulk = 'bulk_call_budget' in request
            if not bulk:
                if extra_calls is not None:
                    raise AIJobError('invalid_bulk_budget', 400)
                self._session(connection, row['session_id'], row['account_id'])
            if connection.execute("SELECT 1 FROM action_receipts WHERE scope_id=? AND state IN ('uncertain','executing') LIMIT 1", (job_id,)).fetchone():
                raise AIJobError('mutation_outcome_requires_review')
            if row['last_continue_key'] == request_key:
                return self.snapshot(job_id)
            interrupted = (row['state'] == 'running' or (bulk and row['state'] == 'queued')) and (
                row['owner_pid'] is not None and not self.process_alive(row['owner_pid']))
            resumable = ('paused', 'paused_budget', 'interrupted') if bulk else ('paused_budget', 'partial', 'failed', 'interrupted')
            refresh_catalog = refresh_catalog if supports_bulk_catalog_resume(request) else None
            cursor = json.loads(row['cursor_json'])
            start_recheck = recheck_search_limits and row['state'] == 'completed' and bool(refresh_catalog)
            stale_failure = bool(refresh_catalog and _stale_catalog_failure(row['state'], row['message']))
            if row['revision'] != revision or (row['state'] not in resumable and not interrupted and not stale_failure and not start_recheck):
                raise AIJobError('stale_or_unresumable_job')
            if recheck_search_limits and not start_recheck:
                raise AIJobError('stale_or_unresumable_job')
            calls = 0
            message = row['message']
            if bulk:
                if stale_failure or start_recheck:
                    selection = json.loads(row['selection_json'])
                    self._guard_bulk_slot(connection, row['account_id'], selection['domain_id'], except_id=job_id)
                apply = self._observed_bulk_apply(cursor)
                if not (request.get('bulk_auto_apply') and apply and apply.get('automatic') and
                        apply['state'] == 'interrupted'):
                    self._guard_bulk_apply(cursor)
                extra_calls = 0 if extra_calls is None else extra_calls
                limit = _inference_budget(request, cursor)
                if (type(extra_calls) is not int or not 0 <= extra_calls <= BULK_MAX_CALLS - limit
                        or (row['state'] == 'paused_budget' and not extra_calls)):
                    raise AIJobError('invalid_bulk_budget', 400)
                if 'titles_per_request' in request:
                    offered = bulk_extra_calls(request, cursor) if row['state'] == 'paused_budget' else 0
                    if extra_calls != offered:
                        raise AIJobError('stale_bulk_allowance')
                if refresh_catalog:
                    self._refresh_bulk_catalog(connection, job_id, request, cursor, apply,
                                               stale_failure, refresh_catalog)
                if start_recheck:
                    keys = [item[0] for item in connection.execute(f"""SELECT identity FROM result_items
                        WHERE job_id=? AND domain='iptv' AND {_SEARCH_RECHECK} ORDER BY position""",
                        (job_id, *_SEARCH_LIMIT_MESSAGES))]
                    if not keys:
                        raise AIJobError('no_search_recheck_candidates')
                    cursor['bulk_search_recheck'] = {'keys': keys, 'processed': 0, 'verified': 0}
                cursor['bulk_budget'] = limit + extra_calls
                cursor.pop('bulk_pause_requested', None)
                calls, message = row['run_calls'], ''
            cursor['run_number'] = cursor.get('run_number', 0) + 1
            connection.execute("UPDATE jobs SET state='queued',run_calls=?,message=?,owner_pid=?,last_continue_key=?,cursor_json=?,revision=revision+1,updated=? WHERE id=?",
                               (calls, message, os.getpid() if bulk else None, request_key, _json(cursor), self.clock(), job_id))
            connection.execute('UPDATE sessions SET updated=? WHERE id=?', (self.clock(), row['session_id']))
        return self.snapshot(job_id)

    def _refresh_bulk_catalog(self, connection, job_id, request, cursor, apply, stale_failure, refresh_catalog):
        selection = request['selection_snapshot']
        bound_generation = bulk_catalog_generation({'request': request, 'cursor': cursor})
        finished = {row[0] for row in connection.execute(
            "SELECT identity FROM result_items WHERE job_id=? AND domain='iptv'", (job_id,))}
        remaining = [key for key in selection['source_keys'] if key not in finished]
        if stale_failure and not remaining and not cursor.get('bulk_automatic_pending') and not _unfinished_search_recheck(cursor):
            raise AIJobError('stale_or_unresumable_job')
        receipt_rows = {}
        if apply and apply['state'] in ('interrupted', 'stale'):
            predicate = _BULK_REVIEW[_APPLY_VIEWS[apply['scope']]]
            receipt_rows = {row[0]: bool(row[1]) for row in connection.execute(f"""SELECT identity,
                json_extract(payload,'$.bulk_automatic') FROM result_items
                WHERE job_id=? AND domain='iptv' AND position<=? AND ({predicate})
                AND coalesce(json_extract(payload,'$.apply_id'),'')<>?""",
                (job_id, apply['cutoff'], apply['id']))}
        generation, eligible, receipts = refresh_catalog(remaining, selection.get('filters', {}),
                                                         apply['id'] if receipt_rows else None, list(receipt_rows))
        if generation == bound_generation and not stale_failure:
            return
        if receipts:
            self._record_bulk_apply_outcomes(connection, job_id, cursor, apply,
                (({'source_key': key, 'bulk_automatic': receipt_rows[key]}, 'applied', '', False)
                 for key in receipts), advance=False)
        if apply and apply['state'] in ('interrupted', 'stale'):
            apply.update(state='stale', reason='The catalog changed. Any unapplied proposals need a fresh review.')
            cursor['bulk_apply'] = apply

        # A saved result belongs to its earlier catalogue. Only its receipt may cross the fence.
        connection.execute(f"""UPDATE result_items SET payload=json_set(payload,'$.apply_state','stale',
            '$.apply_reason','The provider catalog changed. Review this source again before applying.',
            '$.apply_retryable',json('false')) WHERE job_id=? AND domain='iptv'
            AND (({_BULK_REVIEW['pending_matches']}) OR ({_BULK_REVIEW['retry_failed']})
                 OR ({_BULK_REVIEW['classifications']}))""", (job_id,))
        connection.execute(f"""UPDATE result_items SET payload=json_set(payload,'$.catalog_stale',json('true'))
            WHERE job_id=? AND domain='iptv' AND {_APPLY_STATE}<>'applied'
              AND coalesce(json_extract(payload,'$.catalog_stale'),0)=0""", (job_id,))
        pending = cursor.pop('bulk_automatic_pending', 0)
        cursor.pop('bulk_automatic_range', None)
        if pending:
            counts = cursor.setdefault('bulk_automatic_counts', dict.fromkeys(('applied', 'locked', 'skipped', 'failed'), 0))
            counts['skipped'] += pending

        counts = cursor.setdefault('bulk_counts', dict.fromkeys(BULK_OUTCOMES, 0))
        skipped = [key for key in remaining if key not in eligible]
        reason = 'This source is no longer eligible in the refreshed selection.'
        connection.executemany('INSERT INTO result_items VALUES (?,?,?,?,?)',
            ((job_id, 'iptv', key, position, _json({'source_key': key, 'proposal_id': key, 'outcome': 'review',
                'category': 'unclassified', 'review_reason': reason, 'catalog_stale': True}))
             for position, key in enumerate(skipped, start=len(finished))))
        counts['review'] += len(skipped)
        cursor['bulk_catalog_generation'] = generation
        cursor['checkpoint_at'] = self.clock()
        work = cursor.get('bulk_work', {})
        cursor['bulk_work'] = {'offset': 0, 'pending': [], 'answers': {}, 'throttles': 0,
            'source_cutoff': len(finished) + len(skipped), 'source_count': len(remaining) - len(skipped),
            'previously_checked': len(finished), 'first_pass_resolved': work.get('first_pass_resolved', 0)}

    def session(self, session_id, account_id):
        with self._connection() as connection:
            row = self._session(connection, session_id, account_id)
            return {'id': row['id'], 'turns': json.loads(row['turns']), 'constraints': json.loads(row['constraints_json'])}

    def append_turn(self, session_id, account_id, turn, *, constraints=None):
        if not isinstance(turn, dict) or turn.get('role') not in ('user', 'assistant') or not isinstance(turn.get('content'), str):
            raise AIJobError('invalid_turn', 400)
        with self._connection(write=True) as connection:
            row = self._session(connection, session_id, account_id)
            durable = json.loads(row['constraints_json'])
            if constraints:
                durable.update(constraints)
            turns = (json.loads(row['turns']) + [turn])[-20:]
            connection.execute('UPDATE sessions SET turns=?,constraints_json=?,updated=? WHERE id=?',
                               (_json(turns), _json(durable), self.clock(), session_id))

    def acquire_inference_slot(self, job_id, cancel=None):
        if cancel is not None and cancel.is_set():
            raise AIJobError('cancelled')
        with self._connection(write=True) as connection:
            now = self.clock()
            for row in connection.execute('SELECT id,owner_pid FROM inference_leases WHERE expires<?', (now,)).fetchall():
                if not self.process_alive(row['owner_pid']):
                    connection.execute('DELETE FROM inference_leases WHERE id=?', (row['id'],))
            if connection.execute('SELECT count(*) FROM inference_leases').fetchone()[0] >= 2:
                return None
            lease_id = uuid.uuid4().hex
            connection.execute('INSERT INTO inference_leases VALUES (?,?,?,?,?)',
                               (lease_id, job_id, os.getpid(), self.owner_id, now + 240))
            return lease_id

    def release_inference_slot(self, lease_id):
        with self._connection(write=True) as connection:
            connection.execute('DELETE FROM inference_leases WHERE id=? AND owner_id=?', (lease_id, self.owner_id))

    @contextmanager
    def inference_slot(self, job_id, cancel):
        deadline = time.monotonic() + 180
        lease = None
        while lease is None:
            lease = self.acquire_inference_slot(job_id, cancel)
            if lease is None:
                if time.monotonic() >= deadline:
                    raise AIJobError('inference_busy')
                if cancel.wait(0.1):
                    raise AIJobError('cancelled')
        try:
            yield
        finally:
            self.release_inference_slot(lease)

    def disconnect(self, account_id):
        if not self.path.is_file():
            return
        with self._connection(write=True) as connection:
            connection.execute("""UPDATE jobs SET state='cancelled',message='Account disconnected',revision=revision+1,updated=?
                WHERE account_id=? AND state IN ('queued','running','paused','paused_budget','awaiting_clarification','awaiting_confirmation')""", (self.clock(), account_id))
            self._cancel_prepared_actions(connection, account_id=account_id, message='Account disconnected.')
        with self._progress_lock:
            for identity, entry in list(self._progress.items()):
                if entry['account_id'] == account_id:
                    self._progress.pop(identity, None)

    def _cancel_prepared_actions(self, connection, *, message, job_id=None, account_id=None):
        query, parameters = "SELECT owner_reference FROM action_receipts WHERE state='prepared'", []
        if job_id is not None:
            query += ' AND scope_id=?'
            parameters.append(job_id)
        if account_id is not None:
            query += " AND json_extract(owner_reference,'$.account_id')=?"
            parameters.append(account_id)
        for row in connection.execute(query, parameters).fetchall():
            action = json.loads(row['owner_reference'])
            action.update(state='cancelled', revision=action['revision'] + 1, outcome={'message': message})
            self._save_action(connection, action)


class AIJobService:
    """Dispatch only. Persistent claims, budgets and domain behavior have their owners."""
    def __init__(self, store, handlers=None, *, cancel_handlers=None, reconcile_bulk_cancel=None):
        self.store, self.handlers = store, dict(handlers or {})
        self.cancel_handlers = dict(cancel_handlers or {})
        self.reconcile_bulk_cancel = reconcile_bulk_cancel
        self._lock = threading.RLock()
        self._active = {}
        self._executor = None
        self._bulk_executor = None
        self._apply_executor = None
        self._apply_serialization = threading.Lock()
        self._apply_shutdown = threading.Event()
        self._closing = False

    def start_bulk_apply(self, job_id, apply_id, handler):
        from concurrent.futures import ThreadPoolExecutor
        with self._lock:
            if self._closing:
                self.store.checkpoint_bulk_apply(job_id, apply_id, state='interrupted', reason='CP is shutting down.')
                return
            if self._apply_executor is None:
                self._apply_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='cp-iptv-apply')
            def execute():
                try:
                    return self.serialize_bulk_apply(lambda: handler(self._apply_shutdown.is_set))
                except Exception:
                    return self.store.checkpoint_bulk_apply(job_id, apply_id, state='interrupted',
                        reason='Apply stopped unexpectedly. Resume to reconcile saved catalogue writes.')
            future = self._apply_executor.submit(execute)
            future.add_done_callback(lambda result: self._apply_done(job_id, apply_id, result))
            return future

    def serialize_bulk_apply(self, operation):
        with self._apply_serialization:
            return operation()

    def _apply_done(self, job_id, apply_id, future):
        if future.cancelled() or future.exception() is not None:
            self.store.checkpoint_bulk_apply(job_id, apply_id, state='interrupted',
                reason='Apply stopped unexpectedly. Resume Apply to reconcile saved catalog writes.')

    def start(self, job_id):
        with self._lock:
            job = self.store.snapshot(job_id)
            if self._closing or job['state'] != 'queued' or job_id in self._active:
                return job
            handler = self.handlers.get(job['feature'])
            if handler is None:
                raise AIJobError('feature_not_implemented')
            from concurrent.futures import ThreadPoolExecutor
            if 'bulk_call_budget' in job['request']:
                if self._bulk_executor is None:
                    self._bulk_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='cp-iptv-bulk')
                executor = self._bulk_executor
            else:
                if self._executor is None:
                    self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix='cp-gpt-job')
                executor = self._executor
            future = executor.submit(handler, job_id)
            self._active[job_id] = future
            run_number = job['cursor'].get('run_number', 0)
            future.add_done_callback(lambda completed: self._done(job_id, run_number, completed))
            return job

    def _done(self, job_id, run_number, future):
        with self._lock:
            self._active.pop(job_id, None)
            if not future.cancelled() and future.exception() is not None:
                self.store.finish(job_id, 'failed', message='ai_job_failed')
            operation = self.store.snapshot(job_id)
            if not future.cancelled() and operation['cursor'].get('run_number', 0) > run_number:
                # Resume can queue the next run while the previous worker is returning.
                self.start(job_id)
        self._reconcile_cancelled_bulk(operation)

    def _reconcile_cancelled_bulk(self, operation):
        if (self.reconcile_bulk_cancel and operation['state'] == 'cancelled' and
                operation['request'].get('bulk_auto_apply')):
            return self.serialize_bulk_apply(lambda: self.reconcile_bulk_cancel(self.store.snapshot(operation['id'])))
        return operation

    def cancel(self, job_id, revision, *, run_number=None):
        with self._lock:
            operation = self.store.cancel(job_id, revision, run_number=run_number)
            inactive = job_id not in self._active
        if inactive:
            operation = self._reconcile_cancelled_bulk(operation)
        handler = self.cancel_handlers.get(operation['feature'])
        if handler is not None and operation['state'] == 'cancelled':
            handler(operation)
        return operation

    def close(self):
        with self._lock:
            self._closing = True
            self._apply_shutdown.set()
            active = list(self._active)
        for job_id in active:
            operation = self.store.snapshot(job_id)
            if operation['state'] in ('queued', 'running'):
                self.store.finish(job_id, 'interrupted', message='CP stopped; Continue explicitly to resume.')
        for executor in (self._executor, self._bulk_executor, self._apply_executor):
            if executor:
                executor.shutdown(wait=True, cancel_futures=True)
