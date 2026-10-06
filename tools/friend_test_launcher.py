"""Supervisor for the explicitly private Windows friend package, not the live app."""
import argparse
import json
import os
from pathlib import Path
import signal
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

PORTS = {'CP': 15000, 'Prowlarr': 19696, 'FlareSolverr': 18191,
         'qBittorrent': 18686}


def write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    os.replace(temp, path)


def prepare_config(root):
    root = Path(root).resolve()
    config_path = root / 'config.json'
    config = json.loads(config_path.read_text(encoding='utf-8-sig'))
    marker = root / 'data/friend-root.json'
    old_root = json.loads(marker.read_text())['root'] if marker.exists() else None

    def relocate(value):
        path = Path(value)
        if not path.is_absolute():
            return str(root / path)
        if old_root:
            try:
                return str(root / path.relative_to(Path(old_root)))
            except ValueError:
                pass
        return str(path)

    for key in ('movies_dir', 'user_data_dir', 'tmdb_cache_dir', 'qbt_download_dir', 'qbt_incomplete_dir'):
        if config.get(key):
            config[key] = relocate(config[key])
    for key in ('movies_dirs', 'tv_roots'):
        config[key] = [relocate(value) for value in config.get(key, [])]
    for relative in ('library/movies', 'library/tv', 'cache', 'data/runtime'):
        (root / relative).mkdir(parents=True, exist_ok=True)
    write_json(config_path, config)
    write_json(marker, {'root': str(root)})
    return config


def require_free_ports(ports):
    for name, port in ports.items():
        with socket.socket() as probe:
            if os.name == 'nt':
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            try:
                probe.bind(('127.0.0.1', port))
            except OSError as error:
                raise RuntimeError(f'{name} port {port} is occupied. Close the conflicting app or ask Codex to diagnose it. No existing process was stopped.') from error


def external_ollama_available(url):
    """Read-only check. Missing optional AI must not prevent CP from opening."""
    if not url:
        return False
    try:
        with urllib.request.urlopen(url.rstrip('/') + '/api/version', timeout=3) as response:
            payload = json.load(response)
            return isinstance(payload, dict) and bool(payload.get('version'))
    except (OSError, ValueError, urllib.error.URLError):
        return False


def signin_external_ollama(root):
    executable = shutil.which('ollama')
    if not executable:
        installed = Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs/Ollama/ollama.exe'
        if installed.is_file():
            executable = str(installed)
    if not executable:
        raise RuntimeError('Ollama is not installed or cannot be found. Follow the Ollama setup section in CODEX-HANDOVER.md.')
    config = json.loads((root / 'config.json').read_text(encoding='utf-8-sig'))
    env = os.environ.copy()
    env['OLLAMA_HOST'] = config.get('ollama_url') or 'http://127.0.0.1:11434'
    # Use the recipient's existing account/model storage; CP does not own it.
    return subprocess.call([executable, 'signin'], cwd=root, env=env)


def cp_environment(root):
    root = Path(root).resolve()
    env = os.environ.copy()
    for key in list(env):
        if key.startswith('CP_TEST_') or key in ('CP_TEST_MODE', 'CP_TV_E2E', 'CP_DISCOVER_PAGING_E2E'):
            env.pop(key)
    env.update(CP_PORT=str(PORTS['CP']), CP_PORTABLE_DATA='1',
               LOCALAPPDATA=str(root / 'data/localappdata'))
    return env


