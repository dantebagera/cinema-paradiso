import { useEffect, useState } from 'react';
import { getMovieAvailability } from '../api/iptvAvailability.js';

export default function useIPTVMovieAvailability(movieIds, enabled = true) {
  const key = [...new Set(movieIds.map(Number).filter(id => Number.isInteger(id) && id > 0))].join(',');
  const [state, setState] = useState({ key: '', providers: [], loading: false, error: '' });
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const invalidate = () => setRevision(value => value + 1);
    window.addEventListener('cp-iptv-catalog-changed', invalidate);
    return () => window.removeEventListener('cp-iptv-catalog-changed', invalidate);
  }, []);
  useEffect(() => {
    if (!enabled || !key) return undefined;
    const controller = new AbortController();
    async function refresh() {
      if (document.hidden) return;
      setState(previous => ({ ...(previous.key === key ? previous : { providers: [] }), key, loading: true, error: '' }));
      try {
        const data = await getMovieAvailability(key.split(',').map(Number), { signal: controller.signal });
        if (!controller.signal.aborted) setState({ key, ...data, loading: false, error: '' });
      } catch (error) {
        if (!controller.signal.aborted) setState({ key, providers: [], loading: false, error: error.message });
      }
    }
    refresh();
    const timer = window.setInterval(refresh, 15000);
    document.addEventListener('visibilitychange', refresh);
    return () => {
      controller.abort();
      window.clearInterval(timer);
      document.removeEventListener('visibilitychange', refresh);
    };
  }, [key, enabled, revision]);
  return state.key === key ? state : { providers: [], loading: enabled && Boolean(key), error: '' };
}
