"""Task 0 only: isolated user-driven sign-in, model picker, ONE synthetic response.

Run with --root <unique cp-chatgpt-* OS-temp directory>. Never imports CP's app.
Shared service owners implement OAuth, storage and inference; this is a client.
"""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import sys
import tempfile
import threading
from types import SimpleNamespace
from urllib.parse import urlsplit

if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.chatgpt_auth import ChatGPTAuth
from services.chatgpt_credentials import CredentialStore
from services.chatgpt_transport import ChatGPTTransport, ChatGPTError


def validate_root(value):
    supplied = Path(value).absolute()
    root = supplied.resolve()
    temp = Path(tempfile.gettempdir()).resolve()
    if root == temp or not root.is_relative_to(temp) or not root.name.startswith('cp-chatgpt-'):
        raise ValueError('Preflight requires a unique cp-chatgpt-* OS-temp root')
    # Refuse junctions/symlinks anywhere below the OS temp directory.
    current = supplied
    while current != temp and current.is_relative_to(temp):
        if current.is_symlink() or current.is_junction():
            raise ValueError('Preflight root must not contain links or junctions')
        current = current.parent
    return root


class Preflight:
    def __init__(self, root, *, auth=None, transport=None):
        self.root = validate_root(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.auth = auth or ChatGPTAuth(CredentialStore(self.root / 'ai' / 'chatgpt'))
        self.transport = transport or ChatGPTTransport(self.auth.access_token)
        self.attempt_id = None
        self._models = []
        self.last_error = None
        self._lock = threading.RLock()
        self.budget_file = self.root / 'preflight-qualification.json'

    def start(self):
        with self._lock:
            attempt = self.auth.start()
            self.attempt_id = attempt['attempt_id']
            self._models = []
            return attempt

    def status(self):
        state = self.auth.status(self.attempt_id) if self.attempt_id else {'state': 'not_connected'}
        result = {'connection': state, 'models': self._models, 'inference_calls': 0}
        if self.last_error:
            result['last_error'] = self.last_error
        if self.budget_file.exists():
            try:
                result['qualification'] = json.loads(self.budget_file.read_text(encoding='utf-8'))
            except ValueError:
                result['qualification'] = {'state': 'interrupted'}
            # Reserving before HTTP means a crash or uncertain delivery is never replayed.
            result['inference_calls'] = 1
        return result

    def _selection(self, model=''):
        if not self.attempt_id:
            raise ChatGPTError('explicit_connection_required')
        state = self.auth.status(self.attempt_id)
        if state['state'] != 'complete' or not state.get('plan_enabled'):
            raise ChatGPTError('consent_required')
        return SimpleNamespace(account_id=state['account_id'], model=model)

    def models(self):
        with self._lock:
            self._models = self.transport.list_models(self._selection())
            return {'models': self._models}

    def test(self, model):
        with self._lock:
            if self.budget_file.exists():
                raise ChatGPTError('connection_test_budget_used')
            selection = self._selection(model)
            if not any(m['slug'] == model for m in self._models):
                raise ChatGPTError('choose_an_available_model')
            try:
                with self.budget_file.open('x', encoding='utf-8') as output:
                    json.dump({'state': 'running', 'model': model, 'inference_calls': 1}, output)
                    output.flush()
                    os.fsync(output.fileno())
            except FileExistsError:
                raise ChatGPTError('connection_test_budget_used') from None
        result = {'state': 'failed', 'model': model, 'inference_calls': 1}
        try:
            response = self.transport.run(selection, instructions='Return only the exact requested connection-check text.',
                input_items=[{'role': 'user', 'content': 'Say exactly: CP_CONNECTION_OK'}],
                tools=[], cancel=threading.Event())
            if response.text.strip() != 'CP_CONNECTION_OK':
                raise ChatGPTError('unexpected_connection_response')
            result.update(state='passed', response_id=response.response_id)
            return result
        except ChatGPTError as error:
            result['error'] = error.public()
            raise
        except Exception:
            result['error'] = {'code': 'connection_check_failed'}
            raise ChatGPTError('connection_check_failed') from None
        finally:
            # Token-free evidence only. Reservation stays present even if replacement fails.
            temporary = self.budget_file.with_suffix('.tmp')
            temporary.write_text(json.dumps(result, indent=2), encoding='utf-8')
            os.replace(temporary, self.budget_file)


PAGE = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Cinema Paradiso — isolated ChatGPT connection check</title>
<style>body{font:17px system-ui;background:#161820;color:#edf0f6;max-width:820px;margin:70px auto;padding:20px}button,select{font:inherit;padding:12px;margin:8px 8px 8px 0}button{cursor:pointer}pre{white-space:pre-wrap;border:1px solid #555;padding:18px}a{color:#aacaff}small{color:#b9bfce}</style>
<h1>ChatGPT connection check</h1><p>This isolated Cinema Paradiso registration uses your ChatGPT plan. Sign in and review OpenAI’s consent yourself.</p>
<p>Only a fixed synthetic prompt is sent. The connection test permits one inference request. CP’s live settings and libraries are not connected to this page.</p>
<button id="connect">Continue with ChatGPT</button><button id="cancel" disabled>Cancel sign-in</button>
<p>Continue opens OpenAI sign-in in your system’s default browser, outside this page. If it does not appear in front, check your browser on the Windows taskbar. Complete sign-in there, then return here to choose a model.</p>
<p><label>Available model <select id="model" disabled><option value="">Choose a model after sign-in</option></select></label></p>
<button id="test" disabled>Send one connection test</button><p><a href="https://chatgpt.com/settings/usage" target="_blank" rel="noreferrer">Manage ChatGPT usage and app access</a></p>
<pre id="status">Not connected.</pre><small>Temporary registration. Credentials stay encrypted in this diagnostic’s OS-temp directory. This does not activate ChatGPT in the running CP app.</small>
<script>
const csrf = '__CSRF__';
const statusEl=document.querySelector('#status'), model=document.querySelector('#model');
const connect=document.querySelector('#connect'), cancel=document.querySelector('#cancel'), test=document.querySelector('#test');
let loaded=false, busy=false;
async function post(path,body={}) { const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-CP-Preflight':csrf},body:JSON.stringify(body)}); const data=await r.json(); if(!r.ok)throw data; return data; }
function show(data){statusEl.textContent=JSON.stringify(data,null,2);}
async function poll(){
 try { const state=await (await fetch('/status')).json(); show(state);
 const c=state.connection; cancel.disabled=!['pending','exchanging'].includes(c.state);
 connect.disabled=busy||['pending','exchanging','complete'].includes(c.state);
 if(c.state==='complete'&&c.plan_enabled&&!loaded){loaded=true; try {const d=await post('/models'); model.replaceChildren(new Option('Choose an available model','')); for(const m of d.models)model.add(new Option(m.display_name,m.slug)); model.disabled=false;}catch(e){show(e);}}
 test.disabled=busy||state.inference_calls>0||!model.value||c.state!=='complete'||!c.plan_enabled;
 if(state.qualification){show(state);}
 }catch(e){show({error:'Local diagnostic unavailable. Return to the implementation chat.'});}
}
connect.onclick=async()=>{busy=true; connect.disabled=true; try{await post('/start');loaded=false;}catch(e){show(e);}finally{busy=false;}};
cancel.onclick=async()=>{try{await post('/cancel');}catch(e){show(e);}};
model.onchange=poll;
test.onclick=async()=>{busy=true;test.disabled=true;try{show({state:'running',model:model.value});show(await post('/test',{model:model.value}));}catch(e){show(e);}finally{busy=false;await poll();}};
setInterval(poll,1500); poll();
</script></html>'''


def make_server(preflight):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def host_allowed(self):
            return self.headers.get('Host') == '127.0.0.1:' + str(self.server.server_port)

        def send(self, status, value, *, html=False):
            body = value.encode('utf-8') if html else json.dumps(value).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'text/html; charset=utf-8' if html else 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if not self.host_allowed():
                self.send(403, {'error': {'code': 'invalid_host'}})
            elif self.path == '/':
                self.send(200, PAGE.replace('__CSRF__', self.server.csrf), html=True)
            elif self.path == '/status':
                self.send(200, preflight.status())
            else:
                self.send(404, {})

        def do_POST(self):
            origin = 'http://127.0.0.1:' + str(self.server.server_port)
            if (not self.host_allowed() or self.headers.get('Origin') not in (None, origin)
                    or not secrets.compare_digest(self.headers.get('X-CP-Preflight', ''), self.server.csrf)):
                self.send(403, {'error': {'code': 'invalid_local_request'}})
                return
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if self.headers.get('Content-Type') != 'application/json' or not 1 <= size <= 4096:
                    raise ChatGPTError('invalid_json_request')
                body = json.loads(self.rfile.read(size))
                allowed = {'model'} if self.path == '/test' else set()
                if not isinstance(body, dict) or set(body) - allowed:
                    raise ChatGPTError('unknown_fields')
                if self.path == '/start':
                    result = preflight.start()
                elif self.path == '/models':
                    result = preflight.models()
                elif self.path == '/test':
                    result = preflight.test(body.get('model'))
                elif self.path == '/cancel' and preflight.attempt_id:
                    preflight.auth.cancel(preflight.attempt_id)
                    result = preflight.status()
                else:
                    raise ChatGPTError('unknown_action')
                preflight.last_error = None
                self.send(200, result)
            except ChatGPTError as error:
                preflight.last_error = error.public()
                self.send(400, {'error': error.public()})
            except Exception:
                preflight.last_error = {'code': 'preflight_request_failed'}
                self.send(400, {'error': {'code': 'preflight_request_failed'}})

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.daemon_threads = True
    server.csrf = secrets.token_urlsafe(32)
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True)
    args = parser.parse_args()
    preflight = Preflight(args.root)
    server = make_server(preflight)
    url = 'http://127.0.0.1:' + str(server.server_port) + '/'
    (preflight.root / 'preflight-server.json').write_text(json.dumps({'pid': os.getpid(), 'url': url}), encoding='utf-8')
    print('Isolated connection page: ' + url, flush=True)
    print('Waiting for Dante to click Continue with ChatGPT. No inference runs automatically.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        preflight.auth.close()
        server.server_close()


if __name__ == '__main__':
    main()