class OwnedProcesses:
    """A Windows Job Object closes every owned descendant if this launcher exits."""
    def __init__(self, log_root):
        self.log_root = Path(log_root)
        self.log_root.mkdir(parents=True, exist_ok=True)
        self.children = []
        self.logs = []
        self.job = None
        if os.name == 'nt':
            import ctypes
            from ctypes import wintypes

            class BasicLimits(ctypes.Structure):
                _fields_ = [('PerProcessUserTimeLimit', ctypes.c_int64), ('PerJobUserTimeLimit', ctypes.c_int64),
                            ('LimitFlags', wintypes.DWORD), ('MinimumWorkingSetSize', ctypes.c_size_t),
                            ('MaximumWorkingSetSize', ctypes.c_size_t), ('ActiveProcessLimit', wintypes.DWORD),
                            ('Affinity', ctypes.c_size_t), ('PriorityClass', wintypes.DWORD), ('SchedulingClass', wintypes.DWORD)]

            class IO(ctypes.Structure):
                _fields_ = [(name, ctypes.c_uint64) for name in ('ReadOperationCount', 'WriteOperationCount',
                            'OtherOperationCount', 'ReadTransferCount', 'WriteTransferCount', 'OtherTransferCount')]

            class ExtendedLimits(ctypes.Structure):
                _fields_ = [('BasicLimitInformation', BasicLimits), ('IoInfo', IO),
                            ('ProcessMemoryLimit', ctypes.c_size_t), ('JobMemoryLimit', ctypes.c_size_t),
                            ('PeakProcessMemoryUsed', ctypes.c_size_t), ('PeakJobMemoryUsed', ctypes.c_size_t)]

            self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            self.kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
            self.kernel.CreateJobObjectW.restype = wintypes.HANDLE
            self.kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
            self.kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
            self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            self.kernel.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
            self.kernel.QueryInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p]
            self.kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
            self.kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
            self.kernel.Thread32First.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
            self.kernel.Thread32Next.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
            self.kernel.OpenThread.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            self.kernel.OpenThread.restype = wintypes.HANDLE
            self.kernel.ResumeThread.argtypes = [wintypes.HANDLE]
            self.job = self.kernel.CreateJobObjectW(None, None)
            limits = ExtendedLimits()
            limits.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if not self.job or not self.kernel.SetInformationJobObject(self.job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
                self.close()
                raise ctypes.WinError(ctypes.get_last_error())

    def start(self, name, command, cwd, env=None):
        log = open(self.log_root / f'{name}.log', 'ab', buffering=0)
        self.logs.append(log)
        process = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                   stdout=log, stderr=subprocess.STDOUT,
                                   creationflags=(subprocess.CREATE_NO_WINDOW | 0x4) if os.name == 'nt' else 0)
        self.children.append((name, process))
        if self.job and not self.kernel.AssignProcessToJobObject(self.job, int(process._handle)):
            process.kill()
            raise RuntimeError(f'Cannot own {name} process; refusing unmanaged startup')
        if self.job:
            import ctypes
            from ctypes import wintypes

            class ThreadEntry(ctypes.Structure):
                _fields_ = [('dwSize', wintypes.DWORD), ('cntUsage', wintypes.DWORD),
                            ('threadId', wintypes.DWORD), ('ownerPid', wintypes.DWORD),
                            ('basePriority', wintypes.LONG), ('deltaPriority', wintypes.LONG), ('flags', wintypes.DWORD)]
            snapshot = self.kernel.CreateToolhelp32Snapshot(4, 0)
            thread = ThreadEntry()
            thread.dwSize = ctypes.sizeof(thread)
            resumed = False
            try:
                more = self.kernel.Thread32First(snapshot, ctypes.byref(thread))
                while more:
                    if thread.ownerPid == process.pid:
                        handle = self.kernel.OpenThread(2, False, thread.threadId)
                        if handle:
                            try:
                                resumed = self.kernel.ResumeThread(handle) != -1
                            finally:
                                self.kernel.CloseHandle(handle)
                            break
                    more = self.kernel.Thread32Next(snapshot, ctypes.byref(thread))
            finally:
                self.kernel.CloseHandle(snapshot)
            if not resumed:
                process.kill()
                raise RuntimeError(f'Could not resume owned {name} process')
        return process

    def close(self):
        if self.job:
            import ctypes
            self.kernel.TerminateJobObject(self.job, 0)
            # Closing a job schedules termination; wait for descendants to release
            # inherited log handles before claiming shutdown or moving the folder.
            accounting = ctypes.create_string_buffer(48)
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                if not self.kernel.QueryInformationJobObject(self.job, 1, accounting, 48, None):
                    break
                if int.from_bytes(accounting.raw[40:44], 'little') == 0:
                    break
                time.sleep(.05)
            self.kernel.CloseHandle(self.job)
            self.job = None
        for _, process in reversed(self.children):
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        for log in self.logs:
            log.close()
        if os.name == 'nt':
            import ctypes
            from ctypes import wintypes
            self.kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                               ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
            self.kernel.CreateFileW.restype = wintypes.HANDLE
            for log in self.logs:
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    handle = self.kernel.CreateFileW(str(Path(log.name).resolve()), 0x80000000, 0, None, 3, 128, None)
                    if handle != ctypes.c_void_p(-1).value:
                        self.kernel.CloseHandle(handle)
                        break
                    time.sleep(.05)


