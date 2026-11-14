import os,subprocess,sys
from pathlib import Path
from pass3_support import new_fixture_root
R=Path(__file__).parent;root=new_fixture_root(R/'tmp','store-check')
env={**os.environ,'CP_ISOLATION_ROOT':str(R),'CP_ISOLATION_ROLE':'suite',
 'PYTHONPATH':os.pathsep.join([str(R),str(R/'checkout')]),'PYTHONDONTWRITEBYTECODE':'1',
 'CP_TEST_MODE':'1','CP_TEST_ROOT':str(root),'CP_TEST_QBT_MODE':'embedded',
 'TEMP':str(R/'tmp'),'TMP':str(R/'tmp'),'LOCALAPPDATA':str(R/'localappdata'),'PYTHONIOENCODING':'utf-8'}
raise SystemExit(subprocess.run([sys.executable,str(R/'pass3_store_checks.py')],cwd=R/'checkout',env=env).returncode)
