"""Bounded Windows process-tree runner for the approved disposable test pass."""
import argparse
import ctypes
from ctypes import wintypes as w
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time


class IO(ctypes.Structure):
    _fields_ = [(name, ctypes.c_ulonglong) for name in (
        'read_operations', 'write_operations', 'other_operations',
        'read_bytes', 'write_bytes', 'other_bytes')]


class BASIC(ctypes.Structure):
    _fields_ = [(name, ctypes.c_longlong) for name in (
        'user_time', 'kernel_time', 'period_user', 'period_kernel')]
    _fields_ += [(name, w.DWORD) for name in (
        'page_faults', 'total_processes', 'active_processes', 'terminated_processes')]


class ACCOUNTING(ctypes.Structure):
    _fields_ = [('basic', BASIC), ('io', IO)]


class JOB_LIMITS(ctypes.Structure):
    _fields_=[('process_time',ctypes.c_longlong),('job_time',ctypes.c_longlong),('flags',w.DWORD),
      ('minimum',ctypes.c_size_t),('maximum',ctypes.c_size_t),('process_count',w.DWORD),
      ('affinity',ctypes.c_size_t),('priority',w.DWORD),('scheduling',w.DWORD)]
class EXTENDED_LIMITS(ctypes.Structure):
    _fields_=[('basic',JOB_LIMITS),('io',IO),('process_memory',ctypes.c_size_t),
      ('job_memory',ctypes.c_size_t),('peak_process',ctypes.c_size_t),('peak_job',ctypes.c_size_t)]
def configure_kill_on_close(kernel,job):
    kernel.SetInformationJobObject.argtypes=[w.HANDLE,ctypes.c_int,ctypes.c_void_p,w.DWORD]
    kernel.SetInformationJobObject.restype=w.BOOL
    limits=EXTENDED_LIMITS();limits.basic.flags=0x2000
    if not kernel.SetInformationJobObject(job,9,ctypes.byref(limits),ctypes.sizeof(limits)):
        raise ctypes.WinError(ctypes.get_last_error())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', required=True)
    parser.add_argument('--expected-exit', type=int, choices=[0, 1], default=0)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    root = Path(os.environ['CP_TEST_ROOT']).resolve()
    if (os.name != 'nt' or os.environ.get('CP_TEST_MODE') != '1'
            or os.environ.get('CP_TEST_QBT_MODE') != 'embedded'
            or Path(tempfile.gettempdir()).resolve() not in root.parents):
        raise RuntimeError('Windows OS-temp embedded isolation is mandatory')
    ledger = root / 'bounded-pass-2.json'
    state = json.loads(ledger.read_text()) if ledger.exists() else {'batches': []}
    if state.get('halted') or state.get('closed'):
        raise RuntimeError('This allowance is stopped or closed; no automatic retry')
    used = sum(b['active_seconds'] for b in state['batches'])
    written = sum(b['process_tree_write_bytes'] for b in state['batches'])
    limit = min(240.0, 600.0 - used)
    if limit <= 0 or written >= 8*1024**3:
        raise RuntimeError('Approved cumulative allowance exhausted')
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, w.LPCWSTR]
    kernel.CreateJobObjectW.restype = w.HANDLE
    kernel.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
    kernel.AssignProcessToJobObject.restype = w.BOOL
    kernel.QueryInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD, ctypes.c_void_p]
    kernel.QueryInformationJobObject.restype = w.BOOL
    kernel.TerminateJobObject.argtypes = [w.HANDLE, w.UINT]
    kernel.CloseHandle.argtypes = [w.HANDLE]
    ntdll = ctypes.WinDLL('ntdll')
    ntdll.NtResumeProcess.argtypes = [w.HANDLE]
    ntdll.NtResumeProcess.restype = ctypes.c_long
    job = kernel.CreateJobObjectW(None, None)
    if not job:
        raise ctypes.WinError(ctypes.get_last_error())
    configure_kill_on_close(kernel,job)
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    log = root / (args.name + '.log')
    started = time.perf_counter()
    reason = ''
    accounting = ACCOUNTING()
    try:
        with log.open('wb') as output:
            process = subprocess.Popen(command, stdout=output, stderr=subprocess.STDOUT,
                                       creationflags=0x4 | subprocess.CREATE_NO_WINDOW)
            if not kernel.AssignProcessToJobObject(job, int(process._handle)):
                process.kill()
                raise ctypes.WinError(ctypes.get_last_error())
            if ntdll.NtResumeProcess(int(process._handle)) != 0:
                kernel.TerminateJobObject(job, 99)
                raise RuntimeError('Could not resume owned test process')
            while True:
                if not kernel.QueryInformationJobObject(job, 8, ctypes.byref(accounting), ctypes.sizeof(accounting), None):
                    kernel.TerminateJobObject(job, 99)
                    raise ctypes.WinError(ctypes.get_last_error())
                elapsed = time.perf_counter() - started
                if elapsed > limit:
                    reason = 'active time limit'
                elif written + accounting.io.write_bytes > 8*1024**3:
                    reason = 'cumulative process write limit'
                # Whole temporary root, including the retained corrected bundle.
                footprint = 0
                for path in root.rglob('*'):
                    try:
                        if path.is_file():
                            footprint += path.stat().st_size
                    except FileNotFoundError:
                        pass  # SQLite can retire a disposable WAL during enumeration.
                if footprint > 4*1024**3:
                    reason = 'temporary footprint limit'
                if reason:
                    kernel.TerminateJobObject(job, 98)
                    break
                if process.poll() is not None and accounting.basic.active_processes == 0:
                    break
                time.sleep(1)
            process.wait(timeout=5)
        kernel.QueryInformationJobObject(job, 8, ctypes.byref(accounting), ctypes.sizeof(accounting), None)
        batch = {'name': args.name, 'command': command, 'exit_code': process.returncode,
                 'active_seconds': round(time.perf_counter() - started, 3),
                 'process_tree_cpu_seconds': (accounting.basic.user_time + accounting.basic.kernel_time) / 10**7,
                 'process_tree_write_bytes': accounting.io.write_bytes,
                 'processes': accounting.basic.total_processes, 'temporary_footprint_bytes': footprint,
                 'stop_reason': reason, 'log': str(log)}
        batch['expected_exit_code'] = args.expected_exit
        state['batches'].append(batch)
        state['halted'] = bool(reason)
        state['product_failure'] = bool(process.returncode != args.expected_exit)
        ledger.write_text(json.dumps(state, indent=2) + '\n')
        print(json.dumps(batch))
        print(log.read_text(encoding='utf-8', errors='replace')[-1800:])
        return 1 if state['halted'] or state['product_failure'] else 0
    finally:
        kernel.TerminateJobObject(job, 99)
        kernel.CloseHandle(job)


if __name__ == '__main__':
    sys.exit(main())
