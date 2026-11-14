import json
import os
import tempfile
import time
import unittest
from urllib.parse import parse_qs, urlencode, urlsplit

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from services.chatgpt_auth import ChatGPTAuth, OpenAIIdentityVerifier
from services.chatgpt_credentials import CredentialStore
from services.chatgpt_transport import ChatGPTError


ISSUER = 'https://auth.openai.com'
METADATA = {'issuer': ISSUER, 'authorization_endpoint': ISSUER + '/api/accounts/authorize',
            'token_endpoint': ISSUER + '/api/accounts/oauth/token',
            'jwks_uri': ISSUER + '/.well-known/jwks.json',
            'revocation_endpoint': ISSUER + '/api/accounts/oauth/revoke',
            'id_token_signing_alg_values_supported': ['RS256']}


class AuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(cls.key.public_key()))
        cls.jwk.update(kid='fixture', use='sig', alg='RS256')

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ['CP_TEST_ROOT'])
        self.addCleanup(self.temp.cleanup)
        self.store = CredentialStore(self.temp.name)
        self.opened = []
        self.posts = []
        self.claim_changes = {}
        self.scope = 'openid profile email offline_access resource.invoke chatgpt.tokens.use.direct'
        self.auth = ChatGPTAuth(self.store, http=self, browser_open=self.opened.append)
        self.addCleanup(self.auth.close)

    def json(self, method, url, *, form=None, **kwargs):
        if url.endswith('openid-configuration'):
            return METADATA
        if url.endswith('jwks.json'):
            return {'keys': [self.jwk]}
        self.posts.append(form)
        claims = {'iss': ISSUER, 'aud': form['client_id'], 'sub': 'account-1',
                  'nonce': self.query['nonce'][0], 'exp': int(time.time()) + 300}
        claims.update(self.claim_changes)
        token = jwt.encode(claims, self.key, algorithm='RS256', headers={'kid': 'fixture'})
        return {'id_token': token, 'access_token': 'SECRET_ACCESS', 'refresh_token': 'SECRET_REFRESH',
                'token_type': 'Bearer', 'expires_in': 3600, 'scope': self.scope}

    def start(self, account_id=None):
        attempt = self.auth.start(account_id=account_id)
        self.query = parse_qs(urlsplit(self.opened[-1]).query)
        return attempt

    def callback(self, attempt, **changes):
        values = {'state': self.query['state'][0], 'code': 'SECRET_CODE', 'client_id': 'oaiapp_fixture'}
        values.update(changes)
        return self.auth.complete_callback(attempt['attempt_id'],
            self.query['redirect_uri'][0] + '?' + urlencode(values))

    def test_registration_pkce_and_verified_identity(self):
        a = self.start()
        self.assertEqual(self.query['client_id'], ['dynamic_agent_client'])
        self.assertEqual(self.query['agent_name_hint'], ['Cinema Paradiso'])
        self.assertEqual(self.query['code_challenge_method'], ['S256'])
        self.assertEqual(self.query['resource'], ['https://api.openai.com/v1'])
        self.assertNotEqual(urlsplit(self.query['redirect_uri'][0]).port, 5000)
        result = self.callback(a)
        self.assertEqual(result['state'], 'complete')
        self.assertTrue(result['plan_enabled'])
        self.assertEqual(self.posts[0]['client_id'], 'oaiapp_fixture')
        self.assertNotIn('SECRET', json.dumps(result))
        self.assertEqual(self.callback(a)['error']['code'], 'attempt_consumed')

    def test_wrong_state_cannot_consume_legitimate_callback(self):
        a = self.start()
        self.assertEqual(self.callback(a, state='wrong')['error']['code'], 'invalid_state')
        self.assertFalse(self.posts)
        self.assertEqual(self.callback(a)['state'], 'complete')

    def test_denial_and_missing_client_do_not_exchange(self):
        for values in [{'error': 'access_denied'}, {'client_id': ''}]:
            a = self.start()
            self.assertIn(self.callback(a, **values)['state'], ['denied', 'error'])
        self.assertFalse(self.posts)

    def test_invalid_identity_never_creates_profile(self):
        for changes in [{'nonce': 'wrong'}, {'aud': 'wrong'}, {'iss': 'wrong'}, {'exp': 1}, {'sub': ''}]:
            with self.subTest(changes=changes):
                self.claim_changes = changes
                a = self.start()
                self.assertEqual(self.callback(a)['state'], 'error')
                self.assertEqual(self.store.profiles(), [])

    def test_signature_and_algorithm_rejected(self):
        verifier = OpenAIIdentityVerifier(self)
        claims = {'iss': ISSUER, 'aud': 'issued', 'sub': 'a', 'nonce': 'n', 'exp': time.time() + 60}
        foreign = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        for token in [jwt.encode(claims, foreign, algorithm='RS256', headers={'kid': 'fixture'}),
                      jwt.encode(claims, 'bad-secret-that-is-at-least-32-bytes', algorithm='HS256', headers={'kid': 'fixture'})]:
            with self.assertRaises(ChatGPTError):
                verifier.verify(token, 'issued', 'n')

    def test_missing_permission_is_signed_in_without_inference(self):
        self.scope = 'openid email'
        result = self.callback(self.start())
        self.assertEqual(result['state'], 'complete')
        self.assertFalse(result['plan_enabled'])
        with self.assertRaises(ChatGPTError):
            self.auth.access_token(result['account_id'])

    def test_wrong_returning_client_preserves_profile(self):
        result = self.callback(self.start())
        original = self.store.load(result['account_id'])
        a = self.start(result['account_id'])
        self.assertNotIn('agent_name_hint', self.query)
        self.assertEqual(self.query['client_id'], ['oaiapp_fixture'])
        self.assertEqual(self.callback(a, client_id='other')['state'], 'error')
        self.assertEqual(self.store.load(result['account_id']), original)

    def test_expired_or_cancelled_attempt_never_exchanges(self):
        a = self.start()
        self.auth.cancel(a['attempt_id'])
        self.assertEqual(self.callback(a)['error']['code'], 'attempt_consumed')
        self.assertFalse(self.posts)

    def test_expired_and_wrong_callback_host_never_exchange(self):
        a = self.start()
        callback = self.query['redirect_uri'][0] + '?' + urlencode({
            'state': self.query['state'][0], 'code': 'SECRET', 'client_id': 'issued'})
        self.assertEqual(self.auth.complete_callback(a['attempt_id'], callback.replace('127.0.0.1', 'localhost'))['error']['code'], 'invalid_callback')
        self.auth.clock = lambda: time.time() + 601
        self.assertEqual(self.auth.complete_callback(a['attempt_id'], callback)['state'], 'expired')
        self.assertFalse(self.posts)

    def test_browser_launch_failure_closes_attempt(self):
        self.auth.browser_open = lambda url: False
        with self.assertRaises(ChatGPTError):
            self.auth.start()
        self.assertFalse(any(a['state'] == 'pending' for a in self.auth._attempts.values()))

    def test_returning_identity_mismatch_does_not_replace_credentials(self):
        result = self.callback(self.start())
        original = self.store.load(result['account_id'])
        self.claim_changes = {'sub': 'different-account'}
        a = self.start(result['account_id'])
        self.assertEqual(self.callback(a)['error']['code'], 'account_identity_mismatch')
        self.assertEqual(self.store.load(result['account_id']), original)

    def test_real_loopback_callback_returns_only_redacted_status(self):
        import requests
        a = self.start()
        url = self.query['redirect_uri'][0]
        response = requests.get(url, params={
            'state': self.query['state'][0], 'code': 'SECRET_CODE', 'client_id': 'oaiapp_fixture'}, timeout=5)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.assertNotIn('SECRET', response.text)
        self.assertEqual(self.auth.status(a['attempt_id'])['state'], 'complete')

    def test_wrong_loopback_host_and_path_never_exchange(self):
        import requests
        a = self.start()
        url = self.query['redirect_uri'][0]
        for destination, headers in [(url, {'Host': 'untrusted.test'}),
                                     (url.replace('/auth/callback', '/wrong'), {})]:
            response = requests.get(destination, headers=headers, timeout=5)
            self.assertEqual(response.status_code, 400)
        self.assertFalse(self.posts)
        self.assertEqual(self.auth.status(a['attempt_id'])['state'], 'pending')

    def test_refresh_is_serialized_and_rotates_the_whole_token_record(self):
        from concurrent.futures import ThreadPoolExecutor
        result = self.callback(self.start())
        profile = result['account_id']
        record = self.store.load(profile)
        record['expires_at'] = time.time() + 1
        self.store.replace(profile, record)
        original = self.json
        refreshes = []
        def refreshing(method, url, *, form=None, **kwargs):
            if form and form.get('grant_type') == 'refresh_token':
                refreshes.append(form)
                payload = original(method, url, form=form, **kwargs)
                payload.update(access_token='ROTATED_ACCESS', refresh_token='ROTATED_REFRESH')
                return payload
            return original(method, url, form=form, **kwargs)
        self.auth.http = type('HTTP', (), {'json': staticmethod(refreshing)})()
        self.auth.verifier.http = self.auth.http
        with ThreadPoolExecutor(max_workers=2) as pool:
            tokens = list(pool.map(lambda _: self.auth.access_token(profile), range(2)))
        self.assertEqual(tokens, ['ROTATED_ACCESS', 'ROTATED_ACCESS'])
        self.assertEqual(len(refreshes), 1)
        self.assertNotIn('scope', refreshes[0])
        self.assertEqual(refreshes[0]['client_id'], 'oaiapp_fixture')
        self.assertEqual(self.store.load(profile)['refresh_token'], 'ROTATED_REFRESH')

    def test_refresh_temporary_failure_preserves_record_terminal_failure_disconnects(self):
        result = self.callback(self.start())
        profile = result['account_id']
        record = self.store.load(profile)
        record['expires_at'] = time.time() + 1
        self.store.replace(profile, record)
        for code, expected_connected in [('network_error', True), ('invalid_grant', False)]:
            self.auth.http = type('HTTP', (), {'json': staticmethod(
                lambda *args, **kwargs: (_ for _ in ()).throw(ChatGPTError(code)))})()
            with self.assertRaises(ChatGPTError):
                self.auth.access_token(profile)
            current = self.store.load(profile)
            self.assertEqual(bool(current.get('access_token')), expected_connected)
            if expected_connected:
                self.assertEqual(current, record)
            self.assertEqual(current['client_id'], 'oaiapp_fixture')

    def test_signout_retains_host_registration_and_other_accounts_even_if_remote_fails(self):
        result = self.callback(self.start())
        profile = result['account_id']
        other = self.store.create({'access_token': 'OTHER', 'client_id': 'other'})
        host = self.store.host_id()
        original = self.json
        def revoke(method, url, **kwargs):
            if url.endswith('/revoke'):
                raise ChatGPTError('network_error')
            return original(method, url, **kwargs)
        self.auth.http = type('HTTP', (), {'json': staticmethod(revoke)})()
        self.auth.verifier.http = self.auth.http
        outcome = self.auth.sign_out(profile)
        self.assertFalse(outcome['remote_revocation_confirmed'])
        self.assertEqual(self.store.host_id(), host)
        self.assertEqual(self.store.load(profile)['client_id'], 'oaiapp_fixture')
        self.assertFalse(self.store.load(profile).get('access_token'))
        self.assertEqual(self.store.load(other)['access_token'], 'OTHER')
        with self.assertRaises(ChatGPTError):
            self.auth.access_token(profile)

    def test_signout_cancels_a_pending_reauthorization(self):
        result = self.callback(self.start())
        pending = self.start(result['account_id'])
        self.auth.sign_out(result['account_id'])
        self.assertEqual(self.callback(pending)['error']['code'], 'attempt_consumed')
        self.assertFalse(self.store.load(result['account_id']).get('access_token'))

    def test_cancellation_during_exchange_cannot_save_credentials(self):
        import threading
        a = self.start()
        entered, release = threading.Event(), threading.Event()
        original = self.json
        def slow(method, url, **kwargs):
            if kwargs.get('form', {}).get('grant_type') == 'authorization_code':
                entered.set()
                if not release.wait(5):
                    raise RuntimeError('Fixture exchange budget exceeded')
            return original(method, url, **kwargs)
        self.auth.http = type('HTTP', (), {'json': staticmethod(slow)})()
        results = []
        worker = threading.Thread(target=lambda: results.append(self.callback(a)))
        worker.start()
        self.assertTrue(entered.wait(5))
        self.auth.cancel(a['attempt_id'])
        release.set()
        worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(results[0]['state'], 'cancelled')
        self.assertEqual(self.store.profiles(), [])

    def test_expired_code_retains_issued_registration_for_an_explicit_retry(self):
        original = self.json
        failed = [False]
        def exchange(method, url, **kwargs):
            if kwargs.get('form', {}).get('grant_type') == 'authorization_code' and not failed[0]:
                failed[0] = True
                raise ChatGPTError('invalid_grant', status=400)
            return original(method, url, **kwargs)
        self.auth.http = type('HTTP', (), {'json': staticmethod(exchange)})()
        error = self.callback(self.start())
        self.assertEqual(error['state'], 'error')
        self.assertTrue(error.get('account_id'))
        self.assertEqual(self.store.profiles(), [])
        self.assertEqual(self.store.load(error['account_id'])['client_id'], 'oaiapp_fixture')
        retry = self.start(error['account_id'])
        self.assertEqual(self.query['client_id'], ['oaiapp_fixture'])
        self.assertNotIn('agent_name_hint', self.query)
        done = self.callback(retry)
        self.assertEqual(done['state'], 'complete')
        self.assertEqual(done['account_id'], error['account_id'])

