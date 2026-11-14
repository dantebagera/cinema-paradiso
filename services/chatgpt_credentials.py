"""Windows-user-bound credential records; no production-root defaults."""
import ctypes
from ctypes import wintypes
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import uuid


class _Blob(ctypes.Structure):
    _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_ubyte))]


class DPAPIProtector:
    def __init__(self):
        if os.name != 'nt':
            raise RuntimeError('ChatGPT secure storage requires Windows')

    def _crypt(self, data, decrypt):
        source_buffer = ctypes.create_string_buffer(data)
        source = _Blob(len(data), ctypes.cast(source_buffer, ctypes.POINTER(ctypes.c_ubyte)))
        result = _Blob()
        api = ctypes.WinDLL('crypt32', use_last_error=True)
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.LocalFree.argtypes = [ctypes.c_void_p]
        kernel.LocalFree.restype = ctypes.c_void_p
        if decrypt:
            ok = api.CryptUnprotectData(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(result))
        else:
            ok = api.CryptProtectData(ctypes.byref(source), 'Cinema Paradiso ChatGPT', None, None, None, 1,
                                      ctypes.byref(result))
        if not ok:
            raise OSError('Protected credential storage failed')
        try:
            return ctypes.string_at(result.pbData, result.cbData)
        finally:
            kernel.LocalFree(result.pbData)

    def protect(self, data):
        return self._crypt(data, False)

    def unprotect(self, data):
        return self._crypt(data, True)


def _owner_only(directory):
    if os.name != 'nt':
        raise RuntimeError('ChatGPT secure storage requires Windows')
    identity = subprocess.run(['whoami', '/user', '/fo', 'csv', '/nh'], capture_output=True,
                              text=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
    import csv
    sid = next(csv.reader([identity.stdout.strip()]))[1]
    subprocess.run(['icacls', str(directory), '/inheritance:r', '/grant:r', '*' + sid + ':(OI)(CI)F'],
                   capture_output=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)


class CredentialStore:
    def __init__(self, root, *, protector=None, secure_directory=_owner_only):
        self.root = Path(root).resolve()
        self.protector = protector or DPAPIProtector()
        self.secure_directory = secure_directory
        self._lock = threading.RLock()

    def _prepare(self):
        self.root.mkdir(parents=True, exist_ok=True)
        self.secure_directory(self.root)
        (self.root / 'profiles').mkdir(exist_ok=True)
        self.secure_directory(self.root / 'profiles')

    def _atomic(self, path, data):
        self._prepare()
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.cp-', delete=False) as output:
                temporary = Path(output.name)
                output.write(data)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, path)
        finally:
            if temporary and temporary.exists():
                temporary.unlink()

    def host_id(self):
        with self._lock, self._named_mutex('installation'):
            path = self.root / 'host.json'
            if path.exists():
                value = json.loads(path.read_text(encoding='utf-8'))['host_id']
                uuid.UUID(value.removeprefix('urn:uuid:'))
                return value
            value = 'urn:uuid:' + str(uuid.uuid4())
            self._atomic(path, json.dumps({'host_id': value}).encode())
            return value

    @contextmanager
    def _named_mutex(self, opaque_id):
        # Local Windows session namespace; the name contains no account/credential.
        digest = hashlib.sha256((os.path.normcase(str(self.root)) + ':' + opaque_id).encode()).hexdigest()
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
        kernel.CreateMutexW.restype = wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.WaitForSingleObject.restype = wintypes.DWORD
        kernel.ReleaseMutex.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.CreateMutexW(None, False, 'Local\\CP-ChatGPT-' + digest)
        if not handle:
            raise OSError('Credential lock unavailable')
        acquired = False
        try:
            result = kernel.WaitForSingleObject(handle, 30000)
            acquired = result in (0, 0x80)  # Acquired, or abandoned owner with recoverable record.
            if not acquired:
                raise OSError('Credential lock timed out')
            yield
        finally:
            if acquired:
                kernel.ReleaseMutex(handle)
            kernel.CloseHandle(handle)

    def refresh_lock(self, profile_id):
        self._path(profile_id)  # Validate before constructing a cross-process lock.
        return self._named_mutex(profile_id)

    def _path(self, profile_id):
        if str(uuid.UUID(profile_id)) != profile_id:
            raise ValueError('Invalid account ID')
        return self.root / 'profiles' / (profile_id + '.bin')

    def create(self, record):
        profile_id = str(uuid.uuid4())
        self.replace(profile_id, record)
        return profile_id

    def load(self, profile_id):
        return json.loads(self.protector.unprotect(self._path(profile_id).read_bytes()))

    def replace(self, profile_id, record):
        with self._lock:
            self._atomic(self._path(profile_id), self.protector.protect(json.dumps(record).encode('utf-8')))

    def profiles(self):
        result = []
        for path in sorted((self.root / 'profiles').glob('*.bin')):
            record = self.load(path.stem)
            if record.get('pending_registration'):
                continue  # An issued client without verified identity is not a usable account.
            result.append({'account_id': path.stem, 'email': record.get('email', ''),
                           'label': record.get('label') or ('Registration ' + path.stem[:8]),
                           'connected': bool(record.get('access_token')) and not record.get('revoking'),
                           'plan_enabled': 'chatgpt.tokens.use.direct' in record.get('scopes', [])})
        return result
