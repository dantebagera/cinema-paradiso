import json
import threading
import unittest
from services.ai_provider import AISelection
from services.chatgpt_skills import load
from services.chatgpt_transport import CompletedResponse, ToolCall, ChatGPTError
from services.chatgpt_matching import MovieIdentity


class IdentityTests(unittest.TestCase):
    def setUp(self):
        skill = load('F3')
        self.selection = AISelection('chatgpt', 1, 'account', 'model', skill['id'], '1', skill['hash'], 'F3')

    def test_targeted_repair_preserves_unicode_and_never_sends_paths_or_folder_names(self):
        payloads = []
        replies = [
            {'matches': [{'id': 'a', 'title': 'Les Misérables', 'year': '2019', 'alternatives': []}]},
            {'matches': [{'id': 'b', 'title': 'المومياء', 'year': '1969', 'alternatives': []}]}]
        class Transport:
            def run(self, selection, **kwargs):
                payloads.append({key: value for key, value in kwargs.items() if key != 'cancel'})
                return CompletedResponse('fake', '', [], [ToolCall('c', 'cp_result.submit', replies.pop(0))])
        result = MovieIdentity(Transport()).identify(self.selection, [
            {'id': 'a', 'filename': 'C:\\private\\Les.Misérables.2019.mkv', 'folder_name': 'private', 'title_hint': 'Les Misérables', 'year_hint': '2019'},
            {'id': 'b', 'filename': 'C:\\private\\المومياء.1969.mkv', 'folder_name': 'private', 'title_hint': 'المومياء', 'year_hint': '1969'}],
            cancel=threading.Event())
        self.assertEqual(set(result['matches']), {'a', 'b'})
        self.assertNotIn('private', json.dumps(payloads, ensure_ascii=False))
        self.assertNotIn('folder_name', json.dumps(payloads))
        repaired = json.loads(payloads[1]['input_items'][0]['content'])
        self.assertEqual([row['id'] for row in repaired['files']], ['b'])
        self.assertIn('المومياء', payloads[1]['input_items'][0]['content'])

    def test_provider_failure_is_not_repaired_or_switched_to_ollama(self):
        calls = []
        class Transport:
            def run(self, *args, **kwargs):
                calls.append(1)
                raise ChatGPTError('plan_not_available')
        with self.assertRaises(ChatGPTError):
            MovieIdentity(Transport()).identify(self.selection, [{'id': 'a', 'filename': 'A.mkv'}], cancel=threading.Event())
        self.assertEqual(len(calls), 1)

    def test_duplicate_and_unknown_ids_cannot_authorize_an_identity(self):
        class Transport:
            def run(self, *args, **kwargs):
                return CompletedResponse('fake', '', [], [ToolCall('c', 'cp_result.submit', {'matches': [
                    {'id': 'a', 'title': 'One', 'year': '2001', 'alternatives': []},
                    {'id': 'a', 'title': 'Two', 'year': '2002', 'alternatives': []},
                    {'id': 'foreign', 'title': 'Foreign', 'year': '2003', 'alternatives': []}]})])
        result = MovieIdentity(Transport()).identify(self.selection, [{'id': 'a', 'filename': 'A.mkv'}], cancel=threading.Event())
        self.assertEqual(result['matches'], {})
        self.assertEqual(set(result['errors']), {'a'})
