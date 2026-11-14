"""Explicit, provider-bound cloud inference for IPTV review proposals only."""
import hashlib
import json
import time
from collections import Counter

from services.ai_jobs import AIJobError, bulk_catalog_generation
from services.ai_provider import AISelection, AIProviderError
from services.chatgpt_recommendations import JobCancellation
from services.chatgpt_skills import (
    IPTV_BULK_INSTRUCTIONS, IPTV_BULK_PROTOCOL_HASH, IPTV_BULK_ROW_SCHEMA, IPTV_RECOVERY_BATCH,
    IPTV_RECOVERY_CHARACTERS, IPTV_RECOVERY_INSTRUCTIONS, IPTV_RECOVERY_PROTOCOL_HASH,
    IPTV_RECOVERY_ROW_SCHEMA, load, validate_schema,
)
from services.chatgpt_tools import model_safe
from services.chatgpt_transport import ChatGPTError
from services.iptv_movie_classifier import build_ollama_classification_payload, validate_classification_result
from services.iptv_movie_store import IPTVSelectionError
from services.iptv_tmdb import IPTVTMDBError


BULK_FIRST_BATCH = 100
BULK_REPAIR_BATCH = 50
BULK_REPAIRS = 2
BULK_CHECKPOINT_ROWS = 25
_USAGE_LIMITS = {'usage_limit_reached', 'usage_limit_exceeded', 'plan_usage_limit_reached',
                 'subscription_sharing_usage_limit_exceeded', 'insufficient_quota', 'quota_exceeded',
                 'billing_hard_limit_reached'}
_INVALID_REPLIES = {'invalid_stream', 'invalid_terminal_response', 'inconsistent_output_text',
                    'missing_terminal_event', 'missing_terminal_tool_call', 'unknown_or_incomplete_tool',
                    'incomplete_output_stream', 'response_incomplete', 'response_too_large',
                    'max_output_tokens', 'content_filter', 'invalid_iptv_result'}


def _unique_json_object(pairs):
    value = dict(pairs)
    if len(value) != len(pairs):
        raise ValueError('Duplicate JSON fields')
    return value


def _validated_rows(text, maximum, schema):
    try:
        response = json.loads(text, object_pairs_hook=_unique_json_object)
        if not isinstance(response, dict) or set(response) != {'rows'}:
            return []
        rows = response['rows']
        if not isinstance(rows, list) or len(rows) > maximum:
            return []
    except (ValueError, TypeError, RecursionError):
        return []
    counts = Counter(row['id'] for row in rows if isinstance(row, dict) and isinstance(row.get('id'), str))
    valid = []
    for row in rows:
        try:
            validate_schema(schema, row)
            json.dumps(row, ensure_ascii=False).encode('utf-8')
        except ValueError:
            continue
        if counts[row['id']] == 1:
            valid.append(row)
    return valid


def _bulk_interpretations(text, submitted):
    submitted = set(submitted)
    return {row['id']: row for row in _validated_rows(text, BULK_FIRST_BATCH, IPTV_BULK_ROW_SCHEMA)
            if row['id'] in submitted and all(model_safe(title) == title and '\n' not in title and '\r' not in title
                                              for title in [row['title'], *row['aliases']])}


def _recovery_decisions(text, submitted):
    valid = {}
    for row in _validated_rows(text, IPTV_RECOVERY_BATCH, IPTV_RECOVERY_ROW_SCHEMA):
        identity, candidate, decision = row['id'], row['candidate_id'], row['decision']
        if identity not in submitted or (candidate is not None and candidate not in submitted[identity]):
            continue
        if (decision == 'match' and candidate is None) or (decision == 'no_candidate' and candidate is not None):
            continue
        if model_safe(row['reason']) != row['reason'] or any(ord(char) < 32 for char in row['reason']):
            continue
        valid[identity] = row
    return valid


def _bulk_input(index, source):
    row = {'id': str(index), 'title': model_safe(source['provider_title'][:240])}
    if source.get('provider_year'):
        row['year'] = source['provider_year']
    if source.get('playlist_name'):
        row['playlist'] = model_safe(source['playlist_name'][:100])
    return row


