"""Public OAuth Responses transport. No CP composition or credentials at import time."""
from dataclasses import dataclass
from contextlib import contextmanager
import codecs
import http.client
import json
import re
import random
import socket
import threading
import time
from urllib.parse import urlencode, urlsplit


ISSUER = 'https://auth.openai.com'
RESOURCE = 'https://api.openai.com/v1'
_URLS = frozenset((ISSUER + '/.well-known/openid-configuration',
                  ISSUER + '/.well-known/jwks.json', ISSUER + '/api/accounts/oauth/token',
                  ISSUER + '/api/accounts/oauth/revoke', RESOURCE + '/models', RESOURCE + '/responses'))
MAX_BYTES = 2 * 1024 * 1024


def safe_code(value):
    value = str(value or '')
    return value if re.fullmatch(r'[a-z][a-z0-9_]{0,95}', value) else 'provider_error'


class ChatGPTError(Exception):
    """Deliberately excludes arbitrary server text, request bodies and credentials."""
    def __init__(self, code, *, status=None, request_id=None, retry_after=None):
        self.code = safe_code(code)
        self.status = status
        self.retry_after = retry_after if isinstance(retry_after, (int, float)) and 0 <= retry_after <= 30 else None
        self.request_id = request_id if re.fullmatch(r'[A-Za-z0-9_-]{1,120}', str(request_id or '')) else None
        super().__init__(self.code)

    def public(self):
        return {k: v for k, v in {'code': self.code, 'http_status': self.status,
                                  'request_id': self.request_id}.items() if v is not None}


class PublicOpenAIHTTP:
    """Owned HTTPS sockets: public endpoints only, no redirects or implicit retry."""
    def __init__(self, *, connection_factory=http.client.HTTPSConnection,
                 clock=time.monotonic, deadline_seconds=180):
        self.connection_factory, self.clock, self.deadline_seconds = connection_factory, clock, deadline_seconds

    @contextmanager
    def _exchange(self, method, url, *, token=None, form=None, payload=None, cancel=None, stream=False):
        if url not in _URLS:
            raise ChatGPTError('endpoint_not_allowed')
        cancel = cancel or threading.Event()
        if cancel.is_set():
            raise ChatGPTError('cancelled')
        parts = urlsplit(url)
        headers = {'Accept': 'text/event-stream' if stream else 'application/json'}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        body = None
        if form is not None:
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
            body = urlencode(form).encode()
        elif payload is not None:
            headers['Content-Type'] = 'application/json'
            body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        connection = self.connection_factory(parts.hostname, timeout=15)
        deadline = self.clock() + self.deadline_seconds
        finished, aborted = threading.Event(), []
        watcher, response = None, None
        try:
            connection.connect()
            native_socket = connection.sock
            native_socket.settimeout(60)
            def monitor():
                while not finished.wait(max(0.001, min(0.1, deadline - self.clock()))):
                    reason = 'cancelled' if cancel.is_set() else 'inference_deadline' if self.clock() >= deadline else None
                    if reason:
                        aborted.append(reason)
                        try:
                            native_socket.shutdown(socket.SHUT_RDWR)
                        except OSError:
                            pass
                        return
            watcher = threading.Thread(target=monitor, daemon=True)
            watcher.start()
            connection.request(method, parts.path, body=body, headers=headers)
            response = connection.getresponse()
            if not 200 <= response.status < 300:
                try:
                    data = json.loads(response.read(65536))
                    error = data.get('error', {})
                    code = (error.get('code') or error.get('type')) if isinstance(error, dict) else error
                except (ValueError, AttributeError):
                    code = 'http_error'
                retry_after = response.getheader('Retry-After')
                try:
                    retry_after = min(30, max(0, float(retry_after))) if retry_after is not None else None
                except ValueError:
                    from email.utils import parsedate_to_datetime
                    try:
                        retry_after = min(30, max(0, parsedate_to_datetime(retry_after).timestamp() - time.time()))
                    except (TypeError, ValueError, OverflowError):
                        retry_after = None
                raise ChatGPTError(code or 'http_error', status=response.status,
                                   request_id=response.getheader('x-request-id'), retry_after=retry_after)
            yield response
            if aborted:
                raise ChatGPTError(aborted[0])
        except ChatGPTError:
            raise
        except (OSError, ValueError, http.client.HTTPException):
            raise ChatGPTError(aborted[0] if aborted else 'network_error') from None
        finally:
            finished.set()
            if response is not None and hasattr(response, 'close'):
                response.close()
            connection.close()
            if watcher:
                watcher.join(timeout=0.2)

    def json(self, method, url, *, token=None, form=None):
        with self._exchange(method, url, token=token, form=form) as response:
            raw = response.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise ChatGPTError('response_too_large')
            try:
                result = json.loads(raw) if raw else {}
            except ValueError:
                raise ChatGPTError('invalid_response') from None
            if not isinstance(result, dict):
                raise ChatGPTError('invalid_response')
            return result

    def stream(self, url, *, payload, token, cancel):
        with self._exchange('POST', url, token=token, payload=payload, stream=True, cancel=cancel) as response:
            # read1 yields available bytes; a fixed-size read could hide streamed output.
            while True:
                if cancel.is_set():
                    raise ChatGPTError('cancelled')
                chunk = response.read1(8192)
                if not chunk:
                    break
                yield chunk


