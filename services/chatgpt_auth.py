"""Reusable OAuth registration owner; app startup and inference are separate."""
import base64
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import secrets
import threading
import time
from urllib.parse import parse_qs, urlencode, urlsplit
import uuid
import webbrowser

import jwt

from services.chatgpt_transport import ChatGPTError, ISSUER, RESOURCE, PublicOpenAIHTTP


SCOPES = 'openid profile email offline_access resource.invoke chatgpt.tokens.use.direct'


class OpenAIIdentityVerifier:
    def __init__(self, http):
        self.http = http

    def metadata(self):
        data = self.http.json('GET', ISSUER + '/.well-known/openid-configuration')
        expected = {'issuer': ISSUER, 'authorization_endpoint': ISSUER + '/api/accounts/authorize',
                    'token_endpoint': ISSUER + '/api/accounts/oauth/token',
                    'jwks_uri': ISSUER + '/.well-known/jwks.json'}
        if any(data.get(k) != v for k, v in expected.items()):
            raise ChatGPTError('untrusted_oidc_metadata')
        return data

    def verify(self, token, client_id, nonce=None):
        try:
            metadata = self.metadata()
            # Never select allowed algorithms from an unverified token header.
            algorithms = [a for a in metadata.get('id_token_signing_alg_values_supported', []) if a == 'RS256']
            if not algorithms:
                raise ChatGPTError('unsupported_identity_algorithm')
            header = jwt.get_unverified_header(token)
            keys = self.http.json('GET', metadata['jwks_uri']).get('keys', [])
            matching = [k for k in keys if k.get('kid') == header.get('kid')
                        and k.get('kty') == 'RSA' and k.get('use', 'sig') == 'sig'
                        and k.get('alg', 'RS256') == 'RS256']
            if len(matching) != 1:
                raise ChatGPTError('identity_key_not_found')
            key = jwt.PyJWK.from_dict(matching[0], algorithm='RS256').key
            required = ['exp', 'iss', 'aud', 'sub'] + (['nonce'] if nonce is not None else [])
            claims = jwt.decode(token, key, algorithms=algorithms, audience=client_id, issuer=ISSUER,
                                options={'require': required})
            if (not isinstance(claims['sub'], str) or not claims['sub']
                    or (nonce is not None and not secrets.compare_digest(claims['nonce'], nonce))):
                raise ChatGPTError('invalid_identity')
            return claims
        except ChatGPTError:
            raise
        except Exception:
            raise ChatGPTError('invalid_identity_token') from None


