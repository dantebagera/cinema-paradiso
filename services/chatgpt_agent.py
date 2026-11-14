"""Bounded AI Control interpretation. Tools prepare; only the user's route confirms."""
import json

from services.ai_jobs import AIJobError
from services.ai_catalog import AICatalogError
from services.ai_provider import AISelection, AIProviderError
from services.chatgpt_recommendations import JobCancellation
from services.chatgpt_skills import load
from services.chatgpt_tools import ToolContext, ToolError, model_safe
from services.chatgpt_transport import ChatGPTError


class ChatGPTAgent:
    def __init__(self, store, transport_factory, tools, *, check_permission=lambda selection: None,
                 scope_context=lambda: {}):
        self.store, self.transport_factory, self.tools = store, transport_factory, tools
        self.check_permission, self.scope_context = check_permission, scope_context

    def run(self, job_id):
        job = self.store.snapshot(job_id)
        if job['state'] != 'queued':
            return job
        try:
            job = self.store.start_run(job_id, job['revision'])
        except AIJobError:
            return self.store.snapshot(job_id)
        selection = AISelection(**job['selection'])
        cancel = JobCancellation(self.store, job_id)
        try:
            skill = load('F2')
            if selection.skill_hash != skill['hash']:
                raise ToolError('skill_changed; start a new request')
            self.check_permission(selection)
            self.store.record_job_turn(job_id)
            session = self.store.session(job['session_id'], selection.account_id)
            context = ToolContext(selection, job_id, job['session_id'],
                result_sets=self.store.result_sets(job['session_id'], selection.account_id))
            saved = job['cursor'].get('agent', {})
            previous_control = session['constraints'].get('last_control_job')
            prior_refs = {}
            if not saved and previous_control and previous_control != job_id:
                prior_refs = self.store.snapshot(previous_control)['cursor'].get('agent', {}).get('private_refs', {})
            context.prepared = saved.get('prepared', [])
            if not saved:
                for identity in session['constraints'].get('control_refs', {}).get('actions', []):
                    action = self.store.action(identity, selection.account_id)
                    context.prepared.append({key: action[key] for key in ('action_id', 'state', 'revision', 'depends_on')})
            context.identities = saved.get('identities', context.identities)
            context.private.update(saved.get('private_refs', prior_refs))
            context.private.update(cancel=cancel, scope_context=self.scope_context())
            messages = saved.get('messages') or [{'role': row['role'], 'content': model_safe(row['content'])}
                                                 for row in session['turns']]
            ui = saved.get('ui', [])
            if not saved and previous_control and previous_control != job_id:
                pending_ids = {row['action_id'] for row in context.prepared if row['state'] == 'prepared'}
                ui = [view for view in self.store.snapshot(previous_control)['cursor'].get('agent', {}).get('ui', [])
                      if view.get('kind') == 'action-plan' and view.get('action', {}).get('action_id') in pending_ids]
            repairs = saved.get('repairs', 0)
            reads = saved.get('reads', 0)
            active_sets = saved.get('active_sets', {})
            def checkpoint():
                self.store.save_checkpoint(job_id, 'agent', {'messages': model_safe(messages),
                    'prepared': context.prepared, 'identities': context.identities, 'ui': ui, 'repairs': repairs, 'reads': reads,
                    'active_sets': active_sets,
                    'private_refs': {key: context.private[key] for key in ('file_refs', 'collections') if key in context.private}})
            runner = self.transport_factory(selection, job_id)
            while not cancel.is_set():
                self.check_permission(selection)
                response = runner.run(selection, instructions=skill['instructions'] + '\n'
                    + json.dumps({'movie_scope': {'released': True, 'minimum_runtime': 60,
                          'include_documentaries': True, 'unknown_runtime': 'unresolved'},
                        'controlled_identities': context.private['scope_context'],
                        'capabilities': self.tools.manifest(context),
                        'durable_constraints': model_safe(session['constraints']),
                        'known_result_sets': [{'id': row.id, 'domain': row.domain, 'count': len(row.movies),
                            'coverage': row.coverage, 'reason': row.reason} for row in context.result_sets.values()]},
                        ensure_ascii=False), input_items=messages,
                    tools=self.tools.available(selection, context), cancel=cancel)
                messages.extend(response.output)
                if not response.tool_calls:
                    if cancel.is_set():
                        return self.store.snapshot(job_id)
                    for prepared in context.prepared:
                        prepared['state'] = self.store.action(prepared['action_id'], selection.account_id)['state']
                    checkpoint()
                    active_results = [context.result_sets[identity] for identity in active_sets.values()]
                    pending = [row for row in context.prepared if row.get('state') == 'prepared']
                    text = model_safe(response.text.strip())
                    output = {'message': text, 'prepared': pending, 'views': ui,
                              'result_sets': list(active_sets.values())}
                    self.store.append_turn(job['session_id'], selection.account_id,
                        {'role': 'assistant', 'content': text}, constraints={'last_control_job': job_id,
                            'control_refs': {'actions': [row['action_id'] for row in context.prepared],
                                'result_sets': list(active_sets.values()),
                                'native_job_ids': [row['data']['id'] for row in ui if row.get('kind') == 'movie-match' and row.get('data', {}).get('id')]}})
                    return self.store.finish(job_id, 'awaiting_confirmation' if pending else
                        'partial' if any(row.coverage != 'complete' for row in active_results) else
                        'completed' if reads or active_results else 'awaiting_clarification',
                        coverage='partial' if any(row.coverage != 'complete' for row in active_results)
                            else 'complete' if active_results else 'unknown', output=output)
                for call in response.tool_calls:
                    if cancel.is_set():
                        return self.store.snapshot(job_id)
                    try:
                        result = self.tools.call(call.name, call.arguments, context)
                        reads += 1
                        body = result.model
                        if self.tools.definitions[call.name]['domain'] == 'iptv':
                            self.store.mark_evidence_scope(context.session_id, selection.account_id, 'iptv_titles')
                        if self.tools.definitions[call.name]['namespace'] == 'cp_metadata':
                            self.store.mark_evidence_scope(context.session_id, selection.account_id, 'movie_identity_hints')
                        if body.get('result_set') in context.result_sets:
                            resolved = context.result_sets[body['result_set']]
                            active_sets[resolved.query_fingerprint] = resolved.id
                        if result.ui:
                            ui.append(result.ui)
                        if body.get('action_id') and not any(row.get('action_id') == body['action_id'] for row in context.prepared):
                            context.prepared.append(body)
                    except ToolError as error:
                        body = {'error': error.code, 'applied': False}
                        repairs += 1
                        if repairs > 1:
                            raise
                    messages.append({'type': 'function_call_output', 'call_id': call.call_id,
                                     'output': json.dumps(body, ensure_ascii=False)})
                    checkpoint()
            return self.store.snapshot(job_id)
        except (ChatGPTError, AIJobError, AIProviderError, ToolError, AICatalogError) as error:
            if isinstance(error, AIJobError) and error.code in ('paused_budget', 'job_not_running'):
                return self.store.snapshot(job_id)
            return self.store.finish(job_id, 'failed', message=error.code)
        except Exception:
            return self.store.finish(job_id, 'failed', message='control_operation_failed')
