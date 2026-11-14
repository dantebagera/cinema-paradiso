import { createContext, useContext, useEffect, useLayoutEffect, useState } from 'react';

const pendingArtwork = new Map();
let artworkObserver;

export const CardPosterPriority = createContext(null);

export function isPosterInViewport(element) {
  const rect = element.getBoundingClientRect();
  const workspace = element.closest('main.workspace')?.getBoundingClientRect();
  const rail = element.closest('.horizontal-card-rail-track')?.getBoundingClientRect();
  return rect.width > 0 && rect.height > 0 &&
    rect.left < Math.min(window.innerWidth, workspace?.right ?? Infinity, rail?.right ?? Infinity) &&
    rect.right > Math.max(0, workspace?.left ?? 0, rail?.left ?? 0) &&
    rect.top < Math.min(window.innerHeight, workspace?.bottom ?? Infinity, rail?.bottom ?? Infinity) &&
    rect.bottom > Math.max(0, workspace?.top ?? 0, rail?.top ?? 0);
}

export function createCardPosterPriority() {
  const posters = new Map();
  const pending = new Set();
  const backdrops = new Map();
  const deferredListeners = new Set();
  let viewportObserver;
  let flushScheduled = false;

  function scheduleBackdrops() {
    if (flushScheduled || pending.size || (!backdrops.size && !deferredListeners.size)) return;
    flushScheduled = true;
    requestAnimationFrame(() => {
      flushScheduled = false;
      if (pending.size) return;
      // Scroll can change the viewport before its observer callback runs.
      for (const [element, poster] of posters) {
        if (!poster.settled && isPosterInViewport(element)) return;
      }
      for (const [start, element] of backdrops) {
        if (!element.getClientRects().length) continue;
        backdrops.delete(start);
        start();
      }
      for (const listener of deferredListeners) listener();
    });
  }

  function observeViewport(entries) {
    for (const entry of entries) {
      const poster = posters.get(entry.target);
      if (!poster || entry.time < poster.startedAt) continue;
      if (entry.isIntersecting) {
        if (!poster.settled) pending.add(entry.target);
      } else {
        pending.delete(entry.target);
      }
    }
    scheduleBackdrops();
  }

  return {
    isDeferredReady() {
      if (flushScheduled || pending.size) return false;
      for (const [element, poster] of posters) if (!poster.settled && isPosterInViewport(element)) return false;
      for (const element of backdrops.values()) if (isPosterInViewport(element)) return false;
      return true;
    },
    subscribeDeferredReady(listener) {
      deferredListeners.add(listener);
      scheduleBackdrops();
      return () => deferredListeners.delete(listener);
    },
    watchPoster(element, image, url) {
      viewportObserver ??= new IntersectionObserver(observeViewport);
      const poster = {
        startedAt: performance.now(),
        settled: image.getAttribute('src') === url && image.complete
      };
      const settle = () => {
        if (image.getAttribute('src') !== url || !image.complete) return;
        poster.settled = true;
        pending.delete(element);
        scheduleBackdrops();
      };
      posters.set(element, poster);
      if (!poster.settled) pending.add(element);
      image.addEventListener('load', settle);
      image.addEventListener('error', settle);
      viewportObserver.observe(element);
      return () => {
        image.removeEventListener('load', settle);
        image.removeEventListener('error', settle);
        viewportObserver.unobserve(element);
        posters.delete(element);
        pending.delete(element);
        if (!posters.size) {
          viewportObserver.disconnect();
          viewportObserver = undefined;
        }
        scheduleBackdrops();
      };
    },
    afterVisiblePosters(element, start) {
      backdrops.set(start, element);
      scheduleBackdrops();
      return () => backdrops.delete(start);
    }
  };
}

export function usePrioritizedCardPoster(posterRef, imageRef, url) {
  const priority = useContext(CardPosterPriority);
  useLayoutEffect(() => {
    if (priority && typeof IntersectionObserver !== 'undefined' && url && imageRef.current) {
      return priority.watchPoster(posterRef.current, imageRef.current, url);
    }
  }, [priority, posterRef, imageRef, url]);
}

