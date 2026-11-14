"""Adverse completion controls; child/HTTP doubles avoid unrelated real operations."""
import ast,copy,ctypes,importlib.util,io,json,os,subprocess,sys,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
R=Path(__file__).parent
LEGACY='--legacy' in sys.argv
if LEGACY:sys.argv.remove('--legacy')
else:
    from pass4_audit_contract import validate_exit_audit,finish_run

class Child:
    pid=32123
    def __init__(self,exit_code=0,timeout=False):self.returncode=None;self.exit_code=exit_code;self.timeout=timeout
    def poll(self):return self.returncode
    def wait(self,timeout):
        if self.timeout:raise subprocess.TimeoutExpired('owned-test-child',timeout)
        self.returncode=self.exit_code;return self.returncode

def legacy_finish(**kw):
    # Execute the actual prior controller's finally body, with only HTTP/process effects doubled.
    tree=ast.parse((R/'pass3_behavior.py').read_text());block=next(n for n in tree.body if isinstance(n,ast.Try))
    program=ast.fix_missing_locations(ast.Module(body=block.finalbody,type_ignores=[]))
    class Reply:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self):return json.dumps(kw['stop']()).encode()
    request=types.SimpleNamespace(Request=lambda *a,**k:None,build_opener=lambda *a:types.SimpleNamespace(open=lambda *a,**k:Reply()))
    scope={'server':kw['server'],'browser':None,'base':'http://127.0.0.1:49123','nonce':'test','NoRedirect':object,
      'urllib':types.SimpleNamespace(request=request),'json':json,'subprocess':subprocess}
    with patch.object(subprocess,'run',side_effect=lambda *a,**k:kw['terminate'](kw['server'])):
        exec(compile(program,'legacy-finally','exec'),scope)

class ArtifactCase(unittest.TestCase):
    def setUp(self):
        self.work=tempfile.TemporaryDirectory(prefix='pass4-contract-',dir=R/'tmp');self.addCleanup(self.work.cleanup)
        self.root=Path(self.work.name);self.path=self.root/'audit.json'
        self.valid={'pid':32123,'root':str(R),'role':'ui','violations':[],'audit_counts':{'open':12,'sqlite3.connect':3}}
        self.write(self.valid)
    def write(self,value):self.path.write_text(json.dumps(value))
    def validate(self):return validate_exit_audit(self.path,pid=32123,root=R)
    def reject(self,value):
        self.write(value);raw=self.path.read_bytes()
        with self.assertRaises((ValueError,OSError)):self.validate()
        self.assertEqual(self.path.read_bytes(),raw,'Rejected raw artifact must be preserved')

class AuditTests(ArtifactCase):
    def test_browser_report_utf8_with_non_ascii_error(self):
        from pass4_audit_contract import load_browser_report
        value={'errors':[{'message':'╔═خطأ═╗'}],'stats':{'expected':0,'unexpected':5,'skipped':0,'flaky':0}}
        self.path.write_text(json.dumps(value,ensure_ascii=False),encoding='utf-8')
        try:actual=load_browser_report(self.path)
        except UnicodeDecodeError as error:self.fail('UTF-8 report rejected by locale decoder: '+str(error))
        self.assertEqual(actual,value)
    def test_redirected_profile_uses_existing_browser_cache(self):
        from pass4_audit_contract import prepare_browser_environment
        cache=self.root/'existing-browser-cache';exe=cache/'chromium_headless_shell-1228/chrome-headless-shell-win64/chrome-headless-shell.exe'
        exe.parent.mkdir(parents=True);exe.write_text('controlled cache placeholder; not executed')
        env={'LOCALAPPDATA':str(self.root/'localappdata'),'USERPROFILE':str(self.root/'profile')}
        actual=prepare_browser_environment(env,cache=cache)
        self.assertEqual(actual.get('PLAYWRIGHT_BROWSERS_PATH'),str(cache));self.assertEqual(actual['LOCALAPPDATA'],env['LOCALAPPDATA'])
        self.assertNotIn('PLAYWRIGHT_BROWSERS_PATH',env)
        with self.assertRaises(ValueError):prepare_browser_environment(env,cache=self.root/'absent')
    def test_missing_report(self):
        self.path.unlink()
        with self.assertRaises((ValueError,OSError)):self.validate()
    def test_empty_report(self):
        self.path.write_text('')
        with self.assertRaises(ValueError):self.validate()
    def test_malformed_report(self):
        self.path.write_text('{bad')
        with self.assertRaises(ValueError):self.validate()
        self.assertEqual(self.path.read_text(),'{bad')
    def test_invalid_identity_and_shape(self):
        for field,value in [('pid',1),('pid',True),('root',str(self.root)),('root',None),('role','suite'),('violations',{}),('violations',[{'event':'read','value':'forbidden'}])]:
            with self.subTest(field=field,value=value):self.reject({**self.valid,field:value})
        for value in [[],None,{}, {k:v for k,v in self.valid.items() if k!='violations'}]:
            with self.subTest(shape=value):self.reject(value)
    def test_incomplete_workload_counts(self):
        for counts in [None,{},[],{'open':1},{'sqlite3.connect':1},{'open':0,'sqlite3.connect':1},{'open':1,'sqlite3.connect':-1},{'open':True,'sqlite3.connect':1},{'open':'4','sqlite3.connect':1}]:
            with self.subTest(counts=counts):self.reject({**self.valid,'audit_counts':counts})
    def test_valid_normalized_report(self):
        self.write({**self.valid,'root':str(R).upper()+'\\.'})
        self.assertEqual(self.validate()['violations'],[])

