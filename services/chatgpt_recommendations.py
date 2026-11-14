"""Bounded curator orchestration; metadata and filter owners validate every result."""
import json
import threading
import time
from contextlib import nullcontext

from services.advanced_search import normalize_query
from services.ai_jobs import AIJobError
from services.ai_provider import AISelection, AIProviderError, canonical_count
from services.ai_catalog import AICatalogError
from services.chatgpt_skills import load, validate_schema
from services.chatgpt_transport import ChatGPTError
from services.chatgpt_recommendation_stream import CandidateBatch


def target_reached(count, target):
    text = str(count)
    return (len(text), text) >= (len(target), target)


def parse_result(response, skill, *, scope_fixed=False):
    """The F1 output boundary: names/years, with constraints once only."""
    try:
        if response.tool_calls:
            raise ValueError('Result cannot also call a tool')
        result = json.loads(response.text)
        validate_schema(skill['continuation_schema'] if scope_fixed else skill['result_schema'], result)
        return result
    except (ValueError, TypeError):
        raise ChatGPTError('invalid_feature_result') from None


class JobCancellation:
    def __init__(self, store, job_id):
        self.store, self.job_id = store, job_id
        self._checked, self._cancelled = 0, False

    def is_set(self):
        if time.monotonic() - self._checked >= 0.25:
            self._cancelled = self.store.is_cancelled(self.job_id)
            self._checked = time.monotonic()
        return self._cancelled

    def wait(self, seconds):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if self.is_set():
                return True
            threading.Event().wait(min(0.1, max(0, deadline - time.monotonic())))
        return self.is_set()


