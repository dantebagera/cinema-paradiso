"""Fresh allowance; fast monitoring and an independent process-tree deadline."""
import argparse,ctypes,importlib.util,json,os,subprocess,sys,tempfile,threading,time
from pathlib import Path
from ctypes import wintypes as w
R=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('previous_budget_structures',R/'budget-pass2.py')
old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
def footprint():
    total=0;pending=[str(R)]
    while pending:
        with os.scandir(pending.pop()) as entries:
            for entry in entries:
                try:
                    if entry.is_symlink():raise RuntimeError('Unexpected link in disposable tree')
                    if entry.is_dir(follow_symlinks=False):pending.append(entry.path)
                    elif entry.is_file(follow_symlinks=False):total+=entry.stat(follow_symlinks=False).st_size
                except FileNotFoundError:pass
    return total
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--name',required=True)
    parser.add_argument('--expected-exit',type=int,default=0,choices=[0,1])
    parser.add_argument('command',nargs=argparse.REMAINDER);a=parser.parse_args()
    assert os.name=='nt' and os.environ.get('CP_TEST_MODE')=='1'
    assert os.environ.get('CP_TEST_QBT_MODE')=='embedded'
    assert Path(os.environ['CP_TEST_ROOT']).resolve()==R and Path(tempfile.gettempdir()).resolve() in R.parents
    ledger=R/'bounded-pass-3.json';state=json.loads(ledger.read_text()) if ledger.exists() else {'batches':[]}
    assert not state.get('closed') and not state.get('halted'),'Allowance stopped or closed'
    used=sum(x['active_seconds'] for x in state['batches']);written=sum(x['process_tree_write_bytes'] for x in state['batches'])
    # Leave ten seconds for cleanup/accounting; no intentional batch approaches the 240s cap.
    limit=min(230.,600.-used-10.);assert limit>0 and written<8*1024**3
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateJobObjectW.argtypes=[ctypes.c_void_p,w.LPCWSTR];kernel.CreateJobObjectW.restype=w.HANDLE
    kernel.AssignProcessToJobObject.argtypes=[w.HANDLE,w.HANDLE];kernel.AssignProcessToJobObject.restype=w.BOOL
    kernel.QueryInformationJobObject.argtypes=[w.HANDLE,ctypes.c_int,ctypes.c_void_p,w.DWORD,ctypes.c_void_p]
    kernel.QueryInformationJobObject.restype=w.BOOL
    kernel.TerminateJobObject.argtypes=[w.HANDLE,w.UINT];kernel.CloseHandle.argtypes=[w.HANDLE]
    ntdll=ctypes.WinDLL('ntdll');ntdll.NtResumeProcess.argtypes=[w.HANDLE];ntdll.NtResumeProcess.restype=ctypes.c_long
    job=kernel.CreateJobObjectW(None,None);assert job
    old.configure_kill_on_close(kernel,job)
    began=time.perf_counter();done=threading.Event();reason=[];sample={'bytes':footprint(),'error':None}
    assert sample['bytes']<4*1024**3
    def stop(why):
        if not reason:reason.append(why)
        kernel.TerminateJobObject(job,98)
    def watchdog():
        if not done.wait(max(0,limit-(time.perf_counter()-began))):stop('active deadline')
    def sampler():
        while not done.wait(2):
            try:
                sample['bytes']=max(sample['bytes'],footprint())
                if sample['bytes']>4*1024**3:stop('temporary footprint limit');return
            except Exception as error:sample['error']=repr(error);stop('footprint sampling failure');return
    threads=[threading.Thread(target=f,daemon=True) for f in (watchdog,sampler)]
    for thread in threads:thread.start()
    account=old.ACCOUNTING();command=a.command[1:] if a.command[:1]==['--'] else a.command
    log=R/(a.name+'.log')
    try:
        with log.open('wb') as output:
            process=subprocess.Popen(command,stdout=output,stderr=subprocess.STDOUT,creationflags=0x4|subprocess.CREATE_NO_WINDOW)
            if not kernel.AssignProcessToJobObject(job,int(process._handle)):process.kill();raise ctypes.WinError(ctypes.get_last_error())
            assert ntdll.NtResumeProcess(int(process._handle))==0
            while True:
                assert kernel.QueryInformationJobObject(job,8,ctypes.byref(account),ctypes.sizeof(account),None)
                if written+account.io.write_bytes>8*1024**3:stop('cumulative process write limit')
                if process.poll() is not None and account.basic.active_processes==0:break
                time.sleep(.1)
            process.wait(timeout=5)
        done.set()
        for thread in threads:thread.join(timeout=3)
        assert kernel.QueryInformationJobObject(job,8,ctypes.byref(account),ctypes.sizeof(account),None)
        sample['bytes']=max(sample['bytes'],footprint())
        elapsed=round(time.perf_counter()-began,3)
        if elapsed>240 or used+elapsed>600:reason.append('accounted wall limit exceeded')
        if sample['bytes']>4*1024**3:reason.append('final footprint limit')
        batch={'name':a.name,'command':command,'exit_code':process.returncode,'expected_exit_code':a.expected_exit,
         'active_seconds':elapsed,'process_tree_cpu_seconds':(account.basic.user_time+account.basic.kernel_time)/10**7,
         'process_tree_write_bytes':account.io.write_bytes,'processes':account.basic.total_processes,
         'temporary_footprint_bytes':sample['bytes'],'stop_reason':'; '.join(reason),'log':str(log)}
        state['batches'].append(batch);state['halted']=bool(reason)
        ledger.write_text(json.dumps(state,indent=2)+'\n')
        print(json.dumps(batch),flush=True);print(log.read_text(encoding='utf-8',errors='replace')[-1600:],flush=True)
        return int(bool(reason) or process.returncode!=a.expected_exit)
    finally:done.set();kernel.TerminateJobObject(job,99);kernel.CloseHandle(job)
if __name__=='__main__':raise SystemExit(main())