class ChatGPTAuth:
    def __init__(self, credentials, *, http=None, browser_open=webbrowser.open, clock=time.time,
                 on_disconnect=lambda account_id: None):
        self.credentials = credentials
        self.http = http or PublicOpenAIHTTP()
        self.browser_open = browser_open
        self.clock = clock
        self.on_disconnect = on_disconnect
        self.verifier = OpenAIIdentityVerifier(self.http)
        self._attempts = {}
        self._lock = threading.RLock()

    def start(self, *, account_id=None):
        metadata = self.verifier.metadata()
        previous = self.credentials.load(account_id) if account_id else None
        host_id = self.credentials.host_id()
        attempt_id = str(uuid.uuid4())
        owner = self

        class Callback(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass  # Codes/state/hints never enter the HTTP access log.

            def do_GET(self):
                expected_host = '127.0.0.1:' + str(self.server.server_port)
                if self.headers.get('Host') != expected_host or urlsplit(self.path).path != '/auth/callback':
                    self.send_error(400)
                    return
                result = owner.complete_callback(attempt_id, 'http://' + expected_host + self.path)
                body = ('Cinema Paradiso: ' + result['state'] + '. Return to the connection-check page.').encode()
                self.send_response(200 if result['state'] == 'complete' else 400)
                self.send_header('Content-Type', 'text/plain; charset=utf-8')
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Referrer-Policy', 'no-referrer')
                self.end_headers()
                self.wfile.write(body)

        listener = ThreadingHTTPServer(('127.0.0.1', 0), Callback)
        listener.daemon_threads = True
        redirect = 'http://127.0.0.1:' + str(listener.server_port) + '/auth/callback'
        verifier = secrets.token_urlsafe(48)
        attempt = {'state': 'pending', 'expires_at': self.clock() + 600, 'oauth_state': secrets.token_urlsafe(32),
                   'nonce': secrets.token_urlsafe(32), 'verifier': verifier, 'redirect': redirect,
                   'account_id': account_id, 'previous': previous, 'listener': listener}
        with self._lock:
            if any(a['state'] in ('pending', 'exchanging') for a in self._attempts.values()):
                listener.server_close()
                raise ChatGPTError('sign_in_already_pending')
            self._attempts[attempt_id] = attempt
        threading.Thread(target=listener.serve_forever, daemon=True).start()
        timer = threading.Timer(600, self._expire, args=(attempt_id,))
        timer.daemon = True
        attempt['timer'] = timer
        timer.start()
        params = {'client_id': previous['client_id'] if previous else 'dynamic_agent_client',
                  'ext_agent_host_id': host_id, 'response_type': 'code',
                  'redirect_uri': redirect, 'scope': SCOPES, 'resource': RESOURCE,
                  'state': attempt['oauth_state'], 'nonce': attempt['nonce'], 'code_challenge_method': 'S256',
                  'code_challenge': base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')}
        if previous:
            if previous.get('id_token'):
                params['id_token_hint'] = previous['id_token']
            if previous.get('email'):
                params['login_hint'] = previous['email']
        else:
            params['agent_name_hint'] = 'Cinema Paradiso'
        try:
            if self.browser_open(metadata['authorization_endpoint'] + '?' + urlencode(params)) is False:
                raise ChatGPTError('browser_open_failed')
        except Exception:
            self.cancel(attempt_id)
            raise ChatGPTError('browser_open_failed') from None
        return {'attempt_id': attempt_id, 'expires_at': attempt['expires_at']}

    def _close_listener(self, attempt):
        attempt.get('timer') and attempt['timer'].cancel()
        listener = attempt['listener']
        def stop():
            listener.shutdown()
            listener.server_close()
        threading.Thread(target=stop, daemon=True).start()

    def _expire(self, attempt_id):
        with self._lock:
            attempt = self._attempts[attempt_id]
            if attempt['state'] == 'pending':
                attempt['state'] = 'expired'
                self._close_listener(attempt)

    def status(self, attempt_id):
        with self._lock:
            a = self._attempts.get(attempt_id)
            if not a:
                raise ChatGPTError('unknown_attempt')
            if a['state'] == 'pending' and self.clock() >= a['expires_at']:
                self._expire(attempt_id)
            return {k: a[k] for k in ('state', 'expires_at', 'account_id', 'plan_enabled', 'error') if k in a}

    def complete_callback(self, attempt_id, callback_url):
        with self._lock:
            a = self._attempts.get(attempt_id)
            if not a or a['state'] != 'pending':
                return {'state': 'error', 'error': {'code': 'attempt_consumed'}}
            parts = urlsplit(callback_url)
            if parts.scheme + '://' + parts.netloc + parts.path != a['redirect'] or parts.fragment:
                return {'state': 'error', 'error': {'code': 'invalid_callback'}}
            query = parse_qs(parts.query, keep_blank_values=True)
            if any(len(v) != 1 for v in query.values()) or not secrets.compare_digest(query.get('state', [''])[0], a['oauth_state']):
                return {'state': 'error', 'error': {'code': 'invalid_state'}}
            if self.clock() >= a['expires_at']:
                a['state'] = 'expired'
                self._close_listener(a)
                return self.status(attempt_id)
            a['state'] = 'exchanging'
        try:
            if 'error' in query:
                raise ChatGPTError('access_denied' if query['error'][0] == 'access_denied' else 'authorization_error')
            previous = a['previous']
            issued = query.get('client_id', [previous['client_id'] if previous else ''])[0]
            if not issued or issued == 'dynamic_agent_client' or (previous and issued != previous['client_id']):
                raise ChatGPTError('invalid_issued_client')
            if not previous:
                # Registration has already happened at OpenAI. Retain that issued
                # client for an explicit retry even when the code expires. This
                # provisional record has no credentials and cannot become active.
                with self._lock:
                    a['account_id'] = self.credentials.create({'issuer': ISSUER, 'client_id': issued,
                        'subject': None, 'pending_registration': True, 'ext_agent_host_id': self.credentials.host_id()})
            code = query.get('code', [''])[0]
            if not code:
                raise ChatGPTError('missing_authorization_code')
            tokens = self.http.json('POST', ISSUER + '/api/accounts/oauth/token', form={
                'grant_type': 'authorization_code', 'client_id': issued, 'code': code,
                'code_verifier': a['verifier'], 'redirect_uri': a['redirect'], 'resource': RESOURCE})
            identity = self.verifier.verify(tokens.get('id_token', ''), issued, a['nonce'])
            if previous and previous.get('subject') and identity['sub'] != previous['subject']:
                raise ChatGPTError('account_identity_mismatch')
            if tokens.get('token_type', '').lower() != 'bearer' or not tokens.get('access_token'):
                raise ChatGPTError('invalid_token_response')
            scopes = tokens.get('scope', '').split()
            record = {key: tokens.get(key) for key in ('access_token', 'refresh_token', 'id_token')}
            record.update(issuer=ISSUER, subject=identity['sub'], email=identity.get('email', ''), client_id=issued,
                          scopes=scopes, expires_at=self.clock() + int(tokens['expires_in']),
                          ext_agent_host_id=self.credentials.host_id())
            # Returning OAuth and rotating refresh share the same profile lock.
            from contextlib import nullcontext
            profile_lock = self.credentials.refresh_lock(a['account_id']) if a['account_id'] else nullcontext()
            with profile_lock, self._lock:
                if a['state'] != 'exchanging':
                    raise ChatGPTError('cancelled')
                if a['account_id']:
                    self.credentials.replace(a['account_id'], record)
                else:
                    a['account_id'] = self.credentials.create(record)
                a.update(state='complete', plan_enabled='chatgpt.tokens.use.direct' in scopes)
        except Exception as error:
            with self._lock:
                if a['state'] != 'cancelled':
                    a.update(state='denied' if isinstance(error, ChatGPTError) and error.code == 'access_denied' else 'error',
                             error=error.public() if isinstance(error, ChatGPTError) else {'code': 'authentication_failed'})
        finally:
            self._close_listener(a)
            # Retain only safe attempt status, never transient PKCE/nonce/token hints.
            with self._lock:
                for key in ('previous', 'verifier', 'nonce', 'oauth_state'):
                    a.pop(key, None)
        return self.status(attempt_id)

    def access_token(self, account_id):
        with self.credentials.refresh_lock(account_id):
            # Re-read after the cross-process lock: another call may have rotated it.
            record = self.credentials.load(account_id)
            if not record.get('access_token') or record.get('revoking'):
                raise ChatGPTError('account_disconnected')
            if 'chatgpt.tokens.use.direct' not in record.get('scopes', []):
                raise ChatGPTError('consent_required')
            if record['expires_at'] - self.clock() > 60:
                return record['access_token']
            if not record.get('refresh_token'):
                raise ChatGPTError('reauthentication_required')
            try:
                tokens = self.http.json('POST', self.verifier.metadata()['token_endpoint'], form={
                    'grant_type': 'refresh_token', 'client_id': record['client_id'],
                    'refresh_token': record['refresh_token'], 'resource': RESOURCE})
                if tokens.get('token_type', '').lower() != 'bearer' or not tokens.get('access_token'):
                    raise ChatGPTError('invalid_token_response')
                updated = dict(record)
                if tokens.get('id_token'):
                    identity = self.verifier.verify(tokens['id_token'], record['client_id'])
                    if identity['sub'] != record['subject']:
                        raise ChatGPTError('account_identity_mismatch')
                    updated['id_token'] = tokens['id_token']
                updated.update(access_token=tokens['access_token'],
                    refresh_token=tokens.get('refresh_token') or record['refresh_token'],
                    expires_at=self.clock() + int(tokens['expires_in']))
                if updated['expires_at'] <= self.clock():
                    raise ChatGPTError('invalid_token_response')
                if 'scope' in tokens:
                    updated['scopes'] = tokens['scope'].split()
                self.credentials.replace(account_id, updated)
                if 'chatgpt.tokens.use.direct' not in updated['scopes']:
                    raise ChatGPTError('consent_required')
                return updated['access_token']
            except ChatGPTError as error:
                if error.code in ('invalid_grant', 'invalid_token', 'account_identity_mismatch'):
                    self._clear_tokens(account_id, record, error.code)
                raise
            except (ValueError, KeyError, TypeError):
                raise ChatGPTError('invalid_token_response') from None

    def _clear_tokens(self, account_id, record, reason):
        updated = dict(record)
        for key in ('access_token', 'refresh_token', 'id_token'):
            updated.pop(key, None)
        updated.update(disconnected_reason=reason, revoking=False)
        self.credentials.replace(account_id, updated)
        self.on_disconnect(account_id)

    def sign_out(self, account_id):
        confirmed = False
        with self._lock:
            for attempt_id, attempt in self._attempts.items():
                if attempt.get('account_id') == account_id:
                    self.cancel(attempt_id)
        with self.credentials.refresh_lock(account_id):
            record = self.credentials.load(account_id)
            try:
                # Persist the barrier before any remote I/O so other processes stop.
                self.credentials.replace(account_id, {**record, 'revoking': True})
                self.on_disconnect(account_id)
                if record.get('refresh_token'):
                    endpoint = self.verifier.metadata().get('revocation_endpoint')
                    if endpoint != ISSUER + '/api/accounts/oauth/revoke':
                        raise ChatGPTError('untrusted_revocation_endpoint')
                    self.http.json('POST', endpoint, form={'token': record['refresh_token'],
                        'token_type_hint': 'refresh_token', 'client_id': record['client_id']})
                    confirmed = True
            except (ChatGPTError, OSError):
                confirmed = False
            finally:
                self._clear_tokens(account_id, record, 'signed_out')
        return {'account_id': account_id, 'connected': False, 'remote_revocation_confirmed': confirmed,
                'manage_usage_url': 'https://chatgpt.com/settings/usage'}

    def cancel(self, attempt_id):
        with self._lock:
            a = self._attempts[attempt_id]
            if a['state'] in ('pending', 'exchanging'):
                a['state'] = 'cancelled'
                self._close_listener(a)

    def close(self):
        for attempt_id in list(self._attempts):
            self.cancel(attempt_id)