class Recommender:
    def __init__(self, store, transport_factory, resolve_candidate, *, catalogue, scope_context=lambda: {},
                 validate_identities=lambda query, context: None, check_permission=lambda selection: None,
                 measure_phase=lambda phase: nullcontext()):
        self.store, self.transport_factory = store, transport_factory
        self.resolve_candidate, self.catalogue = resolve_candidate, catalogue
        self.scope_context, self.validate_identities, self.check_permission = scope_context, validate_identities, check_permission
        self.measure_phase = measure_phase

    def run(self, job_id):
        job = self.store.snapshot(job_id)
        if job['state'] != 'queued':
            return job
        try:
            job = self.store.start_run(job_id, job['revision'])
        except AIJobError:
            return self.store.snapshot(job_id)
        selection = AISelection(**job['selection'])
        report_progress = self.store.progress_reporter(job_id)
        cancel = JobCancellation(self.store, job_id)
        skill = load('F1')
        if skill['hash'] != selection.skill_hash:
            return self.store.finish(job_id, 'failed', message='skill_changed; start a new request')
        self.store.record_job_turn(job_id)
        session = self.store.session(job['session_id'], selection.account_id)
        previous = []
        last_job = session['constraints'].get('last_recommendation_job')
        if last_job and last_job != job_id:
            previous = self.store.snapshot(last_job)['results']
        try:
            context = self.scope_context()
        except (AICatalogError, AIProviderError, ChatGPTError) as error:
            return self.store.finish(job_id, 'failed', message=error.code)
        except Exception:
            return self.store.finish(job_id, 'failed', message='metadata_unavailable')
        identity_context = session['constraints'].get('identity_context') or {'person': [], 'company': []}
        entity_cache = {}
        transport = self.transport_factory(selection, job_id)
        followup_items = []
        repair = 0
        try:
            while True:
                self.check_permission(selection)
                job = self.store.snapshot(job_id)
                if job['state'] != 'running':
                    return job
                if target_reached(job['accepted_count'], job['requested_count']):
                    return self._finish(job, 'completed', 'Requested verified target reached.')
                scope = job['cursor'].get('scope') or session['constraints'].get('scope')
                # Ordinary fifty-film requests fit one response; total targets
                # remain unrestricted and larger requests still resume in batches.
                remaining = 50
                if len(job['requested_count']) <= len(str(job['accepted_count'] + 50)):
                    remaining = min(50, int(job['requested_count']) - job['accepted_count'])
                content = {'request': job['request']['prompt'], 'requested_target': job['requested_count'],
                    'count_source': job['request'].get('count_source', 'explicit'), 'batch_target': remaining,
                    'accepted_count': job['accepted_count'], 'existing_scope': scope,
                    'scope_is_fixed': bool(job['cursor'].get('scope_fixed')),
                    'rejected_candidates': job['cursor'].get('recommendation_rejections', []),
                    'initial_request': session['constraints'].get('initial_request'), 'recent_turns': session['turns'],
                    'previous_results': [{key: row.get(key) for key in ('tmdb_id', 'title', 'year')} for row in previous],
                    'already_accepted_examples': [{key: row.get(key) for key in ('tmdb_id', 'title', 'year')}
                                                  for row in self.store.recent_results(job_id, limit=200)],
                    'catalogue_context': context}
                inputs = followup_items or [{'role': 'user', 'content': json.dumps(content, ensure_ascii=False)}]
                item_schema = skill['result_schema']['properties']['recommendations']['items']
                with CandidateBatch(self.resolve_candidate, cancel, item_schema) as lookups:
                    try:
                        tools = skill['continuation_tools'] if job['cursor'].get('scope_fixed') else skill['tools']
                        response = transport.run(selection, instructions=skill['instructions'], input_items=inputs,
                                                 tools=tools, cancel=cancel, on_text_delta=lookups.feed)
                        if any(call.name == 'cp_control.open' for call in response.tool_calls):
                            if len(response.tool_calls) != 1:
                                raise ChatGPTError('invalid_feature_result')
                            return self.store.finish(job_id, 'awaiting_clarification',
                                message='Open AI Control to retrieve and review this factual catalogue request.',
                                output={'handoff': 'ai-control', 'prompt': job['request']['prompt']})
                        tool_outputs = []
                        for call in response.tool_calls:
                            if call.name == 'cp_catalog.resolve_people':
                                result = self.catalogue.resolve_people(call.arguments['text'], call.arguments['role'], page=call.arguments['page'])
                                identity_context['person'].extend(result['candidates'])
                                self.store.update_constraints(job['session_id'], selection.account_id, {'identity_context': identity_context})
                                tool_outputs.append({'type': 'function_call_output', 'call_id': call.call_id, 'output': json.dumps(result)})
                            elif call.name == 'cp_catalog.resolve_companies':
                                result = self.catalogue.resolve_company(call.arguments['text'], page=call.arguments['page'])
                                identity_context['company'].extend(result['candidates'])
                                self.store.update_constraints(job['session_id'], selection.account_id, {'identity_context': identity_context})
                                tool_outputs.append({'type': 'function_call_output', 'call_id': call.call_id, 'output': json.dumps(result)})
                            else:
                                raise ChatGPTError('invalid_feature_result')
                        if tool_outputs:
                            followup_items = inputs + list(response.output) + tool_outputs
                            continue
                        self.check_permission(selection)
                        result = parse_result(response, skill, scope_fixed=bool(job['cursor'].get('scope_fixed')))
                        if not job['cursor'].get('scope_fixed'):
                            declared = result['scope']
                            query = normalize_query(declared['query'], 'discover')
                            self.validate_identities(query, {**context, **identity_context})
                            target = declared.get('requested_count')
                            if target is not None:
                                target = canonical_count(target)
                                if job['request'].get('count_source', 'explicit') == 'explicit' and target != job['requested_count']:
                                    raise AIJobError('quantity_conflict')
                            scope = {'query': query, 'subjective_requirements': declared['subjective_requirements']}
                            job = self.store.fix_scope(job_id, scope, target=target)
                            self.store.update_constraints(job['session_id'], selection.account_id, {'scope': scope})
                            session['constraints']['scope'] = scope
                        final = result['recommendations']
                        repair = 0
                    except ChatGPTError as error:
                        if error.code in ('invalid_stream', 'invalid_feature_result', 'inconsistent_tool_arguments',
                                          'unknown_or_incomplete_tool', 'invalid_terminal_response') and repair == 0:
                            repair = 1
                            followup_items = inputs + [{'role': 'developer', 'content':
                                'The previous result failed local JSON validation. Return the required JSON object with title/year recommendations. Include scope only when scope_is_fixed is false. This is the only repair for this batch.'}]
                            continue
                        raise
                    followup_items = []
                    if not final:
                        return self._finish(job, 'partial', 'No further verified candidates returned; the requested target was not reached.')
                    report_progress('matching')
                    with self.measure_phase('tmdb_matching'):
                        batch = []
                        batch_ids = set()
                        rejected = list(job['cursor'].get('recommendation_rejections', []))
                        for candidate, resolved in lookups.resolve(final):
                            if cancel.is_set():
                                return self.store.snapshot(job_id)
                            if not resolved:
                                rejected.append({'title': candidate['title'], 'year': candidate.get('year', ''),
                                                 'reason': 'Movie identity could not be verified; suggest a different film.'})
                                continue
                            eligibility = self.catalogue.candidate_eligibility(resolved['raw'], scope['query'], context_cache=entity_cache)
                            if eligibility != 'eligible':
                                rejected.append({'title': candidate['title'], 'year': candidate.get('year', ''),
                                                 'reason': 'Provider facts are '+eligibility+' for the fixed requirements; suggest a different film.'})
                                continue
                            card = resolved['card']
                            identity = str(card.get('tmdb_id') or '')
                            if not identity or identity in batch_ids or self.store.result_seen(job['session_id'], 'movie', identity):
                                rejected.append({'title': candidate['title'], 'year': candidate.get('year', ''),
                                                 'reason': 'Movie already shown in this session; suggest a different film.'})
                                continue
                            batch_ids.add(identity)
                            batch.append({'domain': 'movie', 'identity': identity, 'card': card})
                            if not job['accepted_count'] or len(batch) >= 4:
                                self.check_permission(selection)
                                job = self.store.add_results(job_id, batch, limit_to_target=True)
                                batch = []
                            if target_reached(job['accepted_count'] + len(batch), job['requested_count']):
                                break
                        if batch:
                            self.check_permission(selection)
                            job = self.store.add_results(job_id, batch, limit_to_target=True)
                        if rejected:
                            self.store.save_checkpoint(job_id, 'recommendation_rejections', rejected[-200:])
                        if target_reached(job['accepted_count'], job['requested_count']):
                            return self._finish(job, 'completed', 'Requested verified target reached.')
        except AIJobError as error:
            if error.code in ('paused_budget', 'job_not_running', 'cancelled'):
                return self.store.snapshot(job_id)
            current = self.store.snapshot(job_id)
            return self._finish(current, 'awaiting_clarification' if error.code == 'quantity_conflict'
                                else 'partial' if current['accepted_count'] else 'failed', error.code)
        except (ChatGPTError, AICatalogError, AIProviderError) as error:
            current = self.store.snapshot(job_id)
            return self._finish(current, 'partial' if current['accepted_count'] else 'failed', error.code)
        except Exception:
            return self._finish(self.store.snapshot(job_id), 'failed', 'recommendation_failed')

    def _finish(self, job, state, message):
        if job['accepted_count']:
            self.store.append_turn(job['session_id'], job['selection']['account_id'],
                {'role': 'assistant', 'content': f"Returned {job['accepted_count']} verified recommendations."},
                constraints={'last_recommendation_job': job['id']})
        return self.store.finish(job['id'], state, coverage='complete' if state == 'completed' else 'partial', message=message)
