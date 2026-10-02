import { cloneElement, lazy, Suspense, useEffect, useRef, useState } from 'react';
import { Bot, Clapperboard, Compass, Radio, Tv } from 'lucide-react';
const TVWorkspace = lazy(() => import('./TVWorkspace.jsx'));

export default function MediaWorkspace({ enabled, context, children, discoverTab = 'explore', onDiscoverTabChange, movieRequestId, ...props }) {
  const [media, setMedia] = useState(() => window.location.pathname.startsWith('/tv/series/') ? 'tv' : sessionStorage.getItem(`cp-${context}-media`) || 'movie');
  const [mounted, setMounted] = useState(media === 'tv');
  const scrollPositions = useRef({ movie: 0, tv: 0 });
  useEffect(() => { const pop = () => { if (window.location.pathname.startsWith('/tv/series/')) { setMedia('tv'); setMounted(true); } }; window.addEventListener('popstate', pop); return () => window.removeEventListener('popstate', pop); }, []);
  useEffect(() => {
    if (context !== 'discover' || !movieRequestId) return;
    setMedia('movie');
    sessionStorage.setItem('cp-discover-media', 'movie');
  }, [context, movieRequestId]);
  if (!enabled) return children;
  function selectMedia(value) {
    const workspace = document.querySelector('main.workspace');
    if (workspace) scrollPositions.current[media] = workspace.scrollTop;
    setMedia(value);
    if (value === 'tv') setMounted(true);
    sessionStorage.setItem(`cp-${context}-media`, value);
    requestAnimationFrame(() => { if (workspace) workspace.scrollTop = scrollPositions.current[value] || 0; });
  }
  const entries = context === 'discover'
    ? [
      { id: 'explore', label: 'Explore Movies', icon: Compass, media: 'movie' },
      { id: 'shows', label: 'Explore Shows', icon: Tv, media: 'tv' },
      { id: 'browse', label: 'Browse Indexers', icon: Radio, media: 'movie' },
      { id: 'pick', label: 'Pick My Movie', icon: Bot, media: 'movie' }
    ]
    : [
      { id: 'movie', label: 'Movies', icon: Clapperboard, media: 'movie' },
      { id: 'tv', label: 'TV Shows', icon: Tv, media: 'tv' }
    ];
  const navigation = <div className={`discover-tabs media-section-tabs media-section-tabs-${context}`} role="tablist" aria-label={context === 'discover' ? 'Discover tools' : 'Library media'}>
    {entries.map(({ id, label, icon: Icon, media: target }) => <button
      type="button" key={id} aria-pressed={media === target && (context !== 'discover' || discoverTab === id || target === 'tv')}
      className={media === target && (context !== 'discover' || discoverTab === id || target === 'tv') ? 'discover-tab-active' : ''}
      onClick={() => { if (context === 'discover' && target === 'movie') onDiscoverTabChange?.(id); selectMedia(target); }}
    ><Icon size={16} /> {label}</button>)}
  </div>;
  return <>
    <div hidden={media !== 'movie'}>{cloneElement(children, { mediaNavigation: navigation })}</div>
    {mounted && <div hidden={media !== 'tv'}><Suspense fallback={<div role="status">Loading TV…</div>}><TVWorkspace context={context} mediaNavigation={navigation} {...props} /></Suspense></div>}
  </>;
}
