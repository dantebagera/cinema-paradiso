import { createContext, useContext, useEffect, useRef, useSyncExternalStore } from 'react';
import { createAwardsCache, movieAwardCounts, personAwardCounts } from '../api/movieAwards.js';

const Context = createContext(null);
const inert = { getSnapshot:() => null, subscribe:() => () => {}, acquire:() => () => {} };

export function MovieAwardsProvider({children}) {
  const cache = useRef(null);
  if (!cache.current) cache.current = createAwardsCache({visible:() => document.visibilityState === 'visible' &&
    Array.from(document.querySelectorAll('.movie-awards-consumer')).some(card => card.getClientRects().length && !card.closest('[hidden]'))});
  useEffect(() => {
    const focus = () => cache.current.focus();
    const timer = window.setInterval(focus,300000);
    window.addEventListener('focus',focus);
    document.addEventListener('visibilitychange',focus);
    // A workspace switch can expose consumers without a window focus event.
    const observer = new MutationObserver(focus);
    observer.observe(document.getElementById('root'),{subtree:true,attributes:true,attributeFilter:['hidden']});
    return () => {clearInterval(timer);window.removeEventListener('focus',focus);document.removeEventListener('visibilitychange',focus);observer.disconnect();};
  },[]);
  return <Context.Provider value={cache.current}>{children}</Context.Provider>;
}

function useSnapshot(enabled) {
  const cache = useContext(Context) || inert;
  useEffect(() => cache.acquire(enabled),[cache,enabled]);
  return useSyncExternalStore(cache.subscribe,cache.getSnapshot,cache.getSnapshot);
}
export function useMovieAwardCounts(movie,{enabled=false}={}) { return movieAwardCounts(useSnapshot(enabled),movie,enabled); }
export function usePersonAwardCounts(personId,role,{enabled=false}={}) { return personAwardCounts(useSnapshot(enabled),personId,role,enabled); }
