"""Opt-in, temp-only phase capture. No production store or SQLite policy changes."""
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
from urllib.parse import unquote


class SlotDiagnostics:
    _active = None
    _install_lock = threading.Lock()

    def __init__(self, root, trace, *, clock=time.perf_counter):
        self.root = Path(root).resolve()
        if Path(tempfile.gettempdir()).resolve() not in self.root.parents:
            raise ValueError('Slot diagnostics require a unique OS-temp root')
        self.database = (self.root/'user-data/ai/ai.sqlite').as_posix().casefold()
        self.trace, self.clock = trace, clock
        self.zero, self.samples, self.dropped = clock(), [], 0
        self._local, self._sample_lock = threading.local(), threading.Lock()
        self._started = self._closed = False

    def _record(self, phase, start, cpu, **fields):
        row = {'phase': phase, 'operation': getattr(self._local, 'operation', ''),
               'at_seconds': start-self.zero, 'seconds': self.clock()-start,
               'thread_cpu_seconds': time.thread_time()-cpu, 'thread': threading.get_ident(), **fields}
        with self._sample_lock:
            if len(self.samples) < 10000:
                self.samples.append(row)
            else:
                self.dropped += 1

    def _call(self, phase, function, /, *args, **kwargs):
        start, cpu = self.clock(), time.thread_time()
        try:
            return function(*args, **kwargs)
        finally:
            self._record(phase, start, cpu)

    @contextmanager
    def operation(self, name):
        previous = getattr(self._local, 'operation', '')
        self._local.operation = name
        try:
            start, cpu = self.clock(), time.thread_time()
            try:
                yield
            finally:
                self._record(name, start, cpu)
        finally:
            self._local.operation = previous

    def start(self):
        with self._install_lock:
            if self._started or SlotDiagnostics._active is not None:
                raise RuntimeError('Slot diagnostics already installed')
            if self._closed:
                raise RuntimeError('Slot diagnostics already closed')
            SlotDiagnostics._active = self
            self._connect, self._emit = sqlite3.connect, self.trace.emit
            owner = self
            methods = {}
            for name in ('execute', 'executescript', 'commit', 'rollback', 'close'):
                def method(connection, *args, _name=name, **kwargs):
                    phase = 'sqlite_'+_name
                    if _name == 'execute' and args:
                        word = str(args[0]).lstrip().split(None, 1)[0].upper() if str(args[0]).strip() else ''
                        phase += '_'+(word if word in {'BEGIN','COMMIT','ROLLBACK','SELECT','PRAGMA','DELETE','INSERT','UPDATE','CREATE'} else 'OTHER')
                    return owner._call(phase, getattr(sqlite3.Connection, _name), connection, *args, **kwargs)
                methods[name] = method
            observed = type('ObservedSlotConnection', (sqlite3.Connection,), methods)
            def connect(*args, **kwargs):
                raw = str(args[0] if args else kwargs.get('database', ''))
                target = unquote(raw.removeprefix('file:').split('?', 1)[0]).replace('\\', '/').casefold()
                if target != self.database:
                    return self._connect(*args, **kwargs)
                # Keep explicitly supplied factories and positional signatures intact.
                if 'factory' not in kwargs and len(args) < 6:
                    kwargs['factory'] = observed
                return self._call('sqlite_connect', self._connect, *args, **kwargs)
            def emit(event, **values):
                return self._call('trace_emit', self._emit, event, **values)
            sqlite3.connect, self.trace.emit = connect, emit
            self._started = True

    def summary(self):
        return {'operations': [dict(row) for row in self.samples if row['phase'].endswith('_actual')],
                'slowest_leaf_phases': sorted((dict(row) for row in self.samples if not row['phase'].endswith('_actual')),
                                             key=lambda row: row['seconds'], reverse=True)[:10],
                'sample_count': len(self.samples), 'dropped': self.dropped}

    def close(self):
        with self._install_lock:
            if self._closed:
                return
            if self._started:
                sqlite3.connect, self.trace.emit = self._connect, self._emit
                SlotDiagnostics._active = None
            self._closed = True
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root/'slot-diagnostics.json').write_text(json.dumps({**self.summary(), 'samples': self.samples}, indent=2),
                                                       encoding='utf-8')
