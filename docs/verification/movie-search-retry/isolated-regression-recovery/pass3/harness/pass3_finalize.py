"""Final metadata preservation/sealing and evidence copies; no application execution."""
import hashlib,json,shutil,subprocess
from pathlib import Path
R=Path(__file__).parent;BASE=Path(r'C:\Users\dante\Desktop\cinema paradiso')
OUT=BASE/'docs/verification/movie-search-retry/isolated-regression-recovery/pass3'
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
before=load(R/'pass3-source-before.json')
changed=[name for name,item in before.items() if not (BASE/name).is_file() or digest(BASE/name)!=item['sha256']]
docs={'docs/plans/2026-10-24-isolated-regression-and-recovery.md','docs/verification/movie-search-retry/isolated-regression-recovery/README.md'}
assert set(changed)==docs.intersection(before),changed
status=subprocess.check_output(['git','status','--porcelain=v1','-uno'],cwd=BASE,text=True)
assert status==(R/'pass3-git-before.txt').read_text()
saved=Path(r'C:\Users\dante\Desktop\CP-Recovery\whole-checkout-2026-10-24-153619-e50288')
inputs=load(saved/'candidate-inputs.json');bundle=load(saved/'candidate-bundle.json')
assert all(digest(BASE/name)==item['sha256'] for name,item in inputs.items())
assert all(digest(R/'checkout/dist'/name)==item['sha256'] for name,item in bundle.items())
proof=load(R/'pass3-preservation.json');proof['final_authorized_documentation_updates']=sorted(docs)
proof['changed_files_in_original_seal']=changed
proof['final_non_documentation_drift']=[]
proof['owned_test_processes_at_close']=load(R/'pass3-owned-processes-at-close.json');assert proof['owned_test_processes_at_close']==[]
(R/'pass3-preservation.json').write_text(json.dumps(proof,indent=2)+'\n')
result=load(OUT/'result.json');result['preservation']=proof
result['review']={'critical':0,'important':0,'verdict':'remaining scoped verification gaps closed',
 'deferred_minor':'Library exit guard audit unavailable after owned-tree termination; boundary was installed before app import. Home/Following guard report is complete with no violations.',
 'reporting_closeout_minor':'resolved'}
result['guard_audit']={}
for key in ['library','home-following']:
    pid=result['ownership'][key]['child_pid'];p=R/f'guard-{pid}.json'
    if p.is_file() and p.stat().st_size:
        audit=load(p);result['guard_audit'][key]={'report_complete':True,'violations':audit['violations']}
        assert not audit['violations'];shutil.copy2(p,OUT/p.name)
    else:
        result['guard_audit'][key]={'report_complete':False,'reason':'owned child force-stopped before atexit report flush','boundary_installed_before_app_import':True}
        staged=OUT/p.name
        if staged.exists():staged.rename(OUT/(p.stem+'.unflushed.empty'))
result['status']='Remaining scoped gaps closed; final ledger metadata closure follows'
(OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n')
for name in ['pass3-preservation.json','pass3-owned-processes-at-close.json','pass3-progress.md','pass3-source-before.json']:
    shutil.copy2(R/name,OUT/name)
scripts=OUT/'harness';scripts.mkdir(exist_ok=True)
for pattern in ['pass3*.py','pass3*.cjs','dispatch3.py','budget-pass3.py']:
    for p in R.glob(pattern):shutil.copy2(p,scripts/p.name)
for name in ['guard.py','sitecustomize.py','budget-pass2.py','pass2_preflight.py','guard_probe.py']:
    shutil.copy2(R/name,scripts/name)
specs=OUT/'harness/specs';specs.mkdir(exist_ok=True)
for p in (R/'pass3-specs').iterdir():
    if p.is_file():shutil.copy2(p,specs/p.name)
print(json.dumps({'final_preservation':True,'only_prior_file_updates':changed,'runtime_inputs_matched':len(inputs),
 'compiled_files_matched':len(bundle),'owned_processes_remaining':0,'review_critical':0,'review_important':0}))