class CompletionTests(ArtifactCase):
    def invoke(self,child=None,stop=None,report=None,browser_exit=0):
        child=child or Child();self.forced=[]
        def terminate(p):self.forced.append(p.pid);p.returncode=99
        fn=legacy_finish if LEGACY else finish_run
        return fn(server=child,browser=None,stop=stop or (lambda:{'pid':32123}),
          report_path=self.path,root=R,browser_exit=browser_exit,
          report=report or {'stats':{'expected':5,'unexpected':0,'skipped':0,'flaky':0},'errors':[]},
          terminate=terminate,outcome_path=self.root/'outcome.json')
    def test_shutdown_timeout_is_failure(self):
        with self.assertRaises(subprocess.TimeoutExpired):self.invoke(Child(timeout=True))
        self.assertEqual(self.forced,[32123])
    def test_nonzero_exit_is_failure(self):
        with self.assertRaises(ValueError):self.invoke(Child(exit_code=4))
    def test_wrong_stop_pid_is_failure(self):
        with self.assertRaises(ValueError):self.invoke(stop=lambda:{'pid':32124})
        self.assertEqual(self.forced,[32123])
    def test_missing_audit_is_failure_after_passing_browser(self):
        self.path.unlink()
        with self.assertRaises((ValueError,OSError)):self.invoke()
    def test_violation_is_failure_after_passing_browser(self):
        self.write({**self.valid,'violations':[{'event':'read','value':'blocked'}]})
        with self.assertRaises(ValueError):self.invoke()
    def test_forced_cleanup_cannot_qualify(self):
        with self.assertRaises(subprocess.TimeoutExpired):self.invoke(Child(timeout=True))
        if not LEGACY:
            outcome=json.loads((self.root/'outcome.json').read_text());self.assertFalse(outcome['qualified']);self.assertEqual(outcome['forced_pids'],[32123])
    def test_browser_stats_and_errors_fail(self):
        reports=[{'stats':{'expected':4,'unexpected':0,'skipped':0,'flaky':0},'errors':[]},
          {'stats':{'expected':5,'unexpected':0,'skipped':1,'flaky':0},'errors':[]},
          {'stats':{'expected':5,'unexpected':1,'skipped':0,'flaky':0},'errors':[]},
          {'stats':{'expected':5,'unexpected':0,'skipped':0,'flaky':1},'errors':[]},
          {'stats':{'expected':5,'unexpected':0,'skipped':0,'flaky':0},'errors':[{'message':'error'}]}]
        for report in reports:
            with self.subTest(report=report):
                with self.assertRaises(ValueError):self.invoke(report=report)
        with self.assertRaises(ValueError):self.invoke(browser_exit=1)
    def test_success_requires_normal_exit_and_audit(self):
        result=self.invoke();self.assertTrue(result['qualified']);self.assertEqual(result['server_exit_code'],0);self.assertEqual(self.forced,[])

class FailingWriter:
    def write_text(self,*args,**kwargs):raise OSError('controlled outcome write failure')

