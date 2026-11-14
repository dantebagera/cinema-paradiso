"""One guarded Library run. Qualification includes exact owned graceful exit and audit."""
import ctypes,json,os,shutil,subprocess,sys,time,urllib.request,uuid
from pathlib import Path
from pass3_support import new_fixture_root,verify_record
from pass4_audit_contract import cleanup_owned,finish_run
R=Path(__file__).parent;CODE=R/'checkout'

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise RuntimeError('Owned fixture redirected')

def terminate(child):
    # Only Popen objects created here are supplied. No live process lookup/control.
    subprocess.run(['taskkill.exe','/PID',str(child.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW,check=True)
    child.wait(timeout=5)

def main():
    STATE=new_fixture_root(R/'tmp','ui-library-exit-audit');shutil.copytree(CODE/'dist',STATE/'dist')
    nonce=uuid.uuid4().hex
    env={**os.environ,'CP_TEST_MODE':'1','CP_TEST_ROOT':str(STATE),'CP_TEST_QBT_MODE':'embedded',
      'CP_DOWNLOAD_COMPLETION_E2E':'1','CP_PORT':'0','CP_TEST_DIST_DIR':str(STATE/'dist'),
      'CP_ISOLATION_ROOT':str(R),'CP_ISOLATION_ROLE':'ui','PYTHONPATH':os.pathsep.join([str(R),str(CODE),str(Path(sys.prefix)/'Lib/site-packages')]),
      'PYTHONDONTWRITEBYTECODE':'1','TEMP':str(R/'tmp'),'TMP':str(R/'tmp'),
      'LOCALAPPDATA':str(R/'localappdata'),'APPDATA':str(R/'appdata'),'USERPROFILE':str(R/'home'),
      'PYTHONNOUSERSITE':'1','PYTHONIOENCODING':'utf-8','CP_PASS3_NONCE':nonce}
    server=None;browser=None
    try:
        with (R/'pass4-ui-library-server.log').open('xb') as log:
            # Suspend before guard import to ensure a reused PID cannot truncate earlier evidence.
            server=subprocess.Popen([sys._base_executable,str(R/'pass3_ui_server.py')],cwd=CODE,env=env,
              stdout=log,stderr=subprocess.STDOUT,creationflags=0x4|subprocess.CREATE_NO_WINDOW)
            if (R/f'guard-{server.pid}.json').exists():raise RuntimeError('Child PID would overwrite prior audit evidence')
            ntdll=ctypes.WinDLL('ntdll');ntdll.NtResumeProcess.argtypes=[ctypes.c_void_p];ntdll.NtResumeProcess.restype=ctypes.c_long
            if ntdll.NtResumeProcess(int(server._handle))!=0:raise RuntimeError('Cannot resume owned child')
            deadline=time.monotonic()+25;record=None
            while time.monotonic()<deadline:
                if server.poll() is not None:raise RuntimeError('Owned server exited before readiness')
                if (STATE/'ready.json').exists():
                    try:record=json.loads((STATE/'ready.json').read_text());break
                    except json.JSONDecodeError:pass
                time.sleep(.1)
            if record is None:raise RuntimeError('No owned readiness record')
            verify_record(record,pid=server.pid,nonce=nonce,root=STATE)
            base='http://127.0.0.1:'+str(record['port'])
            opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect)
            req=urllib.request.Request(base+'/__sandbox/identity',headers={'X-Sandbox-Nonce':nonce})
            with opener.open(req,timeout=3) as response:identity=json.load(response)
            verify_record(identity,pid=server.pid,nonce=nonce,root=STATE)
            if identity!=record:raise RuntimeError('Identity changed after readiness')
            proof={'child_pid':server.pid,'root':str(STATE),'baseURL':base,'identity_verified_before_browser':True,'record':record}
            (R/'pass4-ownership.json').write_text(json.dumps(proof,indent=2)+'\n')
            browser_env={**env,'CP_PASS3_BASE_URL':base,'CP_PASS3_GROUP':'library-exit-audit'}
            # The inherited interpreter-only guard variables do not affect Node/Chromium.
            with (R/'pass4-browser-library.log').open('xb') as output:
                browser=subprocess.Popen(['node',r'C:\Users\dante\Desktop\cinema paradiso\node_modules\@playwright\test\cli.js',
                  'test','library-search-performance.spec.js','--config',str(R/'pass4-playwright.config.cjs'),
                  '--grep','rapid live typing|stale success|foreground typing|Movie to File|pass3 quiet'],
                  cwd=CODE,env=browser_env,stdout=output,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
                deadline=time.monotonic()+55
                while browser.poll() is None:
                    if server.poll() is not None:raise RuntimeError('Owned server exited during browser checks')
                    if time.monotonic()>deadline:raise TimeoutError('Library browser exceeded 55 seconds')
                    time.sleep(.1)
            report=json.loads((R/'pass4-browser-library.json').read_text())
            def stop():
                if server.poll() is not None:raise RuntimeError('Owned server exited before stop request')
                request=urllib.request.Request(base+'/__sandbox/stop',data=b'{}',headers={'X-Sandbox-Nonce':nonce,'Content-Type':'application/json'})
                with opener.open(request,timeout=3) as response:return json.load(response)
            outcome=finish_run(server=server,browser=browser,stop=stop,report_path=R/f'guard-{server.pid}.json',root=R,
              browser_exit=browser.returncode,report=report,terminate=terminate,outcome_path=R/'pass4-completion.json')
            print(json.dumps({'qualified':outcome['qualified'],'child_pid':server.pid,'stats':report['stats'],
              'server_exit_code':outcome['server_exit_code'],'violations':outcome['audit']['violations'],
              'open':outcome['audit']['audit_counts']['open'],'sqlite3.connect':outcome['audit']['audit_counts']['sqlite3.connect'],'forced_pids':outcome['forced_pids']}),flush=True)
    finally:
        original=sys.exc_info()[1]
        try:
            forced=cleanup_owned([browser,server],terminate)
            (R/'pass4-owned-cleanup.json').write_text(json.dumps({'owned_pids':[c.pid for c in [browser,server] if c],
              'remaining':[c.pid for c in [browser,server] if c and c.poll() is None],'outer_forced_pids':forced,'error':repr(original) if original else None},indent=2)+'\n')
            if forced and original is None:raise RuntimeError('Forced cleanup cannot qualify a run')
        except BaseException:
            if original is None:raise

if __name__=='__main__':main()