def wait_ready(process, name, url, *, headers=None, timeout=90):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f'{name} exited with code {process.returncode}; see data/runtime/friend/{name}.log')
        try:
            request = urllib.request.Request(url, headers=headers or {})
            with urllib.request.urlopen(request, timeout=2) as response:
                if response.status == 200:
                    return
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(.5)
    raise RuntimeError(f'{name} startup timed out; see data/runtime/friend/{name}.log')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--signin', action='store_true')
    parser.add_argument('--stop', action='store_true')
    args = parser.parse_args()
    root = args.root.resolve()
    if not (root / 'TEST-PACKAGE.json').is_file():
        raise RuntimeError('This launcher is only for an assembled private test package')
    stop = root / 'data/friend-stop'
    if args.stop:
        stop.parent.mkdir(parents=True, exist_ok=True)
        stop.touch()
        return 0
    if args.signin:
        return signin_external_ollama(root)
    lock = None
    owned = None
    window_started = False
    window_helper = None
    try:
        (root / 'data').mkdir(parents=True, exist_ok=True)
        lock = open(root / 'data/friend-launch.lock', 'a+b')
        if os.name == 'nt':
            import msvcrt
            lock.seek(0)
            if not lock.read(1):
                lock.write(b'0')
                lock.flush()
            lock.seek(0)
            try:
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as error:
                raise RuntimeError('This test package is already running. Use its existing window or Stop CP.bat.') from error
        require_free_ports(PORTS)
        config = prepare_config(root)
        ollama_url = config.get('ollama_url', '')
        if external_ollama_available(ollama_url):
            print(f'Connected to your installed Ollama at {ollama_url}. CP will not start or stop it.', flush=True)
        else:
            print('Ollama is unavailable. CP will still open; start/install Ollama and connect it through Settings. See CODEX-HANDOVER.md.', flush=True)
        stop.unlink(missing_ok=True)
        owned = OwnedProcesses(root / 'data/runtime/friend')
        env = cp_environment(root)
        flare_env = env.copy()
        flare_env.update(HOST='127.0.0.1', PORT=str(PORTS['FlareSolverr']), LOG_LEVEL='info',
                         BROWSER_TIMEOUT='60000')
        flare = owned.start('FlareSolverr', [str(root / 'runtime/flaresolverr/flaresolverr.exe')], root / 'runtime/flaresolverr', flare_env)
        wait_ready(flare, 'FlareSolverr', f'http://127.0.0.1:{PORTS["FlareSolverr"]}/')
        print('FlareSolverr ready.', flush=True)
        prowlarr = owned.start('Prowlarr', [str(root / 'runtime/prowlarr/Prowlarr.Console.exe'),
                              '-nobrowser', f'-data={root / "data/prowlarr"}'], root / 'runtime/prowlarr', env)
        wait_ready(prowlarr, 'Prowlarr', f'http://127.0.0.1:{PORTS["Prowlarr"]}/api/v1/system/status',
                   headers={'X-Api-Key': config['prowlarr_key']})
        print('Prowlarr ready.', flush=True)
        env['CP_PORT'] = str(PORTS['CP'])
        while True:
            cp = owned.start('CP', [sys.executable, str(root / 'app.py')], root, env)
            wait_ready(cp, 'CP', f'http://127.0.0.1:{PORTS["CP"]}/')
            if not args.no_browser:
                # Edge can share its process with unrelated browser windows. The
                # existing helper owns one window; never place Edge in our job.
                window_helper = subprocess.Popen(['powershell.exe', '-NoProfile', '-WindowStyle', 'Hidden', '-ExecutionPolicy', 'Bypass',
                                  '-File', str(root / 'tools/cp_window.ps1'), '-Action', 'Launch',
                                  '-ProjectRoot', str(root), '-Port', str(PORTS['CP'])], cwd=root,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                  creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                window_started = True
            print(f'CP ready: http://127.0.0.1:{PORTS["CP"]}/ — keep this window open. Ctrl+C or Stop CP.bat stops the package.', flush=True)
            while cp.poll() is None and not stop.exists():
                for name, service in [('Prowlarr', prowlarr), ('FlareSolverr', flare)]:
                    if service.poll() is not None:
                        raise RuntimeError(f'{name} stopped unexpectedly; see data/runtime/friend/{name}.log')
                time.sleep(.5)
            if stop.exists() or cp.returncode != 75:
                return 0 if stop.exists() else cp.returncode
            print('Restarting CP; bundled services remain running.', flush=True)
    except KeyboardInterrupt:
        return 0
    finally:
        if window_started:
            try:
                subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                                str(root / 'tools/cp_window.ps1'), '-Action', 'Close', '-ProjectRoot', str(root),
                                '-Port', str(PORTS['CP'])], cwd=root, timeout=20, capture_output=True,
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            except (OSError, subprocess.TimeoutExpired):
                pass
        if window_helper and window_helper.poll() is None:
            window_helper.terminate()  # Only the helper, never its browser tree.
            window_helper.wait(timeout=5)
        if owned:
            owned.close()
        if lock:
            lock.close()
        stop.unlink(missing_ok=True)


if __name__ == '__main__':
    if hasattr(signal, 'SIGBREAK'):
        signal.signal(signal.SIGBREAK, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    try:
        sys.exit(main())
    except Exception as error:
        print(f'Launch failed: {error}', file=sys.stderr)
        sys.exit(1)
