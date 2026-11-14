import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { iptvApi } from '../../api/iptv.js';

const activeStates = ['starting', 'running', 'pausing', 'cancelling', 'waiting-capacity'];
const summaryFields = [
  'sources', 'matches', 'evaluated', 'remaining', 'grouped_movies', 'distinct_tmdb_movies',
  'stale', 'needs_review', 'automatic_remaining', 'classification_review', 'categories',
  'summary_revision', 'summary_updated_at',
];

function mergeStatus(current, incoming) {
  const merged = { ...current, ...incoming };
  if (!current || Number(incoming.summary_revision || 0) >= Number(current.summary_revision || 0)) return merged;
  summaryFields.forEach(field => {
    if (current[field] !== undefined) merged[field] = current[field];
  });
  return merged;
}

export default function useIPTVMovieStatus(providerId, { enabled, generation, refresh, onSettled, notify }) {
  const [snapshot, setSnapshot] = useState(null);
  const [error, setError] = useState('');
  const [command, setCommand] = useState(null);
  const pendingCommand = useRef(null);
  const scope = useMemo(() => ({ providerId, enabled }), [providerId, enabled]);
  const activeScope = useRef(scope);
  const control = command?.providerId === providerId ? command.action : '';
  const controlError = command?.providerId === providerId ? command.error : '';
  const requestKey = JSON.stringify([providerId, enabled, generation, refresh]);
  const worker = snapshot?.providerId === providerId ? snapshot.data : null;
  const publish = useCallback((data, merge = mergeStatus) => {
    if (data && activeScope.current === scope) setSnapshot(current => ({ providerId, requestKey, data: merge(
      current?.providerId === providerId ? current.data : null, data) }));
  }, [providerId, requestKey, scope]);

  useLayoutEffect(() => {
    activeScope.current = scope;
    setCommand(null);
    return () => {
      activeScope.current = null;
      pendingCommand.current = null;
    };
  }, [scope]);

  async function requestControl(action) {
    if (!providerId || !enabled || pendingCommand.current) return;
    const operation = { providerId, action };
    pendingCommand.current = operation;
    setCommand(operation);
    const apiAction = action === 'start-diagnostic' ? 'start' : action;
    const payload = apiAction === 'start'
      ? { consent: !worker?.consent, diagnostic: action === 'start-diagnostic' }
      : apiAction === 'resume' && worker?.restart_confirmation_required ? { continue_after_restart: true } : {};
    try {
      const response = await iptvApi.movieEnrichment(providerId, apiAction, payload);
      if (pendingCommand.current !== operation) return;
      publish(response?.status || response);
      notify?.('IPTV movie metadata ' + action.replaceAll('-', ' '));
      setCommand(null);
    } catch (failure) {
      if (pendingCommand.current === operation) setCommand({ providerId, error: failure.message });
    } finally {
      if (pendingCommand.current === operation) {
        pendingCommand.current = null;
        onSettled();
      }
    }
  }

  useEffect(() => {
    // Retain display data, but never reuse readiness across a disabled interval.
    setSnapshot(current => current ? { ...current, requestKey: null } : current);
    if (!providerId || !enabled) return undefined;
    const controller = new AbortController();
    setError('');
    iptvApi.movieStatus(providerId, {}, { signal: controller.signal }).then(data => {
      if (!controller.signal.aborted) publish(data);
    }).catch(failure => { if (!controller.signal.aborted) setError(failure.message); });
    return () => controller.abort();
  }, [providerId, enabled, generation, refresh, publish]);

  const state = worker?.state;
  const projection = worker?.projection?.state;
  useEffect(() => {
    if (!providerId || !enabled || (!control && !activeStates.includes(state) && projection !== 'running')) return undefined;
    const controller = new AbortController();
    const delay = control || ['pausing', 'cancelling'].includes(state) ? 250 : 1000;
    let timer;
    async function poll() {
      let settled = false;
      try {
        const next = await iptvApi.movieStatus(providerId, { control_only: 1 }, { signal: controller.signal });
        if (controller.signal.aborted) return;
        setError('');
        publish(next);
        settled = (activeStates.includes(state) && !activeStates.includes(next.state)) ||
          (projection === 'running' && next.projection?.state !== 'running');
        if (settled) onSettled();
      } catch (failure) {
        if (!controller.signal.aborted) setError(failure.message);
      } finally {
        if (!controller.signal.aborted && !settled) timer = window.setTimeout(() => poll().catch(() => {}), delay);
      }
    }
    timer = window.setTimeout(() => poll().catch(() => {}), delay);
    return () => { controller.abort(); window.clearTimeout(timer); };
  }, [providerId, enabled, control, state, projection, publish, onSettled]);

  return { worker, publish, error, control, controlError, requestControl,
    current: Boolean(enabled && snapshot?.requestKey === requestKey && !error) };
}
