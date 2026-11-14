"""Explicit, bounded query assistance; the movie search owner validates every video."""
import json

from services.ai_jobs import AIJobError
from services.ai_provider import AISelection, AIProviderError
from services.chatgpt_recommendations import JobCancellation
from services.chatgpt_skills import load, validate_schema
from services.chatgpt_transport import ChatGPTError
from services.youtube_playlist import YouTubePlaylistError


class YouTubeSearchJob:
    def __init__(self, store, transport_factory, search, *, check_permission=lambda selection: None):
        self.store, self.transport_factory, self.search = store, transport_factory, search
        self.check_permission = check_permission

    def run(self, job_id):
        job = self.store.snapshot(job_id)
        if job['state'] != 'queued':
            return job
        try:
            job = self.store.start_run(job_id, job['revision'])
            selection = AISelection(**job['selection'])
            skill = load('F6')
            if selection.feature != 'F6' or selection.skill_hash != skill['hash']:
                raise ChatGPTError('skill_changed')
            self.check_permission(selection)
            state = self.search.snapshot(job['request']['search_id'])
            evidence = {'movie': state['movie'], 'already_searched': state['queries'][-60:],
                        'candidates': [{'title': row['title'][:300], 'duration_seconds': row['duration_seconds']}
                                       for row in state['candidates'][:30]]}
            cancel = JobCancellation(self.store, job_id)
            if cancel.is_set():
                return self.store.snapshot(job_id)
            transport = self.transport_factory(selection, job_id)
            if hasattr(transport, 'max_retries'):
                transport.max_retries = 0
            response = transport.run(selection, instructions=skill['instructions'],
                input_items=[{'role': 'user', 'content': json.dumps(evidence, ensure_ascii=False)}],
                tools=skill['tools'], cancel=cancel)
            if len(response.tool_calls) != 1 or response.tool_calls[0].name != 'cp_result.submit':
                raise ChatGPTError('invalid_feature_result')
            result = response.tool_calls[0].arguments
            try:
                validate_schema(skill['tool_schema'], result)
            except ValueError:
                raise ChatGPTError('invalid_feature_result') from None
            self.check_permission(selection)
            output = self.search.search_queries(state['search_id'], result['queries'],
                                                lambda: self.store.is_cancelled(job_id))
            if self.store.is_cancelled(job_id):
                return self.store.snapshot(job_id)
            return self.store.finish(job_id, 'completed', coverage='partial',
                                     output={**output, 'explanation': result['explanation']})
        except (AIJobError, AIProviderError, ChatGPTError) as error:
            return self.store.finish(job_id, 'failed', message=error.code)
        except YouTubePlaylistError as error:
            try:
                partial = self.search.snapshot(job['request']['search_id'])
            except YouTubePlaylistError:
                partial = None
            return self.store.finish(job_id, 'failed', coverage='partial', message=str(error), output=partial)