class ReportingFailureTests(ArtifactCase):
    def invoke_failing_writer(self,child):
        return finish_run(server=child,browser=None,stop=lambda:{'pid':32123},report_path=self.path,root=R,
          browser_exit=0,report={'stats':{'expected':5,'unexpected':0,'skipped':0,'flaky':0},'errors':[]},
          terminate=lambda p:setattr(p,'returncode',99),outcome_path=FailingWriter())
    def test_outcome_write_failure_preserves_shutdown_timeout(self):
        try:self.invoke_failing_writer(Child(timeout=True))
        except subprocess.TimeoutExpired as error:
            self.assertTrue(any('outcome write failure' in n for n in getattr(error,'__notes__',[])))
        except BaseException as error:self.fail('Original timeout replaced by '+type(error).__name__)
        else:self.fail('Timeout was suppressed')
    def test_outcome_write_failure_rejects_otherwise_successful_run(self):
        with self.assertRaises(OSError):self.invoke_failing_writer(Child())

class Call:
    def __init__(self,fn):self.fn=fn
    def __call__(self,*args):return self.fn(*args)

class BudgetFailureTests(ArtifactCase):
    def run_control(self,kind):
        spec=importlib.util.spec_from_file_location('budget_under_test',R/'budget-pass4.py');budget=importlib.util.module_from_spec(spec);spec.loader.exec_module(budget)
        budget.R=self.root
        ledger=self.root/'bounded-pass-4.json';ledger.write_text('{"batches":[]}')
        def query(*args):
            if kind=='query':return 0
            account=args[2]._obj;account.basic.active_processes=0;account.basic.total_processes=1;account.io.write_bytes=12;return 1
        kernel=types.SimpleNamespace(**{name:Call(fn) for name,fn in {
          'CreateJobObjectW':lambda *a:1,'SetInformationJobObject':lambda *a:1,
          'AssignProcessToJobObject':lambda *a:1,'QueryInformationJobObject':query,
          'TerminateJobObject':lambda *a:1,'CloseHandle':lambda *a:1}.items()})
        ntdll=types.SimpleNamespace(NtResumeProcess=Call(lambda *a:0))
        child=types.SimpleNamespace(_handle=1,returncode=0,poll=lambda:0,wait=lambda **k:0,kill=lambda:None)
        seen=[]
        def launch(*a,**kw):
            seen.append(json.loads(ledger.read_text()))
            if kind=='launch':raise OSError('controlled launch failure')
            return child
        footprints=iter([100,RuntimeError('controlled final footprint failure')] if kind=='footprint' else [100,100])
        def footprint():
            item=next(footprints,100)
            if isinstance(item,Exception):raise item
            return item
        with patch.dict(os.environ,{'CP_TEST_MODE':'1','CP_TEST_QBT_MODE':'embedded','CP_TEST_ROOT':str(self.root)}), \
          patch.object(sys,'argv',['budget-pass4.py','--name','control','--',sys.executable,'-c','pass']), \
          patch.object(budget.ctypes,'WinDLL',side_effect=lambda name,**kw:ntdll if name=='ntdll' else kernel), \
          patch.object(budget.subprocess,'Popen',side_effect=launch),patch.object(budget,'footprint',side_effect=footprint),patch.object(sys,'stdout',io.StringIO()):
            try:budget.main()
            except (OSError,RuntimeError,AssertionError):pass
            state=json.loads(ledger.read_text())
            self.assertTrue(state.get('halted'),'Accounting/launch failure must halt the allowance')
            self.assertEqual(len(state['batches']),1,'Failed batch must be charged')
            self.assertGreater(state['batches'][0]['active_seconds'],0)
            self.assertTrue(state['batches'][0]['stop_reason'])
            self.assertTrue(seen[0].get('in_progress'),'Persist in-progress record before launch')
            self.assertTrue(seen[0].get('halted'),'Unexpected owner exit must leave allowance closed to reuse')
            with self.assertRaises((RuntimeError,AssertionError)):budget.main()
            self.assertEqual(len(seen),1,'Halted allowance must not launch another child')
    def test_accounting_query_failure_is_charged_and_halts(self):self.run_control('query')
    def test_final_footprint_exception_is_charged_and_halts(self):self.run_control('footprint')
    def test_launch_exception_is_charged_and_halts(self):self.run_control('launch')

if __name__=='__main__':
    if LEGACY:
        names=['test_shutdown_timeout_is_failure','test_nonzero_exit_is_failure','test_wrong_stop_pid_is_failure','test_missing_audit_is_failure_after_passing_browser','test_violation_is_failure_after_passing_browser','test_forced_cleanup_cannot_qualify']
        result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(CompletionTests(n) for n in names));raise SystemExit(not result.wasSuccessful())
    unittest.main(verbosity=2)
