import hashlib,json,os,shutil,subprocess
from pathlib import Path
R=Path(__file__).parent;BASE=Path(r'C:\Users\dante\Desktop\cinema paradiso');CODE=R/'checkout'
SAVED=Path(r'C:\Users\dante\Desktop\CP-Recovery\whole-checkout-2026-10-24-153619-e50288')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
before=load(R/'pass2-source-before.json');seal={}
for name in before:
    p=BASE/name;assert p.is_file(),name
    seal[name]={'sha256':digest(p),'bytes':p.stat().st_size}
for p in (BASE/'docs/verification/movie-search-retry/isolated-regression-recovery').rglob('*'):
    if p.is_file():seal[p.relative_to(BASE).as_posix()]={'sha256':digest(p),'bytes':p.stat().st_size}
(R/'pass3-source-before.json').write_text(json.dumps(seal,indent=2)+'\n')
(R/'pass3-git-before.txt').write_text(subprocess.check_output(['git','status','--porcelain=v1','-uno'],cwd=BASE,text=True))
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=BASE,text=True).strip()
assert head=='be511f98846a67a182e5b371ad087938e9344362'
inputs=load(SAVED/'candidate-inputs.json')
for name,record in inputs.items():
    assert digest(BASE/name)==record['sha256'],('current runtime drift',name)
    assert digest(CODE/name)==record['sha256'],('copied runtime drift',name)
bundle=load(SAVED/'candidate-bundle.json')
for name,record in bundle.items():assert digest(CODE/'dist'/name)==record['sha256'],name
for name in ['test_library_action_ux.py','test_full_row_card_grids_ui.py']:
    assert digest(CODE/'tests'/name)==digest(BASE/'tests'/name),name
specs=R/'pass3-specs';specs.mkdir(exist_ok=False)
for name in ['library-search-performance.spec.js','following-refresh.spec.js','home-dashboard-hybrid.spec.js','home-loading.spec.js']:
    shutil.copy2(BASE/'tests/e2e'/name,specs/name)
proof={'head':head,'sealed_files':len(seal),'runtime_inputs':len(inputs),'bundle_files':len(bundle),
       'copied_source_and_compiled_bundle_match':True,'test_worker_count':1}
(R/'pass3-prepared.json').write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps(proof))
