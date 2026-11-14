import {createContext, useContext, useEffect, useMemo, useSyncExternalStore, useCallback, useRef} from 'react';
import {CardPosterPriority, isPosterInViewport} from '../components/movie-card/cardArtwork.js';
import {createMovieRatingsClient, ratingsIdentity} from '../api/movieRatings.js';

const Context=createContext(null);
const empty=()=>null;
const noop=()=>()=>{};

export function MovieRatingsProvider({children}) {
  const priority=useContext(CardPosterPriority);
  const owner=useMemo(()=>{
    let pausedUntil=0;
    const visible=new Map();
    const pendingSubscriptions=new Set();
    const eligible=()=>document.visibilityState!=='hidden'&&Date.now()>=pausedUntil&&Boolean(priority?.isDeferredReady());
    const idle=callback=>{
      let called=false;
      const once=()=>{if(!called){called=true;callback();}};
      if(window.requestIdleCallback)window.requestIdleCallback(once);
      else setTimeout(once,250);
    };
    const client=createMovieRatingsClient({
      eligible,idle
    });
    let activationScheduled=false;
    const result={client,visible,pendingSubscriptions,mounts:0,pause:()=>{pausedUntil=Date.now()+150;}};
    result.activate=()=>{
      if(activationScheduled||!pendingSubscriptions.size)return;
      activationScheduled=true;
      idle(()=>{
        activationScheduled=false;
        if(!result.mounts||!eligible())return;
        for(const start of pendingSubscriptions)start();
        pendingSubscriptions.clear();
      });
    };
    return result;
  },[priority]);
  useEffect(()=>{
    owner.mounts++;
    let resume;
    const observer=typeof IntersectionObserver!=='undefined'?new IntersectionObserver(entries=>{
      for(const entry of entries) owner.visible.set(entry.target,entry.isIntersecting);
      owner.client.revisit();
    }):null;
    owner.observer=observer;
    const wake=()=>{owner.activate();owner.client.wake();};
    const pause=()=>{owner.pause();clearTimeout(resume);resume=setTimeout(wake,160);};
    const invalidate=()=>owner.client.invalidate();
    const revisit=()=>{owner.activate();owner.client.revisit();};
    const ownership=event=>owner.client.refresh((event.detail?.identities||[]).map(ratingsIdentity));
    const unsub=priority?.subscribeDeferredReady(wake);
    owner.activate();
    for(const event of ['scroll','pointerdown','keydown','popstate']) window.addEventListener(event,pause,{capture:true,passive:true});
    for(const event of ['cp-library-changed','cp-catalog-generation-changed','cp-ratings-config-changed']) window.addEventListener(event,invalidate);
    window.addEventListener('focus',revisit);
    window.addEventListener('cp-ownership-resolved',ownership);
    document.addEventListener('visibilitychange',revisit);
    return ()=>{
      clearTimeout(resume);observer?.disconnect();unsub?.();
      for(const event of ['scroll','pointerdown','keydown','popstate']) window.removeEventListener(event,pause,true);
      for(const event of ['cp-library-changed','cp-catalog-generation-changed','cp-ratings-config-changed']) window.removeEventListener(event,invalidate);
      window.removeEventListener('focus',revisit);document.removeEventListener('visibilitychange',revisit);
      window.removeEventListener('cp-ownership-resolved',ownership);
      // StrictMode replays effects on this same owner; invalidate, don't destroy it.
      owner.client.invalidate();
      owner.mounts--;
      queueMicrotask(()=>{if(!owner.mounts)owner.client.destroy();});
    };
  },[owner,priority]);
  return <Context.Provider value={owner}>{children}</Context.Provider>;
}

export function useMovieRatings(identity, elementRef, expanded) {
  const owner=useContext(Context);
  const signature=JSON.stringify(ratingsIdentity(identity));
  const normalized=useMemo(()=>JSON.parse(signature),[signature]);
  const active=useRef(null);
  const subscribe=useCallback(listener=>{
    const element=elementRef.current;
    if(!owner||!normalized||!element) return ()=>{};
    // Even cache registration and observation wait behind posters and idle input.
    let stop;
    const subscription={signature};
    const start=()=>{
      owner.observer?.observe(element);
      active.current=subscription;
      stop=owner.client.subscribe(normalized,()=>owner.visible.get(element)!==false&&isPosterInViewport(element),listener,expanded);
      listener(); // A duplicate card may already have a cached snapshot.
    };
    owner.pendingSubscriptions.add(start);
    owner.activate();
    listener(); // Pending cards cannot display a cache value without invalidation notifications.
    return ()=>{if(active.current===subscription)active.current=null;owner.pendingSubscriptions.delete(start);owner.observer?.unobserve(element);owner.visible.delete(element);stop?.();};
  },[owner,normalized,signature,elementRef,expanded]);
  const snapshot=useCallback(()=>active.current?.signature===signature?(owner?.client.get(normalized?.key,normalized)||null):null,[owner,normalized,signature]);
  return useSyncExternalStore(owner&&normalized?subscribe:noop,snapshot,empty);
}
