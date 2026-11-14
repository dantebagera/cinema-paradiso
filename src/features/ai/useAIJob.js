import { useCallback, useEffect, useRef, useState } from 'react';
import { fetchJson } from '../../api/client.js';
import { useAIProvider } from './AIProviderContext.jsx';
import { aiJson, jobIsRunning, jobStorageKey, requestKey } from './aiClient.js';

export default function useAIJob(feature, providerId = '', { latestEndpoint, recoverStatus = false, enabled = true } = {}) {
  const { config } = useAIProvider();
  const account = config?.chatgpt?.active_account_id;
  const storageKey = jobStorageKey(feature, account, providerId);
  const [job, setJob] = useState(null);
  const [error, setError] = useState('');
  const clearError = useCallback(expectedMessage => {
    setError(currentError => currentError === expectedMessage ? '' : currentError);
  }, []);
  const [busy, setBusy] = useState(false);
  const [page, setPage] = useState(1);
  const [reviewView, setReviewView] = useState('pending_matches');
  const [status, setStatus] = useState({ state: 'loading', lastAt: null });
  const [refresh, setRefresh] = useState(0);
  const generation = useRef(0);
  const uncertainAction = useRef(null);
  const current = useRef(null);
  current.current = job;
  const remember = useCallback(next => {
    setJob(previous => previous?.id === next.id && previous.revision > next.revision ? previous : next);
    if (!recoverStatus) setError('');
    localStorage.setItem(storageKey, JSON.stringify({ id: next.id, session_id: next.session_id }));
    return next;
  }, [storageKey, recoverStatus]);

  useEffect(() => {
    generation.current += 1;
    const stamp = generation.current;
    uncertainAction.current = null;
    setJob(null); setError(''); setPage(1); setBusy(false);
    setReviewView('pending_matches');
    setStatus({ state: account && enabled ? 'loading' : 'idle', lastAt: null });
    if (!account || !enabled || recoverStatus) return () => { generation.current += 1; };
    let lookup;
    if (latestEndpoint) {
      lookup = fetchJson(latestEndpoint).then(data => data.job);
    } else {
      let saved;
      try { saved = JSON.parse(localStorage.getItem(storageKey) || 'null'); } catch { return undefined; }
      if (saved?.id) lookup = fetchJson(`/api/ai/jobs/${encodeURIComponent(saved.id)}`);
    }
    lookup?.then(next => {
      if (next && generation.current === stamp) remember(next);
    }).catch(failure => { if (generation.current === stamp) setError(failure.message); });
    return () => { generation.current += 1; };
  }, [account, storageKey, remember, latestEndpoint, recoverStatus, enabled]);

  useEffect(() => {
    if (recoverStatus || !job?.id || !account || !enabled) return undefined;
    let cancelled = false;
    const stamp = generation.current;
    let timer;
    async function poll() {
      try {
        const next = await fetchJson(`/api/ai/jobs/${encodeURIComponent(job.id)}?page=${page}`);
        if (cancelled || generation.current !== stamp) return;
        remember(next);
        if (jobIsRunning(next)) timer = window.setTimeout(poll, 800);
      } catch (failure) { if (!cancelled && generation.current === stamp) setError(failure.message); }
    }
    poll();
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [job?.id, job?.state, account, page, remember, recoverStatus, enabled]);

  const scopedJob = job?.selection?.account_id === account && job?.selection?.domain_id === providerId ? job : null;
  useEffect(() => {
    if (!recoverStatus || !account || !enabled || !latestEndpoint) return undefined;
    const stamp = generation.current;
    const jobId = scopedJob?.id;
    const query = new URLSearchParams({ page, review_view: reviewView });
    const endpoint = jobId ? `/api/ai/jobs/${encodeURIComponent(jobId)}` : latestEndpoint;
    let closed = false;
    let timer;
    let controller;
    let delay = 1000;
    const stale = () => closed || generation.current !== stamp;

    async function poll() {
      controller = new AbortController();
      const timeout = window.setTimeout(() => controller.abort(), 8000);
      try {
        const response = await fetchJson(`${endpoint}?${query}`, { signal: controller.signal });
        if (stale()) return;
        const next = jobId ? response : response.job;
        if (!next || current.current?.id !== next.id || current.current.revision <= next.revision) {
          if (next) remember(next);
          const before = uncertainAction.current;
          if (before) {
            uncertainAction.current = null;
            setError(next && (next.id !== before.id || next.revision > before.revision) ? '' :
              'The action response was lost. Check the current job before trying again.');
          }
          setStatus({ state: 'ready', lastAt: Date.now() });
          delay = 1000;
        }
        if (jobIsRunning(next) || ['running', 'stopping'].includes(next?.bulk?.apply?.state) ||
            (next?.state === 'cancelled' && next?.bulk?.recovery?.in_flight) ||
            (next && current.current?.revision > next.revision)) {
          timer = window.setTimeout(poll, 800);
        }
      } catch (failure) {
        if (stale()) return;
        const code = failure.status;
        const retryable = !code || code === 408 || code === 429 || code >= 500;
        setStatus(previous => ({ ...previous, state: retryable ? 'reconnecting' : 'unavailable',
          message: code === 401 || code === 403 ? 'Reconnect the ChatGPT account that owns this IPTV job.' :
            code === 404 ? 'This IPTV job is no longer available. Reopen Metadata to check for the latest job.' : failure.message }));
        if (retryable) {
          timer = window.setTimeout(poll, delay);
          delay = Math.min(delay * 2, 8000);
        }
      } finally {
        window.clearTimeout(timeout);
      }
    }
    poll();
    return () => { closed = true; controller?.abort(); window.clearTimeout(timer); };
  }, [recoverStatus, account, enabled, latestEndpoint, scopedJob?.id, page, reviewView, refresh, remember]);

  const start = useCallback(async (endpoint, body, { followUp = true } = {}) => {
    const previous = current.current;
    const stamp = ++generation.current;
    uncertainAction.current = null;
    setBusy(true); setError(''); setPage(1);
    if (!recoverStatus) setJob(null);
    try {
      const next = await aiJson(endpoint, { ...body, request_key: requestKey(),
        ...(followUp && previous?.session_id ? { session_id: previous.session_id } : {}) });
      if (generation.current === stamp) remember(next);
      return next;
    } catch (failure) {
      if (generation.current === stamp) {
        if (recoverStatus && (!failure.status || failure.status >= 500)) {
          uncertainAction.current = { id: previous?.id, revision: previous?.revision };
        } else {
          setError(failure.message);
        }
        // A lost Start reply can hide a newly accepted job behind the previous job ID.
        if (recoverStatus) setJob(null);
      }
      throw failure;
    }
    finally {
      if (generation.current === stamp) {
        setBusy(false);
        if (recoverStatus) refreshStatus();
      }
    }
  }, [remember, recoverStatus]);

  function refreshStatus() {
    setStatus(previous => ({ ...previous, state: 'loading' }));
    setRefresh(value => value + 1);
  }

  async function mutate(endpoint, body, { rememberJob = false } = {}) {
    const stamp = generation.current;
    const previous = current.current;
    uncertainAction.current = null;
    setBusy(true); setError('');
    try {
      const next = await aiJson(endpoint, body);
      if (rememberJob && generation.current === stamp) remember(next);
      return next;
    } catch (failure) {
      if (generation.current === stamp) {
        if (!failure.status || failure.status >= 500) {
          uncertainAction.current = { id: previous?.id, revision: previous?.revision };
        } else {
          setError(failure.message);
        }
      }
      throw failure;
    } finally {
      if (generation.current === stamp) {
        setBusy(false);
        refreshStatus();
      }
    }
  }

  async function jobAction(action, body) {
    const endpoint = `/api/ai/jobs/${job.id}/${action}`;
    if (recoverStatus) {
      await mutate(endpoint, body, { rememberJob: true }).catch(() => {});
      return;
    }
    const stamp = generation.current;
    setBusy(true); setError('');
    try {
      const next = await aiJson(endpoint, body);
      if (generation.current === stamp) remember(next);
    } catch (failure) { if (generation.current === stamp) setError(failure.message); }
    finally { if (generation.current === stamp) setBusy(false); }
  }
  function continueJob(extraCalls) {
    setPage(1);
    return jobAction('continue', { revision: job.revision, request_key: requestKey(),
      ...(job.bulk && typeof extraCalls === 'number' ? { extra_calls: extraCalls } : {}) });
  }
  function pause() { return jobAction('pause', { run_number: job.cursor?.run_number ?? 0 }); }
  function cancel() { return jobAction('cancel', { revision: job.revision, run_number: job.cursor?.run_number ?? 0 }); }
  function newSession() { generation.current += 1; current.current = null; localStorage.removeItem(storageKey); setJob(null); setError(''); setPage(1); }
  async function reload() {
    const stamp = generation.current;
    if (current.current?.id) {
      const next = await fetchJson(`/api/ai/jobs/${current.current.id}?page=${page}`);
      if (generation.current === stamp) remember(next);
    }
  }
  async function attach(id) { remember(await fetchJson(`/api/ai/jobs/${encodeURIComponent(id)}`)); }
  return { job: recoverStatus ? scopedJob : job, error, busy, start, cancel, pause, continueJob, newSession,
    reload, attach, setPage, page, status, reviewView, setReviewView, mutate, clearError };
}
