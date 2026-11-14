"""GPT identity hints; the existing deterministic match/review owner decides identity."""
import json
import ntpath

from services.chatgpt_skills import load, validate_schema
from services.chatgpt_tools import model_safe
from services.chatgpt_transport import ChatGPTError
from services.smart_match import parse_ai_match_response


class MovieIdentity:
    def __init__(self, transport, *, check_permission=lambda selection: None):
        self.transport, self.check_permission = transport, check_permission

    def identify(self, selection, items, *, cancel):
        skill = load('F3')
        if selection.feature != 'F3' or selection.skill_hash != skill['hash']:
            raise ChatGPTError('skill_changed')
        if not items or len(items) > 8:
            raise ChatGPTError('invalid_identity_batch')
        safe = [{'id': str(row['id']), 'filename': ntpath.basename(str(row.get('filename') or '')),
                 'title_hint': model_safe(str(row.get('title_hint') or '')),
                 'year_hint': str(row.get('year_hint') or '')} for row in items]
        expected = [row['id'] for row in safe]
        if len(set(expected)) != len(expected) or any(not identity for identity in expected):
            raise ChatGPTError('invalid_identity_batch')
        accepted, remaining = {}, expected
        for attempt in range(2):
            self.check_permission(selection)
            payload = {'files': [row for row in safe if row['id'] in remaining]}
            if attempt:
                payload['repair'] = 'Return each supplied id exactly once. This is the only targeted repair.'
            try:
                response = self.transport.run(selection, instructions=skill['instructions'],
                    input_items=[{'role': 'user', 'content': json.dumps(payload, ensure_ascii=False)}],
                    tools=skill['tools'], cancel=cancel)
                calls = [call for call in response.tool_calls if call.name == 'cp_result.submit']
                if len(calls) != 1 or len(response.tool_calls) != 1:
                    raise ChatGPTError('invalid_feature_result')
                validate_schema(skill['tool_schema'], calls[0].arguments)
                parsed = parse_ai_match_response(json.dumps(calls[0].arguments), remaining)
                invalid = set(parsed['missing_ids']) | set(parsed['duplicate_ids'])
                accepted.update({identity: value for identity, value in parsed['matches'].items()
                                 if identity in remaining and identity not in invalid})
                remaining = [identity for identity in expected if identity not in accepted]
            except ValueError:
                pass
            except ChatGPTError as error:
                if error.code not in ('invalid_feature_result', 'invalid_stream', 'inconsistent_tool_arguments',
                                      'unknown_or_incomplete_tool', 'invalid_terminal_response'):
                    raise
            if not remaining:
                break
        return {'matches': accepted, 'errors': {identity: 'AI response invalid after targeted repair; deterministic evidence remains available.'
                                               for identity in remaining}}


class NativeMatchJob:
    """Expose the existing Smart Match preview as a resumable GPT operation."""
    def __init__(self, store, coordinator, *, check_permission=lambda selection: None):
        self.store, self.coordinator, self.check_permission = store, coordinator, check_permission

    def run(self, job_id):
        from services.ai_jobs import AIJobError
        from services.ai_provider import AISelection, AIProviderError
        from services.chatgpt_recommendations import JobCancellation
        job = self.store.snapshot(job_id)
        if job['state'] != 'queued':
            return job
        try:
            job = self.store.start_run(job_id, job['revision'])
            selection = AISelection(**job['selection'])
            self.check_permission(selection)
            owner = self.coordinator()
            state = owner.status()
            if state.get('ai_binding', {}).get('ai_job_id') != job_id:
                raise AIJobError('native_match_job_changed')
            cancel = JobCancellation(self.store, job_id)
            if state['status'] != 'running':
                state = owner.resume(background=False)
            while state['status'] == 'running' and not cancel.is_set():
                self.check_permission(selection)
                state = owner.run_batch()
            if state['status'] == 'paused_budget':
                return self.store.snapshot(job_id)
            if cancel.is_set():
                owner.cancel()
                return self.store.snapshot(job_id)
            return self.store.finish(job_id, 'completed' if state['status'] == 'completed' else 'failed',
                coverage='complete' if state['status'] == 'completed' else 'partial',
                message=state.get('ai_error', ''), output={'native_job_id': state['id'],
                    'processed': state['processed'], 'remaining': state['remaining'],
                    'proposal_count': len(state['proposals']), 'review_required': True})
        except (AIJobError, AIProviderError, ChatGPTError) as error:
            return self.store.finish(job_id, 'failed', message=error.code)
