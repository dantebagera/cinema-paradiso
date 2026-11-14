import { useEffect, useRef, useState } from 'react';
import { iptvApi } from '../../api/iptv.js';
import { createIPTVPlaybackCoordinator } from './iptvPlaybackSession.js';

const coordinator = createIPTVPlaybackCoordinator(iptvApi);
const empty = { playback: null, loading: false, error: '' };

export default function useIPTVPlaybackSession() {
  const owner = useRef(Symbol('IPTV player'));
  const [state, setState] = useState(empty);
  useEffect(() => {
    const unsubscribe = coordinator.subscribe(() => {
      const next = coordinator.state();
      setState(next.owner === owner.current ? next : empty);
    });
    return () => {
      unsubscribe();
      coordinator.stop(owner.current).catch(() => {});
    };
  }, []);
  return {
    ...state,
    start: (providerId, payload, history) => coordinator.start(owner.current, providerId, payload, history),
    stop: () => coordinator.stop(owner.current),
    stopActive: () => coordinator.stopActive(owner.current),
  };
}
