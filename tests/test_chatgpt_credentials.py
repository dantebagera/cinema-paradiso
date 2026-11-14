import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from services.chatgpt_credentials import CredentialStore, DPAPIProtector


def _rotate_once(root, profile):
    store = CredentialStore(root)
    with store.refresh_lock(profile):
        record = store.load(profile)
        if record['generation'] == 0:
            record['generation'] = 1
            record['access_token'] = 'rotated'
            store.replace(profile, record)
            with (Path(root) / 'rotations.txt').open('a') as output:
                output.write('rotation\n')


class CredentialTests(unittest.TestCase):
    def test_dpapi_roundtrip_is_protected_and_profile_is_opaque(self):
        with tempfile.TemporaryDirectory(dir=os.environ['CP_TEST_ROOT']) as root:
            store = CredentialStore(root)
            host = store.host_id()
            self.assertEqual(CredentialStore(root).host_id(), host)
            self.assertTrue(host.startswith('urn:uuid:'))
            profile = store.create({'client_id': 'issued', 'access_token': 'SENSITIVE_TOKEN'})
            self.assertEqual(store.load(profile)['access_token'], 'SENSITIVE_TOKEN')
            self.assertNotIn(b'SENSITIVE_TOKEN', (Path(root) / 'profiles' / (profile + '.bin')).read_bytes())
            self.assertNotIn('SENSITIVE_TOKEN', json.dumps(store.profiles()))
            with self.assertRaises(ValueError):
                store.load('../outside')

    def test_failed_atomic_replacement_keeps_original(self):
        with tempfile.TemporaryDirectory(dir=os.environ['CP_TEST_ROOT']) as root:
            store = CredentialStore(root)
            profile = store.create({'access_token': 'old'})
            with patch('services.chatgpt_credentials.os.replace', side_effect=OSError('blocked')):
                with self.assertRaises(OSError):
                    store.replace(profile, {'access_token': 'new'})
            self.assertEqual(store.load(profile)['access_token'], 'old')

    def test_same_email_profiles_remain_distinct(self):
        with tempfile.TemporaryDirectory(dir=os.environ['CP_TEST_ROOT']) as root:
            store = CredentialStore(root)
            one = store.create({'email': 'same@example.test', 'client_id': 'one'})
            two = store.create({'email': 'same@example.test', 'client_id': 'two'})
            self.assertNotEqual(one, two)
            self.assertEqual(store.load(one)['client_id'], 'one')
            self.assertEqual(store.load(two)['client_id'], 'two')

    def test_cross_process_rotation_lock_requires_a_fresh_read(self):
        import multiprocessing
        with tempfile.TemporaryDirectory(dir=os.environ['CP_TEST_ROOT']) as root:
            store = CredentialStore(root)
            profile = store.create({'generation': 0, 'access_token': 'old'})
            context = multiprocessing.get_context('spawn')
            processes = [context.Process(target=_rotate_once, args=(root, profile)) for _ in range(2)]
            for process in processes:
                process.start()
            for process in processes:
                process.join(15)
                if process.is_alive():
                    process.terminate()
                    process.join(5)
                    self.fail('Credential refresh lock exceeded its bounded race test')
                self.assertEqual(process.exitcode, 0)
            self.assertEqual((Path(root) / 'rotations.txt').read_text(), 'rotation\n')
            self.assertEqual(store.load(profile)['access_token'], 'rotated')

