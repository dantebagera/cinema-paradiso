import tempfile
import unittest

from services.ai_jobs import AIJobStore
from services.ai_provider import AISelection
from services.chatgpt_agent import ChatGPTAgent
from services.chatgpt_skills import load
from services.chatgpt_tools import ChatGPTTools, ToolResult
from services.chatgpt_transport import CompletedResponse, ToolCall


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = AIJobStore(self.temp.name)
        skill = load('F2')
        self.selection = AISelection('chatgpt', 1, 'acct', 'model', skill['id'], '1', skill['hash'], 'F2')
        self.job = self.store.create('F2', self.selection, {'prompt': 'Show playback status'}, 'turn')

    def runner(self, responses, captured):
        store, job_id = self.store, self.job['id']
        class Runner:
            def run(self, selection, **kwargs):
                store.reserve_inference(job_id)
                captured.append(kwargs)
                return responses.pop(0)
        return Runner()

    def test_read_result_reaches_completed_state_and_private_evidence_stays_local(self):
        captured = []
        tools = ChatGPTTools({'playback_status': lambda args, context: ToolResult(
            {'title': 'A Movie', 'path': 'C:\\private\\movie.mkv'}, {'path': 'C:\\private\\movie.mkv'})})
        responses = [CompletedResponse('a', '', [], [ToolCall('c', 'cp_runtime.playback_status', {})]),
                     CompletedResponse('b', 'A Movie is playing.', [], [])]
        result = ChatGPTAgent(self.store, lambda *args: self.runner(responses, captured), tools).run(self.job['id'])
        self.assertEqual(result['state'], 'completed')
        self.assertEqual(result['run_calls'], 2)
        self.assertNotIn('private', str(captured))
        self.assertEqual(result['output']['views'][0]['path'], 'C:\\private\\movie.mkv')

    def test_no_execute_tool_is_advertised_and_preparation_never_writes(self):
        writes = []
        action = {}
        def prepare(args, context):
            action.update(self.store.prepare_action(context.job_id, 'runtime', {}, request_key='prepare'))
            return ToolResult({'action_id': action['action_id'], 'state': 'prepared', 'count': len(args['ids'])})
        tools = ChatGPTTools({'prepare_mark_notifications_read': prepare})
        captured = []
        responses = [CompletedResponse('a', '', [], [ToolCall('c', 'cp_runtime.prepare_mark_notifications_read',
                        {'ids': ['n1'], 'depends_on': []})]), CompletedResponse('b', 'Review this change.', [], [])]
        result = ChatGPTAgent(self.store, lambda *args: self.runner(responses, captured), tools).run(self.job['id'])
        self.assertEqual(result['state'], 'awaiting_confirmation')
        self.assertEqual(writes, [])
        self.assertEqual(result['output']['prepared'][0]['action_id'], action['action_id'])
        self.assertNotIn('execute', str(captured[0]['tools']))

    def test_plain_answer_preserves_private_file_references_for_the_next_turn(self):
        captured = []
        self.store.start_run(self.job['id'], self.job['revision'])
        self.store.save_checkpoint(self.job['id'], 'agent', {'private_refs': {'file_refs': {'opaque': 'C:/private/a.mkv'}},
            'messages': [{'role': 'user', 'content': 'Explain the existing review'}]})
        self.store.finish(self.job['id'], 'completed')
        self.store.append_turn(self.job['session_id'], 'acct', {'role': 'assistant', 'content': 'Earlier review'},
                               constraints={'last_control_job': self.job['id']})
        self.job = self.store.create('F2', self.selection, {'prompt': 'Explain', 'session_id': self.job['session_id']}, 'next')
        result = ChatGPTAgent(self.store, lambda *args: self.runner(
            [CompletedResponse('done', 'Review the file before applying.', [], [])], captured), ChatGPTTools({})).run(self.job['id'])
        self.assertEqual(result['cursor']['agent']['private_refs']['file_refs']['opaque'], 'C:/private/a.mkv')
        self.assertNotIn('private/a', str(captured))

    def test_followup_can_depend_on_the_actual_recorded_action_from_the_previous_turn(self):
        self.store.start_run(self.job['id'], 0)
        previous = self.store.prepare_action(self.job['id'], 'fixture', {}, request_key='previous')
        claimed = self.store.claim_action(previous['action_id'], 0)
        self.store.complete_action(previous['action_id'], claimed['revision'], {'created_id': 'actual-list'}, state='completed')
        self.store.finish(self.job['id'], 'completed')
        self.store.append_turn(self.job['session_id'], 'acct', {'role': 'assistant', 'content': 'Saved the reviewed list'},
            constraints={'last_control_job': self.job['id'], 'control_refs': {'actions': [previous['action_id']]}})
        self.job = self.store.create('F2', self.selection, {'prompt': 'Now do the next step',
            'session_id': self.job['session_id']}, 'follow-up')
        def prepare(args, context):
            action = self.store.prepare_action(context.job_id, 'next-step', {}, request_key='next', depends_on=args['depends_on'])
            return {'action_id': action['action_id'], 'state': 'prepared'}
        responses = [CompletedResponse('a', '', [], [ToolCall('next', 'cp_runtime.prepare_mark_notifications_read',
            {'ids': ['n1'], 'depends_on': [previous['action_id']]})]), CompletedResponse('b', 'Review next step.', [], [])]
        result = ChatGPTAgent(self.store, lambda *args: self.runner(responses, []),
            ChatGPTTools({'prepare_mark_notifications_read': prepare})).run(self.job['id'])
        self.assertEqual(result['state'], 'awaiting_confirmation', result)
        current = next(row for row in result['output']['prepared'] if row['action_id'] != previous['action_id'])
        self.assertEqual(self.store.action(current['action_id'], 'acct')['depends_on'], [previous['action_id']])

    def test_tool_loop_pauses_at_shared_budget_and_continues_without_replaying_prior_reads(self):
        reads = []
        tools = ChatGPTTools({'playback_status': lambda args, context: reads.append(1) or {'playing': False}})
        response = CompletedResponse('a', '', [], [ToolCall('c', 'cp_runtime.playback_status', {})])
        captured = []
        result = ChatGPTAgent(self.store, lambda *args: self.runner([response] * 30, captured), tools).run(self.job['id'])
        self.assertEqual(result['state'], 'paused_budget')
        self.assertEqual(len(reads), 24)
        continued = self.store.continue_job(result['id'], result['revision'], 'continue')
        result = ChatGPTAgent(self.store, lambda *args: self.runner(
            [CompletedResponse('done', 'Playback is stopped.', [], [])], captured), tools).run(continued['id'])
        self.assertEqual(result['state'], 'completed')
        self.assertEqual(len(reads), 24)

