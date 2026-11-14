import os,subprocess,sys
from pathlib import Path
from pass3_support import new_fixture_root
R=Path(__file__).parent;kind=sys.argv[1];root=new_fixture_root(R/'tmp',kind)
env={**os.environ,'CP_ISOLATION_ROOT':str(R),'CP_ISOLATION_ROLE':'suite',
 'PYTHONPATH':os.pathsep.join([str(R),str(R/'checkout')]),'PYTHONDONTWRITEBYTECODE':'1',
 'CP_TEST_MODE':'1','CP_TEST_ROOT':str(root),'CP_TEST_QBT_MODE':'embedded',
 'CP_TV_PERF_BASELINE_SOURCE':str(R/'pass2-tv-baseline'),'TEMP':str(R/'tmp'),'TMP':str(R/'tmp'),
 'LOCALAPPDATA':str(R/'localappdata'),'PYTHONIOENCODING':'utf-8'}
tests=['tests.test_tv_library_read_performance'] if kind=='tv-module' else [
 'tests.test_tv_library_read_performance.TVLibraryProbeContractTests.test_invalid_observation_preserves_evidence']
command=[sys.executable,'-m','unittest',*tests,'-v']
result=subprocess.run(command,cwd=R/'checkout',env=env)
with (R/'pass3-unit-runs.jsonl').open('a') as f:f.write(__import__('json').dumps({'kind':kind,'root':str(root),'tests':tests,'exit_code':result.returncode})+'\n')
raise SystemExit(result.returncode)