class IPTVInference:
    def __init__(self, transport, *, check_permission=lambda selection: None):
        self.transport, self.check_permission = transport, check_permission

    def _run(self, selection, evidence, *, cancel, validate, title_hints=False):
        skill = load(selection.feature)
        if selection.feature not in ('F4', 'F5') or selection.skill_hash != skill['hash']:
            raise ChatGPTError('skill_changed')
        inputs = [{'role': 'user', 'content': json.dumps(model_safe(evidence), ensure_ascii=False)}]
        tools = skill['hint_tools'] if title_hints else skill['tools']
        schema = skill['hint_schema'] if title_hints else skill['tool_schema']
        for attempt in range(2):
            self.check_permission(selection)
            try:
                response = self.transport.run(selection, instructions=skill['instructions'], input_items=inputs,
                    tools=tools, cancel=cancel)
                if len(response.tool_calls) != 1 or response.tool_calls[0].name != 'cp_result.submit':
                    raise ValueError('A single feature result is required')
                result = response.tool_calls[0].arguments
                validate_schema(schema, result)
                return validate(result)
            except ValueError:
                if attempt:
                    raise ChatGPTError('invalid_iptv_result') from None
            except ChatGPTError as error:
                if attempt or error.code not in ('invalid_feature_result', 'invalid_stream', 'inconsistent_tool_arguments',
                                                'unknown_or_incomplete_tool', 'invalid_terminal_response'):
                    raise
            inputs.append({'role': 'developer', 'content': 'The response failed local result validation. Follow the supplied result schema and the instructions for this mode. This is the only repair.'})
        raise ChatGPTError('invalid_iptv_result')

    def classify(self, selection, playlist, titles, *, cancel):
        if selection.feature != 'F4' or not titles or len(titles) > 25:
            raise ChatGPTError('invalid_classification_batch')
        evidence = build_ollama_classification_payload(model_safe(playlist), [model_safe(title) for title in titles])
        def validate(result):
            if any(row['title'] not in evidence['sample_titles'] for row in result['title_exceptions']):
                raise ValueError('Foreign title exception')
            normalized = validate_classification_result(result)
            return dict(normalized, method='chatgpt')
        return self._run(selection, evidence, cancel=cancel, validate=validate)


    def rank(self, selection, evidence, *, cancel):
        if selection.feature != 'F5' or len(evidence.get('candidates', [])) > 8:
            raise ChatGPTError('invalid_ranking_batch')
        allowed = {int(row['tmdb_id']) for row in evidence['candidates']} | {0}
        def validate(result):
            if result['tmdb_id'] not in allowed:
                raise ValueError('Foreign candidate identity')
            return result
        return self._run(selection, evidence, cancel=cancel, validate=validate)

    def suggest_titles(self, selection, evidence, *, cancel):
        if selection.feature != 'F5':
            raise ChatGPTError('invalid_ranking_batch')

        def validate(result):
            aliases = [alias.strip() for alias in result['aliases']]
            if any(not alias or model_safe(alias) != alias or '\n' in alias or '\r' in alias for alias in aliases):
                raise ValueError('Invalid search alias')
            return list(dict.fromkeys(aliases))

        return self._run(selection, {**evidence, 'mode': 'suggest-search-aliases'}, cancel=cancel,
                         validate=validate, title_hints=True)


def run_bulk_apply(store, service, job_id, apply, generation, authorize, shutting_down=lambda: False):
    """Reconcile provider receipts before issuing any new catalog writes."""
    from services.ai_provider import AIProviderError

    while True:
        rows = store.bulk_apply_chunk(job_id, apply)
        state, reason = None, ''
        try:
            authorize()
        except AIProviderError:
            state, reason = 'interrupted', 'Restore the original ChatGPT account and IPTV title permission, then resume Apply.'
        if not service.store.bulk_selection_current(generation):
            state, reason = 'stale', 'The provider catalog changed. Start a new scan for the remaining proposals.'
        def stop_job():
            if not apply.get('automatic'):
                return None
            job_state, pausing = store.bulk_control(job_id)
            return 'stopped' if job_state == 'cancelled' else 'interrupted' if pausing or job_state != 'running' else None

        authorization_lost = False
        def authorized_to_write():
            nonlocal authorization_lost
            if authorization_lost:
                return False
            try:
                authorize()
                return True
            except AIProviderError:
                authorization_lost = True
                return False

        with store.bulk_apply_stop_reader(job_id, apply['id']) as stopping:
            report = service.apply_bulk_proposals(rows, 'match', generation, operation_id=apply['id'],
                stop_requested=lambda: bool(state) or shutting_down() or stopping() or bool(stop_job()) or
                ((apply.get('automatic') or apply['scope'] == 'retry_failed') and not authorized_to_write()))
            stopped = stopping()
        if shutting_down() and not state:
            state, reason = 'interrupted', 'CP stopped. Resume Apply to reconcile saved catalog writes.'
        if not state and report['halted'] == 'iptv_selection_changed':
            state, reason = 'stale', 'The provider catalog changed. Start a new scan for the remaining proposals.'
        if not state and (job_stop := stop_job()):
            state, reason = job_stop, 'The scan stopped before the next catalogue write.'
        if not state and (apply.get('automatic') or apply['scope'] == 'retry_failed') and not authorized_to_write():
            state, reason = 'interrupted', 'The ChatGPT account, configuration or IPTV title permission changed.'
        if not state and (report['halted'] == 'bulk_apply_stopped' or not rows or stopped):
            state = 'completed'  # The checkpoint transaction resolves a concurrent Stop to stopped.
        apply = store.checkpoint_bulk_apply(job_id, apply['id'], report['outcomes'], state=state, reason=reason,
            advance=state not in ('interrupted', 'stale'))  # Receipt checks can settle sparse positions.
        if state:
            return apply