@dataclass(frozen=True)
class ToolCall:
    call_id: str
    name: str
    arguments: dict


@dataclass(frozen=True)
class CompletedResponse:
    response_id: str
    text: str
    output: tuple
    tool_calls: tuple = ()


class ChatGPTTransport:
    _process_slots = threading.BoundedSemaphore(2)

    def __init__(self, access_token, *, http=None, clock=time.monotonic, before_request=lambda: None,
                 retry_wait=lambda delay, cancel: cancel.wait(delay), max_retries=1, inference_slot=None,
                 on_phase=lambda phase: None):
        self.access_token = access_token
        self.http = http or PublicOpenAIHTTP()
        self.clock = clock
        self.before_request = before_request
        self.retry_wait = retry_wait
        self.max_retries = min(1, max(0, max_retries))
        self.inference_slot = inference_slot or self._slot
        self.on_phase = on_phase

    def _slot(self, cancel):
        from contextlib import contextmanager
        @contextmanager
        def acquired():
            while not self._process_slots.acquire(timeout=0.1):
                if cancel.is_set():
                    raise ChatGPTError('cancelled')
            try:
                yield
            finally:
                self._process_slots.release()
        return acquired()

    def list_models(self, selection):
        with self.inference_slot(threading.Event()):
            data = self.http.json('GET', RESOURCE + '/models', token=self.access_token(selection.account_id))
        models = data.get('models')
        if not isinstance(models, list):
            raise ChatGPTError('invalid_model_catalogue')
        return [{'slug': m['slug'], 'display_name': m.get('display_name') or m['slug']}
                for m in models if isinstance(m, dict) and m.get('visibility') == 'list'
                and isinstance(m.get('slug'), str) and m['slug']]

    def run(self, selection, *, instructions, input_items, tools, cancel, on_text_delta=None,
            recover_completed_text=False, admit_request=None, reserve_request=None):
        if cancel.is_set():
            raise ChatGPTError('cancelled')
        if not selection.model or not isinstance(input_items, list) or (recover_completed_text and tools):
            raise ChatGPTError('invalid_request')
        if any(item.get('role') == 'system' for item in input_items):
            raise ChatGPTError('unsupported_system_message')
        payload = {'model': selection.model, 'instructions': instructions, 'input': input_items,
                   'store': False, 'stream': True}
        definitions = {}
        aliases = {}
        for namespace in tools:
            if namespace.get('type') != 'namespace' or not isinstance(namespace.get('tools'), list):
                raise ChatGPTError('invalid_tool_definition')
            for tool in namespace['tools']:
                if tool.get('type') != 'function':
                    raise ChatGPTError('unsupported_tool_type')
                full_name = namespace['name'] + '.' + tool['name']
                if full_name in definitions:
                    raise ChatGPTError('duplicate_tool_definition')
                definitions[full_name] = tool['parameters']
                aliases.setdefault(tool['name'], []).append(full_name)
        if tools:
            payload['tools'] = tools
        self.on_phase('waiting_slot' if recover_completed_text else 'connecting')
        with self.inference_slot(cancel):
            retries = 0 if recover_completed_text else self.max_retries
            for attempt in range(retries + 1):
                if cancel.is_set():
                    raise ChatGPTError('cancelled')
                if attempt or recover_completed_text:
                    self.on_phase('connecting')
                token = self.access_token(selection.account_id)
                if admit_request is not None:
                    admit_request()
                (reserve_request if reserve_request is not None else self.before_request)()
                started_output = [False]
                try:
                    return self._run_once(payload, token, cancel, definitions, aliases, started_output, on_text_delta,
                                          recover_completed_text=recover_completed_text)
                except ChatGPTError as error:
                    if recover_completed_text and started_output[0] and error.code in ('network_error', 'inference_deadline'):
                        raise ChatGPTError('incomplete_output_stream') from None
                    transient = error.code == 'network_error' or error.status in (500, 502, 503, 504)
                    if attempt >= retries or started_output[0] or not transient:
                        raise
                    delay = error.retry_after if error.retry_after is not None else random.uniform(1, 5)
                    if self.retry_wait(delay, cancel):
                        raise ChatGPTError('cancelled')

    def _run_once(self, payload, token, cancel, definitions, aliases, started_output, on_text_delta=None,
                  *, recover_completed_text=False):
        start = self.clock()
        decoder = codecs.getincrementaldecoder('utf-8')()
        pending, total = '', 0
        stream = self.http.stream(RESOURCE + '/responses', payload=payload,
                                  token=token, cancel=cancel)
        streamed = {}
        text_parts = {}
        text_done = {}
        item_calls = {}
        received = False
        try:
            for chunk in stream:
                if cancel.is_set():
                    raise ChatGPTError('cancelled')
                if chunk and not received:
                    received = True
                    self.on_phase('retrieving')
                if self.clock() - start > 180:
                    raise ChatGPTError('inference_deadline')
                total += len(chunk)
                if total > MAX_BYTES:
                    raise ChatGPTError('response_too_large')
                pending += decoder.decode(chunk)
                # Split at blank lines after normalizing CRLF, retaining a split CR.
                pending = pending.replace('\r\n', '\n')
                while '\n\n' in pending:
                    block, pending = pending.split('\n\n', 1)
                    raw = '\n'.join(line[5:].lstrip(' ') for line in block.split('\n') if line.startswith('data:'))
                    if not raw or raw == '[DONE]':
                        continue
                    event = json.loads(raw)
                    kind = event.get('type')
                    response = event.get('response') or {}
                    if kind in ('response.output_text.delta', 'response.output_item.added', 'response.function_call_arguments.delta'):
                        started_output[0] = True
                    if kind == 'response.output_text.delta' and (on_text_delta is not None or recover_completed_text):
                        delta = event.get('delta')
                        if not isinstance(delta, str):
                            raise ChatGPTError('invalid_stream')
                        if recover_completed_text:
                            position = (event.get('output_index', 0), event.get('content_index', 0))
                            if any(type(index) is not int or index < 0 for index in position):
                                raise ChatGPTError('invalid_stream')
                            if position in text_done:
                                raise ChatGPTError('inconsistent_output_text')
                            text_parts.setdefault(position, []).append(delta)
                        if on_text_delta is not None:
                            try:
                                on_text_delta(delta)
                            except ChatGPTError:
                                raise
                            except Exception:
                                raise ChatGPTError('stream_observer_failed') from None
                    if recover_completed_text and kind == 'response.output_text.done':
                        position = (event.get('output_index', 0), event.get('content_index', 0))
                        final_text = event.get('text')
                        if (any(type(index) is not int or index < 0 for index in position)
                                or not isinstance(final_text, str)):
                            raise ChatGPTError('invalid_stream')
                        if (position in text_done or
                                (position in text_parts and ''.join(text_parts[position]) != final_text)):
                            raise ChatGPTError('inconsistent_output_text')
                        text_done[position] = final_text
                    if kind == 'response.output_item.added':
                        item = event.get('item') or {}
                        if item.get('type') == 'function_call':
                            call_id = item['call_id']
                            item_calls[item['id']] = call_id
                            if call_id in streamed:
                                raise ChatGPTError('duplicate_tool_call')
                            streamed[call_id] = ''
                    elif kind in ('response.function_call_arguments.delta', 'response.function_call_arguments.done'):
                        call_id = event.get('call_id') or item_calls.get(event.get('item_id'))
                        if not call_id or call_id not in streamed:
                            raise ChatGPTError('unknown_tool_call')
                        if kind.endswith('.delta'):
                            streamed[call_id] += event['delta']
                        else:
                            arguments = event['arguments']
                            if streamed[call_id] and streamed[call_id] != arguments:
                                raise ChatGPTError('inconsistent_tool_arguments')
                            streamed[call_id] = arguments
                    if kind in ('response.failed', 'response.incomplete', 'error'):
                        error = response.get('error') or event.get('error') or event
                        code = error.get('code')
                        if recover_completed_text:
                            code = code or (response.get('incomplete_details') or {}).get('reason') or error.get('type')
                        raise ChatGPTError(code or kind.replace('.', '_'))
                    if kind == 'response.completed':
                        if response.get('status') != 'completed' or not isinstance(response.get('output'), list):
                            raise ChatGPTError('invalid_terminal_response')
                        text = ''.join(content.get('text', '') for item in response['output']
                                       if item.get('type') == 'message' for content in item.get('content', [])
                                       if content.get('type') == 'output_text')
                        if recover_completed_text:
                            if any(item.get('status') not in (None, 'completed') or
                                   any(content.get('type') == 'refusal' for content in item.get('content', []))
                                   for item in response['output']):
                                raise ChatGPTError('invalid_terminal_response')
                            streamed_text = ''.join(text_done[key] if key in text_done else ''.join(text_parts[key])
                                                    for key in sorted(text_parts.keys() | text_done.keys()))
                            if text and streamed_text and text != streamed_text:
                                raise ChatGPTError('inconsistent_output_text')
                            text = text or streamed_text
                        calls = []
                        for item in response['output']:
                            if item.get('type') != 'function_call':
                                continue
                            name = item['name']
                            if item.get('namespace'):
                                name = item['namespace'] + '.' + name
                            elif name not in definitions and len(aliases.get(name, [])) == 1:
                                name = aliases[name][0]
                            if name not in definitions or item.get('status') not in (None, 'completed'):
                                raise ChatGPTError('unknown_or_incomplete_tool')
                            call_id = item['call_id']
                            if not isinstance(call_id, str) or not call_id or any(c.call_id == call_id for c in calls):
                                raise ChatGPTError('duplicate_tool_call')
                            raw = item.get('arguments') or streamed.get(call_id, '')
                            if call_id in streamed and streamed[call_id] and streamed[call_id] != raw:
                                raise ChatGPTError('inconsistent_tool_arguments')
                            arguments = json.loads(raw)
                            from services.chatgpt_skills import validate_schema
                            validate_schema(definitions[name], arguments)
                            calls.append(ToolCall(call_id, name, arguments))
                        if set(streamed) - {call.call_id for call in calls}:
                            raise ChatGPTError('missing_terminal_tool_call')
                        return CompletedResponse(response.get('id', ''), text, tuple(response['output']), tuple(calls))
            decoder.decode(b'', final=True)
            raise ChatGPTError('missing_terminal_event')
        except (UnicodeError, ValueError, AttributeError, TypeError, KeyError):
            raise ChatGPTError('invalid_stream') from None
        finally:
            close = getattr(stream, 'close', None)
            if close:
                close()
