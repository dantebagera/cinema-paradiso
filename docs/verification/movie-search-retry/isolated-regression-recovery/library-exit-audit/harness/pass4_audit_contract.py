"""Single strict qualification owner for the disposable Library exit audit."""
import json,os,sys
from pathlib import Path

def require(condition,message):
    if not condition:raise ValueError(message)

def load_browser_report(path):
    return json.loads(path.read_text(encoding='utf-8'))

def prepare_browser_environment(env,*,cache):
    executable=cache/'chromium_headless_shell-1228/chrome-headless-shell-win64/chrome-headless-shell.exe'
    require(executable.is_file(),'Existing Chromium runtime missing; installation is not authorized')
    return {**env,'PLAYWRIGHT_BROWSERS_PATH':str(cache)}

def validate_exit_audit(report_path:Path,*,pid:int,root:Path)->dict:
    report=json.loads(report_path.read_text(encoding='utf-8'))
    require(isinstance(report,dict),'Audit must be a JSON object')
    require(type(report.get('pid')) is int and report['pid']==pid,'Audit child PID mismatch')
    require(report.get('role')=='ui','Audit role mismatch')
    raw_root=report.get('root')
    require(isinstance(raw_root,str) and bool(raw_root),'Audit isolation root missing')
    require(os.path.normcase(os.path.abspath(raw_root))==os.path.normcase(os.path.abspath(root)),'Audit isolation root mismatch')
    violations=report.get('violations')
    require(isinstance(violations,list) and not violations,'Audit violations missing, invalid or nonempty')
    counts=report.get('audit_counts')
    require(isinstance(counts,dict) and bool(counts),'Audit counts missing or empty')
    for event in ['open','sqlite3.connect']:
        require(type(counts.get(event)) is int and counts[event]>0,'Missing positive workload counter: '+event)
    return report

def cleanup_owned(children,terminate):
    forced=[]
    for child in children:
        if child is not None and child.poll() is None:
            forced.append(child.pid);terminate(child)
            require(child.poll() is not None,'Owned child survived failure cleanup')
    return forced

def finish_run(*,server,browser,stop,report_path,root,browser_exit,report,terminate,outcome_path):
    outcome={'qualified':False,'child_pid':server.pid,'forced_pids':[]}
    try:
        require(browser_exit==0,'Browser exit code must be zero')
        require(isinstance(report,dict),'Browser report missing')
        stats=report.get('stats',{})
        require(isinstance(stats,dict) and all(type(stats.get(k)) is int and stats[k]==v for k,v in {'expected':5,'unexpected':0,'skipped':0,'flaky':0}.items()),'Exactly five passing browser cases required')
        require(report.get('errors')==[],'Browser report-level errors present or missing')
        outcome['browser_stats']=stats
        require(server.poll() is None,'Owned child exited before private stop')
        stopping=stop()
        require(isinstance(stopping,dict) and type(stopping.get('pid')) is int and stopping['pid']==server.pid,'Private stop PID mismatch')
        server.wait(timeout=7)
        outcome['server_exit_code']=server.returncode
        require(server.returncode==0 and server.poll()==0,'Owned server did not exit normally with code zero')
        outcome['audit']=validate_exit_audit(report_path,pid=server.pid,root=root)
        outcome['qualified']=True
        return outcome
    except BaseException as error:
        outcome['error']=repr(error)
        raise
    finally:
        original=sys.exc_info()[1]
        try:
            outcome['forced_pids']=cleanup_owned([browser,server],terminate)
            if outcome['forced_pids']:
                outcome['qualified']=False
                if original is None:raise ValueError('Forced cleanup cannot qualify a run')
        except BaseException as cleanup_error:
            outcome['qualified']=False;outcome['cleanup_error']=repr(cleanup_error)
            if original is None:raise
        finally:
            pending=sys.exc_info()[1]
            try:outcome_path.write_text(json.dumps(outcome,indent=2)+'\n')
            except BaseException as report_error:
                if pending is None:raise
                pending.add_note('Secondary outcome write failure: '+repr(report_error))