class IPTVJob:
    def __init__(self, store, service_factory, transport_factory, *, check_permission=lambda selection: None,
                 prepare_review=None, dispatch_apply=None, check_bulk_binding=None):
        self.store, self.service_factory, self.transport_factory = store, service_factory, transport_factory
        self.check_permission = check_permission
        self.prepare_review = prepare_review
        self.dispatch_apply = dispatch_apply
        self.check_bulk_binding = check_bulk_binding or check_permission

    def reconcile_cancelled_bulk(self, job):
        """Settle abandoned results and saved receipts without new inference or writes."""
        self._settle_abandoned_recovery(job, 'recovery_interrupted', cancelled=True)
        saved_apply = job.get('bulk_apply') or {}
        job_id = job['id']
        if saved_apply.get('automatic') and saved_apply['state'] == 'interrupted':
            service = self.service_factory(job['selection']['domain_id'])
            apply = self.store.claim_automatic_bulk_apply(job_id, reconcile_cancelled=True)
            if apply:
                generation = bulk_catalog_generation(job)
                run_bulk_apply(self.store, service, job_id, apply, generation, lambda: None)
        return self.store.snapshot(job_id)

    def _settle_abandoned_recovery(self, job, reason, *, cancelled=False):
        from services.iptv_movie_service import IPTVMovieService

        work = job['cursor'].get('bulk_work', {})
        recovery = work.get('recovery', {})
        entries = recovery.get('in_flight', [])
        if not entries:
            return
        job_id = job['id']
        snapshot = job['request']['selection_snapshot']
        keys = [snapshot['source_keys'][entry['index']] for entry in entries]
        previous = {row['source_key']: row for row in self.store.bulk_proposals(job_id, keys)}
        results = [{'domain': 'iptv', 'identity': key, 'card': IPTVMovieService.finish_bulk_recovery(
            previous[key], entry, reason=reason)} for key, entry in zip(keys, entries)]
        recovery['in_flight'] = []
        recovery.pop('decisions', None)
        recovery['completed'] += len(entries)
        self.store.add_results(job_id, results, bulk_work=work, replace_bulk_results=True, settle_cancelled=cancelled)

    def run(self, job_id):
        job = self.store.snapshot(job_id)
        if job['state'] != 'queued':
            return job
        try:
            job = self.store.start_run(job_id, job['revision'])
            selection = AISelection(**job['selection'])
            self.check_permission(selection)
            service = self.service_factory(selection.domain_id)
            snapshot = job['request']['selection_snapshot']
            if service.provider_id != selection.domain_id or service.store.source_generation() != bulk_catalog_generation(job):
                if job['request'].get('bulk_recovery_protocol_hash'):
                    self._settle_abandoned_recovery(job, 'recovery_source_changed')
                raise AIJobError('iptv_selection_changed')
            cancel = JobCancellation(self.store, job_id)
            if 'bulk_call_budget' in job['request']:
                return self._run_bulk(job, selection, service, cancel)
            inference = IPTVInference(self.transport_factory(selection, job_id), check_permission=self.check_permission)
            if selection.feature == 'F4':
                cache = job['cursor'].get('iptv_classification_cache', {})
                processed = 0
                def classify(playlist, titles):
                    nonlocal processed
                    if cancel.is_set():
                        raise AIJobError('cancelled')
                    key = hashlib.sha256(json.dumps([playlist, titles], ensure_ascii=False).encode()).hexdigest()
                    if key not in cache:
                        cache[key] = inference.classify(selection, playlist, titles, cancel=cancel)
                        self.store.save_checkpoint(job_id, 'iptv_classification_cache', cache)
                    processed += len(titles)
                    self.store.save_checkpoint(job_id, 'iptv_processed', processed)
                    return cache[key]
                output = service.classification_preview({}, selection_snapshot=snapshot,
                    ai_classifier=classify, ai_provenance=selection.public())
                rows = output['proposals']
            elif selection.feature == 'F5':
                pending_hint = job['cursor'].get('iptv_pending_hint', {})

                def hint(key, evidence):
                    if cancel.is_set():
                        raise AIJobError('cancelled')
                    if pending_hint.get('source_key') != key:
                        aliases = inference.suggest_titles(selection, evidence, cancel=cancel)
                        pending_hint.update(source_key=key, aliases=aliases)
                        self.store.save_checkpoint(job_id, 'iptv_pending_hint', pending_hint)
                    return pending_hint['aliases']

                output = service.create_match_job({'method': 'ai'}, selection_snapshot=snapshot,
                    ai_ranker=lambda evidence: inference.rank(selection, evidence, cancel=cancel),
                    ai_title_hints=hint,
                    resume_job_id=job['cursor'].get('iptv_native_job_id'),
                    on_created=lambda identity: self.store.save_checkpoint(job_id, 'iptv_native_job_id', identity),
                    on_progress=lambda count: self.store.save_checkpoint(job_id, 'iptv_processed', count),
                    ai_provenance=selection.public())
                rows = output['proposals']
            else:
                raise AIJobError('invalid_iptv_feature')
            if service.store.source_generation() != snapshot['catalog_generation']:
                raise AIJobError('iptv_selection_changed')
            if cancel.is_set():
                return self.store.snapshot(job_id)
            self.store.add_results(job_id, [{'domain': 'iptv', 'identity': row['source_key'], 'card': row} for row in rows])
            complete = len(rows) == len(snapshot['source_keys'])
            prepared = (self.prepare_review(job, selection, output) if complete and rows and self.prepare_review
                        and not job['request'].get('parent_job_id') and not job['request'].get('deferred_action_id') else None)
            return self.store.finish(job_id, 'completed' if complete else 'partial',
                coverage='complete' if complete else 'partial', output={'provider_id': selection.domain_id,
                    'review_required': True, 'kind': 'classification' if selection.feature == 'F4' else 'match',
                    'review': output, 'prepared_review': prepared})
        except AIJobError as error:
            if error.code in ('paused_budget', 'job_not_running', 'cancelled', 'stale_job_revision'):
                return self.store.snapshot(job_id)
            return self.store.finish(job_id, 'failed', message=error.code)
        except (AIProviderError, ChatGPTError) as error:
            return self.store.finish(job_id, 'failed', message=error.code)
        except IPTVSelectionError as error:
            return self.store.finish(job_id, 'failed', message=str(error))
        except Exception:
            return self.store.finish(job_id, 'failed', message='iptv_preview_failed')

    def _run_bulk(self, job, selection, service, cancel):
        job_id = job['id']
        work = job['cursor'].get('bulk_work', {'offset': 0, 'pending': [], 'answers': {}, 'throttles': 0})
        keys = self.store.bulk_work_sources(job)
        generation = bulk_catalog_generation(job)
        recovery_protocol = job['request'].get('bulk_recovery_protocol_hash')
        automatic = job['request'].get('bulk_auto_apply', False)
        proposal_options = {'automatic': True, 'focused_search': False} if automatic and recovery_protocol else (
            {'automatic': True} if automatic else {})
        pinned_bulk = automatic or bool(recovery_protocol)
        # Only saved jobs launched with the recovery protocol can reach that stage.
        recovery = work.setdefault('recovery', {'version': 1, 'pending': [], 'in_flight': [],
                                   'admitted': 0, 'requests': 0, 'completed': 0}) if recovery_protocol else None
        batch_size = job['request'].get('titles_per_request', BULK_FIRST_BATCH)
        recheck = job['cursor'].get('bulk_search_recheck')
        transport = None if recheck else self.transport_factory(selection, job_id)
        report = self.store.progress_reporter(job_id)
        client = None
        next_control_check = 0
        saved_apply = job.get('bulk_apply') or {}
        apply_due = bool(job['cursor'].get('bulk_automatic_pending') or
                         (saved_apply.get('automatic') and saved_apply['state'] == 'interrupted'))

        def check():
            state, pausing = self.store.bulk_control(job_id)
            if state != 'running':
                raise AIJobError('job_not_running')
            if pausing:
                raise AIJobError('bulk_pause_requested')

        def should_yield():
            nonlocal next_control_check
            now = time.monotonic()
            if now < next_control_check:
                return False
            next_control_check = now + .25
            state, pausing = self.store.bulk_control(job_id)
            return state != 'running' or pausing

        def admit_request():
            check()
            (self.check_bulk_binding if pinned_bulk else self.check_permission)(selection)
            if not service.store.bulk_selection_current(generation):
                raise IPTVSelectionError('iptv_selection_changed', 'The provider catalog changed. Start a new review.')

        def checkpoint(rows=(), *, replace=False, settle_cancelled=False, check_generation=True, recheck_work=None):
            nonlocal apply_due
            if check_generation and not service.store.bulk_selection_current(generation):
                raise IPTVSelectionError('iptv_selection_changed', 'The provider catalog changed. Start a new review.')
            self.store.add_results(job_id, [{'domain': 'iptv', 'identity': row['source_key'], 'card': row}
                                            for row in rows], bulk_work=work, replace_bulk_results=replace,
                                   settle_cancelled=settle_cancelled, recheck_work=recheck_work)
            apply_due = apply_due or any(row.get('bulk_automatic') for row in rows)

        def stage(phase):
            if pinned_bulk:
                work['phase'] = phase
            report(phase)

        def apply_pending():
            nonlocal apply_due
            if not automatic or not apply_due:
                return
            while (apply := self.store.claim_automatic_bulk_apply(job_id)) is not None:
                stage('applying_verified')
                def apply_work(shutdown):
                    return run_bulk_apply(self.store, service, job_id, apply, generation,
                                          lambda: self.check_bulk_binding(selection), shutdown)
                try:
                    if self.dispatch_apply:
                        future = self.dispatch_apply(job_id, apply['id'], apply_work)
                        status = future.result() if future else None
                    else:
                        status = apply_work(lambda: False)
                except Exception:
                    status = self.store.snapshot(job_id).get('bulk_apply')
                    if status and status['state'] in ('running', 'stopping'):
                        status = self.store.checkpoint_bulk_apply(job_id, apply['id'], state='interrupted',
                            reason='Apply stopped unexpectedly. Resume to reconcile saved catalogue writes.')
                check()
                if status is None or status['state'] == 'interrupted':
                    raise AIJobError('bulk_automatic_apply_interrupted')
                if status['state'] == 'stale':
                    raise AIJobError('iptv_selection_changed')
            apply_due = False

        def prior_rows(indices):
            return {row['source_key']: row for row in self.store.bulk_proposals(
                job_id, [keys[index] for index in indices])}

        def resolve_recovery():
            stage('recovery_verifying')
            entries = recovery['in_flight']
            indices = [entry['index'] for entry in entries]
            previous = prior_rows(indices)
            stale = not service.store.bulk_selection_current(generation)
            try:
                sources = {} if stale else service.store.bulk_sources([keys[index] for index in indices], generation)
            except IPTVSelectionError:
                stale, sources = True, {}
            decisions = recovery.pop('decisions', None)
            results = []
            cancelled = cancel.is_set()
            for entry in entries:
                index = entry['index']
                key = keys[index]
                source = sources.get(key)
                decision = decisions.get(str(index)) if decisions is not None else None
                if cancelled or decisions is None:
                    reason = 'recovery_interrupted'
                elif (stale or not source or source['source_revision'] != entry['source_revision'] or
                      source['match_revision'] != entry['match_revision'] or
                      not service.bulk_recovery_eligible(source, previous[key])):
                    reason = 'recovery_source_changed'
                else:
                    reason = '' if decision else 'recovery_invalid_response'
                results.append(service.finish_bulk_recovery(previous[key], entry, decision, reason))
            recovery['in_flight'] = []
            recovery['completed'] += len(entries)
            checkpoint(results, replace=True, settle_cancelled=True, check_generation=False)
            if stale and not cancelled:
                raise AIJobError('iptv_selection_changed')

        def recover_next():
            nonlocal client
            stage('recovery_preparing')
            checkpoint()
            if client is None:
                client = service.bulk_tmdb_client()
            indices = recovery['pending'][:IPTV_RECOVERY_BATCH]
            previous = prior_rows(indices)
            sources = service.store.bulk_sources([keys[index] for index in indices], generation)
            entries, submitted = [], []
            def encode(rows):
                return json.dumps({'rows': rows}, ensure_ascii=False, separators=(',', ':'))
            for index in indices:
                check()
                key = keys[index]
                source = sources.get(key)
                prior = previous[key]
                entry, reason = {'index': index, 'attempts': 0}, ''
                if not source or not service.bulk_recovery_eligible(source, prior):
                    reason = 'recovery_source_changed'
                else:
                    try:
                        evidence = service.prepare_bulk_recovery(source, prior, client)
                        entry.update(evidence=evidence, source_revision=source['source_revision'],
                                     match_revision=source['match_revision'])
                        if not evidence['candidates']:
                            reason = 'recovery_search_limited' if evidence['search_limit_reached'] else 'recovery_no_candidate'
                        else:
                            payload = {'id': str(index), **service.compact_bulk_recovery(evidence)}
                            if len(encode([payload])) > IPTV_RECOVERY_CHARACTERS:
                                reason = 'recovery_evidence_too_large'
                    except IPTVTMDBError as error:
                        entry['tmdb_error'] = {'status': error.status, 'retryable': error.retryable,
                                               'retry_after': error.retry_after}
                        reason = 'recovery_tmdb_failed'
                if reason:
                    if entries:
                        break  # Keep the persisted admission prefix contiguous.
                    del recovery['pending'][0]
                    recovery['completed'] += 1
                    checkpoint([service.finish_bulk_recovery(prior, entry, reason=reason)], replace=True)
                    continue
                if len(encode([*submitted, payload])) > IPTV_RECOVERY_CHARACTERS:
                    break
                entry.update(attempts=1, protocol_hash=recovery_protocol,
                             evidence_hash=hashlib.sha256((recovery_protocol + encode([payload])).encode()).hexdigest(),
                             submitted_input=payload,
                             candidate_ids=[item['candidate_id'] for item in payload['candidates']])
                entries.append(entry)
                submitted.append(payload)
            if not entries:
                return None

            def reserve():
                # This runs in the existing inference slot immediately before I/O.
                admit_request()
                latest = service.store.bulk_sources([keys[entry['index']] for entry in entries], generation)
                if any((source := latest.get(keys[entry['index']])) is None or
                       source['source_revision'] != entry['source_revision'] or
                       source['match_revision'] != entry['match_revision'] or
                       not service.bulk_recovery_eligible(source, previous[source['source_key']]) for entry in entries):
                    raise AIJobError('recovery_source_changed')
                self.store.reserve_inference(job_id, recovery_batch=entries)
                del recovery['pending'][:len(entries)]
                recovery['in_flight'] = entries
                recovery['admitted'] += len(entries)
                recovery['requests'] += 1
                stage('recovery_comparing')

            allowed = {str(entry['index']): set(entry['candidate_ids']) for entry in entries}
            try:
                response = transport.run(selection, instructions=IPTV_RECOVERY_INSTRUCTIONS,
                    input_items=[{'role': 'user', 'content': encode(submitted)}], tools=[], cancel=cancel,
                    recover_completed_text=True, reserve_request=reserve)
            except AIJobError as error:
                if error.code != 'recovery_source_changed':
                    raise
                # At least one source changed before admission. Settle the changed
                # rows on the next preparation without spending the request.
                latest = service.store.bulk_sources([keys[entry['index']] for entry in entries], generation)
                results = []
                for entry in entries:
                    index = entry['index']
                    key = keys[index]
                    source = latest.get(key)
                    if (not source or source['source_revision'] != entry['source_revision'] or
                            source['match_revision'] != entry['match_revision'] or
                            not service.bulk_recovery_eligible(source, previous[key])):
                        recovery['pending'].remove(index)
                        recovery['completed'] += 1
                        results.append(service.finish_bulk_recovery(previous[key], {**entry, 'attempts': 0},
                                                                   reason='recovery_source_changed'))
                if not results:
                    # A racing change may have been reverted. End the affected
                    # attempt rather than repeatedly trying to admit this batch.
                    raise
                checkpoint(results, replace=True)
                return None
            except ChatGPTError as error:
                admitted = bool(recovery['in_flight'])
                if admitted:
                    if error.code in _INVALID_REPLIES:
                        recovery['decisions'] = {}
                    resolve_recovery()
                if error.code in _USAGE_LIMITS:
                    return self.store.finish(job_id, 'paused', coverage='partial',
                        message='ChatGPT plan usage exhausted. Resume when usage is available.')
                if error.code == 'cancelled' and cancel.is_set():
                    raise AIJobError('job_not_running') from None
                if not error.code in _INVALID_REPLIES and error.status not in (429, 500, 502, 503, 504) and (
                        error.code not in {'network_error', 'inference_deadline', 'rate_limit', 'rate_limit_exceeded'}):
                    raise
                if not admitted or error.code in {'network_error', 'inference_deadline'}:
                    return self.store.finish(job_id, 'paused', coverage='partial',
                        message='The recovery request was interrupted. Resume to continue with remaining sources.')
            else:
                recovery['decisions'] = _recovery_decisions(response.text, allowed)
                if not cancel.is_set():
                    checkpoint(check_generation=False)
                resolve_recovery()
            return None

        def unavailable(key):
            return {'source_key': key, 'proposal_id': key, 'outcome': 'failed', 'category': 'unclassified',
                    'review_reason': 'This source is no longer available.', 'warnings': ['Source unavailable.']}

        try:
            if job['request'].get('bulk_protocol_hash', IPTV_BULK_PROTOCOL_HASH) != IPTV_BULK_PROTOCOL_HASH:
                raise AIJobError('bulk_protocol_changed')
            if recovery_protocol and recovery_protocol != IPTV_RECOVERY_PROTOCOL_HASH:
                raise AIJobError('bulk_recovery_protocol_changed')
            if pinned_bulk:
                self.check_bulk_binding(selection)
            while True:
                apply_pending()
                if recheck and recheck['processed'] < len(recheck['keys']):
                    admit_request()
                    stage('rechecking_search')
                    if client is None or recheck['processed'] % batch_size == 0:
                        client = service.bulk_tmdb_client()
                    chunk = recheck['keys'][recheck['processed']:recheck['processed'] + BULK_CHECKPOINT_ROWS]
                    sources = service.store.bulk_sources(chunk, generation)
                    saved = {row['source_key']: row for row in self.store.bulk_proposals(job_id, chunk)}
                    for key in chunk:
                        check()
                        proposal = service.recheck_bulk_search(sources.get(key), saved[key], client)
                        if proposal and proposal['outcome'] == 'failed':
                            return self.store.finish(job_id, 'paused', coverage='partial',
                                message='TMDB could not finish the lookup. Resume to retry this listing.')
                        if proposal and proposal['outcome'] == 'verified':
                            result = proposal
                            recheck['verified'] += 1
                        else:
                            # Retain the old evidence and historical Apply status for unresolved rows.
                            result = saved[key]
                            if result.get('review_reason') and not proposal:
                                result['review_reason'] = 'The provider listing changed or is no longer eligible.'
                                result['warnings'] = [result['review_reason']]
                            elif proposal:
                                result.update(review_reason=proposal['review_reason'], warnings=proposal['warnings'])
                        result['evidence']['search_recheck'] = True
                        recheck['processed'] += 1
                        checkpoint([result], recheck_work=recheck)
                    continue
                if recheck:
                    check()
                    if not service.store.bulk_selection_current(generation):
                        raise AIJobError('iptv_selection_changed')
                    return self.store.finish(job_id, 'completed', coverage='complete',
                        output={'provider_id': selection.domain_id, 'review_required': True, 'kind': 'bulk'})
                if recovery and recovery['in_flight']:
                    resolve_recovery()
                    check()
                    continue
                if work['answers']:
                    stage('matching')
                    if client is None:
                        client = service.bulk_tmdb_client()
                    indices = list(work['answers'])[:BULK_CHECKPOINT_ROWS]
                    rows = service.store.bulk_sources([keys[int(index)] for index in indices], generation)
                    results = []
                    flush_at = time.monotonic() + 3
                    for index in indices:
                        if should_yield():
                            break
                        key = keys[int(index)]
                        source = rows.get(key)
                        answer = work['answers'].pop(index)
                        proposal = (service.bulk_source_proposal(source, client, interpretation=answer,
                            interpreted=True, **proposal_options) if source else unavailable(key))
                        if recovery is not None and source and service.bulk_recovery_eligible(source, proposal):
                            recovery['pending'].append(int(index))
                        results.append(proposal)
                        if time.monotonic() >= flush_at:
                            break
                    if pinned_bulk:
                        work['first_pass_resolved'] = work.get('first_pass_resolved', 0) + len(results)
                    checkpoint(results)
                elif recovery and recovery['pending'] and not work['pending']:
                    paused = recover_next()
                    if paused is not None:
                        return paused
                elif work['offset'] < len(keys) and (not work['pending'] or
                                                    work['offset'] < work.get('window_end', 0)):
                    check()
                    stage('preparing')
                    client = service.bulk_tmdb_client()  # Keep TMDB memoization bounded to one batch.
                    start = work['offset']
                    stop = work.get('window_end', 0)
                    if stop <= start:
                        stop = min(start + batch_size, len(keys))
                        work['window_end'] = stop
                    rows = service.store.bulk_sources(keys[start:stop], generation)
                    results = []
                    flush_at = time.monotonic() + 3
                    for index in range(start, stop):
                        if should_yield():
                            break
                        key = keys[index]
                        source = rows.get(key)
                        row = (service.bulk_source_proposal(source, client,
                            **proposal_options) if source else unavailable(key))
                        if row is None:
                            work['pending'].append([index, 0])
                        else:
                            results.append(row)
                        work['offset'] = index + 1
                        if results and (len(results) >= BULK_CHECKPOINT_ROWS or time.monotonic() >= flush_at):
                            checkpoint(results)
                            results = []
                            flush_at = time.monotonic() + 3
                    checkpoint(results)
                elif not work['pending']:
                    check()
                    if not service.store.bulk_selection_current(generation):
                        raise AIJobError('iptv_selection_changed')
                    return self.store.finish(job_id, 'completed', coverage='complete',
                        output={'provider_id': selection.domain_id, 'review_required': True, 'kind': 'bulk'})
                else:
                    stage('interpreting')
                    admit_request()
                    if client is None:
                        client = service.bulk_tmdb_client()
                    attempts = work['pending'][0][1]
                    size = min(BULK_REPAIR_BATCH, batch_size) if attempts else batch_size
                    batch = []
                    for index, attempt in work['pending'][:size]:
                        if attempt != attempts:
                            break
                        batch.append(index)
                    rows = service.store.bulk_sources([keys[index] for index in batch], generation)
                    if automatic:
                        rows = {key: row for key, row in rows.items() if service.bulk_inference_eligible(row)}
                    submitted = [_bulk_input(index, rows[keys[index]]) for index in batch if keys[index] in rows]

                    def admit_first_pass():
                        admit_request()
                        if automatic:
                            latest = service.store.bulk_sources(list(rows), generation)
                            if any(key not in latest or not service.bulk_inference_eligible(latest[key]) or
                                   any(latest[key][field] != source[field]
                                       for field in ('source_revision', 'match_revision'))
                                   for key, source in rows.items()):
                                raise AIJobError('bulk_first_pass_source_changed')

                    valid = {}
                    try:
                        if submitted:
                            response = transport.run(selection, instructions=IPTV_BULK_INSTRUCTIONS,
                                input_items=[{'role': 'user', 'content': json.dumps({'rows': submitted},
                                    ensure_ascii=False, separators=(',', ':'))}],
                                tools=[], cancel=cancel, recover_completed_text=True, admit_request=admit_first_pass)
                            valid = _bulk_interpretations(response.text, (row['id'] for row in submitted))
                    except AIJobError as error:
                        if error.code != 'bulk_first_pass_source_changed':
                            raise
                        continue
                    except ChatGPTError as error:
                        if error.code in _USAGE_LIMITS:
                            return self.store.finish(job_id, 'paused', coverage='partial',
                                message='ChatGPT plan usage exhausted. Resume when usage is available.')
                        if error.status in (429, 500, 502, 503, 504) or error.code in (
                                'rate_limit_exceeded', 'rate_limit', 'network_error'):
                            work['throttles'] += 1
                            if work['throttles'] >= 3:
                                work['throttles'] = 0
                                checkpoint()
                                return self.store.finish(job_id, 'paused', coverage='partial',
                                    message='ChatGPT is temporarily unavailable. Resume to retry.')
                            checkpoint()
                            report('backoff')
                            delay = error.retry_after if error.retry_after is not None else 2 ** work['throttles']
                            for _ in range(int(delay * 10 + .999)):
                                check()
                                if cancel.wait(.1):
                                    raise AIJobError('job_not_running')
                            continue
                        if error.code not in _INVALID_REPLIES:
                            raise
                    work['throttles'] = 0
                    del work['pending'][:len(batch)]
                    for index in batch:
                        identity = str(index)
                        if identity in valid or attempts >= BULK_REPAIRS or keys[index] not in rows:
                            work['answers'][identity] = valid.get(identity)
                        else:
                            work['pending'].append([index, attempts + 1])
                    checkpoint()
                check()
        except AIJobError as error:
            if error.code == 'bulk_pause_requested':
                return self.store.finish(job_id, 'paused', coverage='partial', message='Paused by request.')
            if error.code == 'inference_busy':
                return self.store.finish(job_id, 'paused', coverage='partial',
                    message='No ChatGPT request slot became available. Resume to try again.')
            if error.code == 'bulk_automatic_apply_interrupted':
                return self.store.finish(job_id, 'interrupted', coverage='partial',
                    message='Automatic Apply stopped. Resume to reconcile saved catalogue writes.')
            raise
        except ChatGPTError as error:
            if error.code == 'cancelled' and cancel.is_set():
                return self.store.snapshot(job_id)
            if error.code == 'inference_deadline':
                return self.store.finish(job_id, 'paused', coverage='partial',
                    message='The ChatGPT request timed out. Resume to retry the pending batch.')
            raise
        finally:
            if recovery is not None and self.store.bulk_control(job_id)[0] == 'cancelled':
                # Read the durable admission again in case cancellation raced a checkpoint.
                self.reconcile_cancelled_bulk(self.store.snapshot(job_id))

