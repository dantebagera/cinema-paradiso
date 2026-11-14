"""Guarded fixture bootstrap: bind once, publish ownership, keep the same listener."""
import json,os,runpy,threading
from pathlib import Path
from flask import Flask,request,abort,jsonify
from werkzeug.serving import make_server
R=Path(__file__).parent;ROOT=Path(os.environ['CP_TEST_ROOT']).resolve()
assert os.stat.__module__=='guard'
assert os.environ['CP_TEST_MODE']=='1' and os.environ['CP_TEST_QBT_MODE']=='embedded'
assert R in ROOT.parents
def run_owned(flask_app,**kwargs):
    import app
    assert app._TEST_MODE is True
    assert R in Path(app._user_data_dir).resolve().parents
    nonce=os.environ['CP_PASS3_NONCE']
    record={'pid':os.getpid(),'nonce':nonce,'root':str(ROOT),'test_mode':True}
    @flask_app.before_request
    def require_private_nonce():
        if request.headers.get('X-Sandbox-Nonce')!=nonce:abort(404)
    @flask_app.get('/__sandbox/identity')
    def identity():
        if request.headers.get('X-Sandbox-Nonce')!=nonce:abort(404)
        return jsonify(record)
    @flask_app.post('/__sandbox/stop')
    def stop():
        threading.Thread(target=server.shutdown,daemon=True).start()
        return jsonify({'owned_server_stopping':True,'pid':os.getpid()})
    # The OS assigns the unused port to this exact server; no probe/rebind gap.
    server=make_server('127.0.0.1',0,flask_app,threaded=True)
    record['port']=server.server_port
    assert record['port'] not in {5000,8686}
    with (ROOT/'ready.json').open('x',encoding='utf-8') as f:json.dump(record,f)
    print(json.dumps({'owned_fixture_ready':record}),flush=True)
    server.serve_forever()
    server.server_close()
Flask.run=run_owned
runpy.run_module('tests.download_completion_server',run_name='__main__')
