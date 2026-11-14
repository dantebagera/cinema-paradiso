import json
import io
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from services.chatgpt_transport import ChatGPTTransport, ChatGPTError, PublicOpenAIHTTP


def fixture_http(status, payload, headers=None):
    calls = []
    raw = io.BytesIO(json.dumps(payload).encode() if payload is not None else b'')
    response = SimpleNamespace(status=status, getheader=lambda key: (headers or {}).get(key),
                               read=raw.read, read1=raw.read1)
    connection = SimpleNamespace(sock=SimpleNamespace(settimeout=lambda seconds: None, shutdown=lambda mode: None),
        connect=lambda: None, close=lambda: None, getresponse=lambda: response,
        request=lambda method, path, body=None, headers=None: calls.append((method, path, body, headers)))
    return PublicOpenAIHTTP(connection_factory=lambda host, timeout: connection), calls


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.events = []
        self.transport = ChatGPTTransport(lambda account: 'SECRET', http=self)
        self.selection = SimpleNamespace(account_id='fixture', model='listed-model')

    def stream(self, url, *, payload, token, cancel):
        self.calls.append((url, payload))
        for item in self.events:
            data = ('data: ' + json.dumps(item, ensure_ascii=False) + '\r\n\r\n').encode()
            for byte in data:
                yield bytes([byte])

    def json(self, method, url, **kwargs):
        return {'models': [{'slug': 'b', 'display_name': 'B', 'visibility': 'list'},
                           {'slug': 'hidden', 'visibility': 'hide'},
                           {'slug': 'a', 'display_name': 'A', 'visibility': 'list'}]}

    def run_response(self, **options):
        return self.transport.run(self.selection, instructions='Fixed synthetic check.',
            input_items=[{'role': 'user', 'content': 'Say CP_CONNECTION_OK'}], tools=[], cancel=threading.Event(), **options)

    def test_progress_distinguishes_waiting_for_connection_from_received_bytes(self):
        phases = []
        self.transport.on_phase = phases.append
        def stream(*args, **kwargs):
            self.assertEqual(phases, ['connecting'])
            yield b'data: {"type":"response.created"}\n\n'
            self.assertEqual(phases, ['connecting', 'retrieving'])
            yield b'data: {"type":"response.completed","response":{"status":"completed","output":[]}}\n\n'
        self.transport.http = SimpleNamespace(stream=stream)
        self.run_response()
        self.assertEqual(phases, ['connecting', 'retrieving'])

    def test_optional_text_observer_receives_fragments_before_terminal_without_changing_payload(self):
        seen = []
        self.events = [{'type': 'response.output_text.delta', 'delta': 'لم'},
                       {'type': 'response.output_text.delta', 'delta': 'عي'},
                       {'type': 'response.completed', 'response': {'id': 'resp_fixture', 'status': 'completed',
                        'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': 'لمعي'}]}]}}]
        result = self.run_response(on_text_delta=seen.append)
        self.assertEqual(seen, ['لم', 'عي'])
        self.assertEqual(result.text, 'لمعي')
        self.assertNotIn('on_text_delta', self.calls[0][1])

    def test_observer_output_never_turns_a_failed_terminal_into_success(self):
        seen = []
        self.events = [{'type': 'response.output_text.delta', 'delta': 'candidate'},
                       {'type': 'response.failed', 'response': {'error': {'code': 'network_error'}}}]
        with self.assertRaises(ChatGPTError):
            self.run_response(on_text_delta=seen.append)
        self.assertEqual(seen, ['candidate'])

    def test_public_request_and_fragmented_utf8_terminal_result(self):
        self.events = [{'type': 'response.output_text.delta', 'delta': 'لمعي'},
                       {'type': 'response.completed', 'response': {'id': 'resp_fixture', 'status': 'completed',
                        'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': 'لمعي'}]}]}}]
        result = self.run_response()
        self.assertEqual(result.text, 'لمعي')
        url, payload = self.calls[0]
        self.assertEqual(url, 'https://api.openai.com/v1/responses')
        self.assertEqual(set(payload), {'model', 'instructions', 'input', 'store', 'stream'})
        self.assertIs(payload['store'], False)
        self.assertIs(payload['stream'], True)

    def test_errors_after_text_and_missing_terminal_are_failures(self):
        for terminal in [None, {'type': 'response.incomplete', 'response': {}},
                         {'type': 'response.failed', 'response': {'error': {'code': 'subscription_sharing_usage_limit_exceeded', 'message': 'SECRET'}}}]:
            with self.subTest(terminal=terminal):
                self.events = [{'type': 'response.output_text.delta', 'delta': 'CP_CONNECTION_OK'}]
                if terminal:
                    self.events.append(terminal)
                with self.assertRaises(ChatGPTError) as caught:
                    self.run_response()
                self.assertNotIn('SECRET', str(caught.exception))

    def test_models_are_account_specific_and_keep_order(self):
        self.assertEqual([m['slug'] for m in self.transport.list_models(self.selection)], ['b', 'a'])

    def test_cancellation_is_not_success(self):
        cancel = threading.Event()
        cancel.set()
        with self.assertRaises(ChatGPTError):
            self.transport.run(self.selection, instructions='check', input_items=[], tools=[], cancel=cancel)
        self.assertFalse(self.calls)

    def test_http_refuses_private_or_untrusted_destinations(self):
        http = PublicOpenAIHTTP()
        for url in ['https://chatgpt.com/backend-api/codex', 'https://evil.test/v1/responses',
                    'https://api.openai.com/v1/responses?token=SECRET', 'http://api.openai.com/v1/models']:
            with self.assertRaises(ChatGPTError):
                http.json('GET', url)

    def test_http_error_preserves_code_status_request_id_without_secrets(self):
        for status in (401, 403, 429):
            with self.subTest(status=status):
                http, calls = fixture_http(status, {'error': {
                    'code': 'subscription_sharing_usage_unavailable',
                    'message': 'SECRET_ACCESS https://example.test/?token=SECRET'}}, {'x-request-id': 'req_fixture'})
                with self.assertRaises(ChatGPTError) as caught:
                    http.json('GET', 'https://api.openai.com/v1/models', token='SECRET_ACCESS')
                public = caught.exception.public()
                self.assertEqual(public, {'code': 'subscription_sharing_usage_unavailable',
                                          'http_status': status, 'request_id': 'req_fixture'})
                self.assertNotIn('SECRET', json.dumps(public))
                self.assertEqual(len(calls), 1)
                self.assertEqual(calls[0][3]['Authorization'], 'Bearer SECRET_ACCESS')
                self.assertEqual(calls[0][1], '/v1/models')

    def test_namespaced_tool_arguments_are_complete_and_validated_after_terminal(self):
        tool = {'type': 'namespace', 'name': 'cp_result', 'description': 'Synthetic final result', 'tools': [
            {'type': 'function', 'name': 'submit', 'description': 'Return an ID',
             'parameters': {'type': 'object', 'properties': {'tmdb_id': {'type': 'integer', 'minimum': 0}},
                            'required': ['tmdb_id'], 'additionalProperties': False}, 'strict': True}]}
        output = {'type': 'function_call', 'id': 'item_a', 'call_id': 'call_a', 'namespace': 'cp_result',
                  'name': 'submit', 'arguments': '{"tmdb_id":123}', 'status': 'completed'}
        self.events = [
            {'type': 'response.output_item.added', 'item': {**output, 'arguments': ''}},
            {'type': 'response.function_call_arguments.delta', 'item_id': 'item_a', 'delta': '{"tmdb_'},
            {'type': 'response.function_call_arguments.delta', 'item_id': 'item_a', 'delta': 'id":123}'},
            {'type': 'response.completed', 'response': {'status': 'completed', 'id': 'resp_test', 'output': [output]}}]
        result = self.transport.run(self.selection, instructions='Synthetic', input_items=[], tools=[tool], cancel=threading.Event())
        self.assertEqual(result.tool_calls[0].arguments, {'tmdb_id': 123})
        self.assertEqual(result.tool_calls[0].name, 'cp_result.submit')
        output['arguments'] = '{"tmdb_id":123,"apply":true}'
        with self.assertRaises(ChatGPTError):
            self.transport.run(self.selection, instructions='Synthetic', input_items=[], tools=[tool], cancel=threading.Event())

    def test_transient_retry_is_bounded_counted_and_never_replays_started_output(self):
        attempts = []
        class HTTP:
            def stream(inner, *args, **kwargs):
                attempts.append(1)
                raise ChatGPTError('network_error')
                yield b''
        counted = []
        transport = ChatGPTTransport(lambda account: 'fixture', http=HTTP(),
            before_request=lambda: counted.append(1), retry_wait=lambda delay, cancel: False)
        with self.assertRaises(ChatGPTError):
            transport.run(self.selection, instructions='check', input_items=[], tools=[], cancel=threading.Event())
        self.assertEqual(len(attempts), 2)
        self.assertEqual(len(counted), 2)
        attempts.clear()
        class PartialHTTP:
            def stream(inner, *args, **kwargs):
                attempts.append(1)
                yield b'data: {"type":"response.output_text.delta","delta":"partial"}\n\n'
                raise ChatGPTError('network_error')
        transport.http = PartialHTTP()
        with self.assertRaises(ChatGPTError):
            transport.run(self.selection, instructions='check', input_items=[], tools=[], cancel=threading.Event())
        self.assertEqual(len(attempts), 1)

    def test_http_redirect_is_not_followed(self):
        http, calls = fixture_http(302, None, {'Location': 'https://untrusted.test/'})
        with self.assertRaises(ChatGPTError) as caught:
            http.json('GET', 'https://api.openai.com/v1/models', token='SECRET')
        self.assertEqual(caught.exception.status, 302)
        self.assertEqual(len(calls), 1)

    def test_http_deadline_interrupts_a_silent_stream_without_waiting_for_idle_timeout(self):
        stopped = threading.Event()
        def silent_read(size):
            if not stopped.wait(2):
                self.fail('Native HTTP deadline did not interrupt the blocked read')
            raise OSError('synthetic socket shutdown')
        response = SimpleNamespace(status=200, getheader=lambda key: None, read1=silent_read)
        connection = SimpleNamespace(sock=SimpleNamespace(settimeout=lambda seconds: None,
            shutdown=lambda mode: stopped.set()), connect=lambda: None, close=lambda: None,
            request=lambda *args, **kwargs: None, getresponse=lambda: response)
        http = PublicOpenAIHTTP(connection_factory=lambda host, timeout: connection, deadline_seconds=0.05)
        with self.assertRaises(ChatGPTError) as caught:
            list(http.stream('https://api.openai.com/v1/responses', payload={}, token='fixture', cancel=threading.Event()))
        self.assertEqual(caught.exception.code, 'inference_deadline')
