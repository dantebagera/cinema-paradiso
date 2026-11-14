import json,os,shutil,subprocess,sys,time,urllib.request,uuid
from pathlib import Path
from pass3_support import new_fixture_root,verify_record
R=Path(__file__).parent;CODE=R/'checkout';GROUP=sys.argv[1]
assert GROUP in {'library','home-following'}
STATE=new_fixture_root(R/'tmp','ui-'+GROUP);shutil.copytree(CODE/'dist',STATE/'dist')
nonce=uuid.uuid4().hex
env={**os.environ,'CP_TEST_MODE':'1','CP_TEST_ROOT':str(STATE),'CP_TEST_QBT_MODE':'embedded',
 'CP_DOWNLOAD_COMPLETION_E2E':'1','CP_PORT':'0','CP_TEST_DIST_DIR':str(STATE/'dist'),
 'CP_ISOLATION_ROOT':str(R),'CP_ISOLATION_ROLE':'ui','PYTHONPATH':os.pathsep.join([str(R),str(CODE),str(Path(sys.prefix)/'Lib/site-packages')]),
 'PYTHONDONTWRITEBYTECODE':'1','TEMP':str(R/'tmp'),'TMP':str(R/'tmp'),
 'LOCALAPPDATA':str(R/'localappdata'),'APPDATA':str(R/'appdata'),'USERPROFILE':str(R/'home'),
 'PYTHONNOUSERSITE':'1','PYTHONIOENCODING':'utf-8','CP_PASS3_NONCE':nonce}
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise RuntimeError('Owned fixture redirected')
server=None;browser=None
try:
    log_path=R/f'pass3-ui-{GROUP}-server.log'
    if log_path.exists():shutil.copy2(log_path,R/f'pass3-ui-{GROUP}-server-before-{STATE.name}.log')
    with log_path.open('wb') as log:
        server=subprocess.Popen([sys._base_executable,str(R/'pass3_ui_server.py')],cwd=CODE,env=env,
         stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        deadline=time.monotonic()+25;record=None
        while time.monotonic()<deadline:
            if server.poll() is not None:raise RuntimeError('Owned server exited before readiness')
            if (STATE/'ready.json').exists():
                try:record=json.loads((STATE/'ready.json').read_text());break
                except json.JSONDecodeError:pass
            time.sleep(.1)
        assert record is not None,'No owned readiness record'
        # No HTTP request, mutation, or browser execution precedes this check.
        verify_record(record,pid=server.pid,nonce=nonce,root=STATE)
        base='http://127.0.0.1:'+str(record['port'])
        req=urllib.request.Request(base+'/__sandbox/identity',headers={'X-Sandbox-Nonce':nonce})
        with urllib.request.build_opener(NoRedirect).open(req,timeout=3) as response:identity=json.load(response)
        verify_record(identity,pid=server.pid,nonce=nonce,root=STATE);assert identity==record
        proof={'group':GROUP,'child_pid':server.pid,'root':str(STATE),'baseURL':base,'identity_verified_before_browser':True}
        (R/f'pass3-ui-{GROUP}-ownership.json').write_text(json.dumps(proof,indent=2)+'\n')
        files=['library-search-performance.spec.js'] if GROUP=='library' else ['following-refresh.spec.js','home-dashboard-hybrid.spec.js','home-loading.spec.js']
        grep='rapid live typing|stale success|foreground typing|Movie to File|pass3 quiet' if GROUP=='library' else 'reconnect ownership runs|another completion during ownership|health cards retain|health loading preserves|health issue cards|all twenty Upcoming cards|Upcoming finishing first|pass3 manual scan'
        browser_env={**os.environ,'CP_DOWNLOAD_COMPLETION_E2E':'1','TEMP':str(R/'tmp'),'TMP':str(R/'tmp'),
                     'CP_PASS3_NONCE':nonce,'CP_PASS3_BASE_URL':base,'CP_PASS3_GROUP':GROUP}
        with (R/f'pass3-browser-{GROUP}.log').open('wb') as output:
            browser=subprocess.Popen(['node',r'C:\Users\dante\Desktop\cinema paradiso\node_modules\@playwright\test\cli.js',
             'test',*files,'--config',str(R/'pass3-playwright.config.cjs'),'--grep',grep],cwd=CODE,env=browser_env,
             stdout=output,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
            deadline=time.monotonic()+180
            while browser.poll() is None:
                if server.poll() is not None:raise RuntimeError('Owned server exited during browser checks')
                if time.monotonic()>deadline:raise TimeoutError('Browser group exceeded 180s')
                time.sleep(.1)
        report=json.loads((R/f'pass3-browser-{GROUP}.json').read_text())
        print(json.dumps({'group':GROUP,'exit_code':browser.returncode,'stats':report['stats']}),flush=True)
        assert browser.returncode==0,'Compiled behavior checks failed'
finally:
    if server and server.poll() is None and 'base' in locals():
        try:
            request=urllib.request.Request(base+'/__sandbox/stop',data=b'{}',headers={'X-Sandbox-Nonce':nonce,'Content-Type':'application/json'})
            with urllib.request.build_opener(NoRedirect).open(request,timeout=3) as response:stopping=json.load(response)
            assert stopping['pid']==server.pid
            server.wait(timeout=7)
            assert server.returncode==0
        except Exception as error:print('Owned fixture graceful cleanup failed: '+repr(error),flush=True)
    for child in [browser,server]:
        if child and child.poll() is None:
            subprocess.run(['taskkill.exe','/PID',str(child.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