function stopObservingArtwork(element, registration) {
  if (pendingArtwork.get(element) !== registration) return;
  pendingArtwork.delete(element);
  registration.observer.unobserve(element);
  if (!pendingArtwork.size && artworkObserver === registration.observer) {
    registration.observer.disconnect();
    artworkObserver = undefined;
  }
}

function observeArtwork(element, activate, deactivate) {
  artworkObserver ??= new IntersectionObserver((entries, observer) => {
    for (const entry of entries) {
      const registration = pendingArtwork.get(entry.target);
      // Queued entries can outlive a URL change or a disconnected observer.
      // An earlier notification must not activate the card's replacement URL.
      if (!registration || registration.observer !== observer || entry.time < registration.startedAt) continue;
      if (!entry.isIntersecting) {
        registration.deactivate?.();
        continue;
      }
      if (!registration.deactivate) stopObservingArtwork(entry.target, registration);
      registration.activate();
    }
  }, { rootMargin: '200px' });
  const registration = { activate, deactivate, observer: artworkObserver, startedAt: performance.now() };
  pendingArtwork.set(element, registration);
  registration.observer.observe(element);
  return () => stopObservingArtwork(element, registration);
}

// Share visibility and replacement handling for supplied card images. Keep loaded
// URLs on later scrolls; a replacement URL earns a new visibility check.
function useArtworkReady(elementRef, artworkUrl, eager, defer) {
  const [activatedUrl, setActivatedUrl] = useState(null);
  useEffect(() => {
    if (!artworkUrl || activatedUrl === artworkUrl) return;
    if (eager) {
      setActivatedUrl(artworkUrl);
      return;
    }
    const element = elementRef.current;
    if (!element) return;
    let cancelDeferred;
    const activate = () => {
      unobserve();
      setActivatedUrl(artworkUrl);
    };
    const unobserve = observeArtwork(element, () => {
      if (defer) cancelDeferred = defer(element, activate);
      else activate();
    }, defer && (() => cancelDeferred?.()));
    return () => {
      unobserve();
      cancelDeferred?.();
    };
  }, [elementRef, artworkUrl, activatedUrl, eager, defer]);
  return eager || activatedUrl === artworkUrl;
}

export function useMediaCardArtwork(cardRef, backdropUrl, posterUrl, expanded = false) {
  const priority = useContext(CardPosterPriority);
  const eager = expanded || typeof IntersectionObserver === 'undefined';
  const defer = backdropUrl && backdropUrl !== posterUrl ? priority?.afterVisiblePosters : undefined;
  const ready = useArtworkReady(cardRef, backdropUrl || posterUrl, eager, defer);
  return ready
    ? mediaCardArtworkStyle(backdropUrl, posterUrl, expanded)
    : undefined;
}

// Native lazy images can fetch several screens ahead. Use the card artwork's
// visibility owner so distant posters do not compete with the first visible ones.
export function useMediaPosterSource(posterRef, posterUrl, expanded = false) {
  const eager = expanded || /^(data:|blob:)/i.test(posterUrl || '') || typeof IntersectionObserver === 'undefined';
  return useArtworkReady(posterRef, posterUrl, eager) ? posterUrl : undefined;
}

// Reuse artwork already supplied with the card; never fetch detail metadata for styling.
export function mediaCardArtworkStyle(backdropUrl, posterUrl, expanded = false) {
  const artworkUrl = backdropUrl || posterUrl;
  if (!artworkUrl) return undefined;
  return {
    backgroundImage: `linear-gradient(90deg, #111 30%, ${expanded ? '#1119' : '#111111b3'}), url(${JSON.stringify(artworkUrl)})`,
    backgroundSize: 'cover',
    backgroundPosition: 'center',
    backgroundRepeat: 'no-repeat',
    backgroundClip: 'padding-box',
    backgroundColor: '#111'
  };
}
