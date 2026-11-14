"""Metadata-only preservation and owned-PID checks; no app imports or live requests."""
import ctypes,hashlib,json,subprocess,sys
from ctypes import wintypes as w
from pathlib import Path
R=Path(__file__).parent;BASE=Path(r'C:\Users\dante\Desktop\cinema paradiso');CODE=R/'checkout'
SAVED=Path(r'C:\Users\dante\Desktop\CP-Recovery\whole-checkout-2026-10-24-153619-e50288')
PHASE=sys.argv[1];assert PHASE in {'preclose','final'}
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
allowed={'docs/plans/2026-10-24-library-exit-audit-final.md','docs/verification/movie-search-retry/isolated-regression-recovery/README.md'} if PHASE=='final' else set()
before=load(R/'pass4-source-before.json')
changed=[n for n,v in before.items() if not (BASE/n).is_file() or digest(BASE/n)!=v['sha256']]
assert set(changed)<=allowed,changed
status=subprocess.check_output(['git','status','--porcelain=v1','-uno'],cwd=BASE,text=True)
assert status==(R/'pass4-git-before.txt').read_text()
all_status=subprocess.check_output(['git','status','--porcelain=v1','--untracked-files=all'],cwd=BASE,text=True)
old_lines=set((R/'pass4-git-all-before.txt').read_text().splitlines());new_lines=set(all_status.splitlines())
assert old_lines<=new_lines
additions=sorted(new_lines-old_lines)
assert all(line.startswith('?? docs/verification/movie-search-retry/isolated-regression-recovery/library-exit-audit/') for line in additions),additions
inputs=load(SAVED/'candidate-inputs.json');bundle=load(SAVED/'candidate-bundle.json')
for n,v in inputs.items():assert digest(BASE/n)==digest(CODE/n)==v['sha256'],n
for n,v in bundle.items():assert digest(CODE/'dist'/n)==v['sha256'],n
prior=load(R/'pass4-prior-evidence-seal.json')
assert all((R/n).is_file() and digest(R/n)==v['sha256'] for n,v in prior.items())
completion=load(R/'pass4-qualified/completion.json');cleanup=load(R/'pass4-qualified/owned-cleanup.json')
assert completion['qualified'] and completion['server_exit_code']==0 and not completion['forced_pids']
assert not cleanup['remaining'] and not cleanup['outer_forced_pids'] and cleanup['error'] is None
kernel=ctypes.WinDLL('kernel32',use_last_error=True)
kernel.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];kernel.OpenProcess.restype=w.HANDLE
kernel.WaitForSingleObject.argtypes=[w.HANDLE,w.DWORD];kernel.WaitForSingleObject.restype=w.DWORD
kernel.CloseHandle.argtypes=[w.HANDLE]
owned=set(cleanup['owned_pids'])|set(load(R/'pass4-owned-cleanup.json')['owned_pids'])
remaining=[]
for pid in sorted(owned):
    handle=kernel.OpenProcess(0x100000,False,pid)
    if handle:
        try:
            state=kernel.WaitForSingleObject(handle,0)
            assert state in {0,258},(pid,state)
            if state==258:remaining.append(pid)
        finally:kernel.CloseHandle(handle)
    else:assert ctypes.get_last_error()==87,('Cannot confirm owned PID exit',pid,ctypes.get_last_error())
assert not remaining,remaining
proof={'phase':PHASE,'safe_files_sealed':len(before),'authorized_doc_updates':changed,'source_test_drift':[],
 'runtime_inputs_matched':len(inputs),'bundle_files_matched':len(bundle),'prior_evidence_files_matched':len(prior),
 'tracked_dirty_entries_preserved':len(status.splitlines()),'preexisting_git_status_lines_preserved':True,
 'new_status_entries':additions,'owned_pids_checked':sorted(owned),'remaining_owned_processes':remaining,
 'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=BASE,text=True).strip()}
assert proof['head']=='be511f98846a67a182e5b371ad087938e9344362'
(R/f'pass4-preservation-{PHASE}.json').write_text(json.dumps(proof,indent=2)+'\n')
print(json.dumps({k:v for k,v in proof.items() if k!='new_status_entries'}))
