import SectionTabs, { SectionTab } from '../../components/ui/SectionTabs.jsx';
import { cloneElement, useEffect, useRef, useState } from 'react';
import { Bot, Clapperboard, Compass, Radio, Tv } from 'lucide-react';
import TVWorkspace from './TVWorkspace.jsx';

export default function MediaWorkspace({ enabled, context, children, discoverTab = 'explore', onDiscoverTabChange, movieRequestId, mediaRequest, ...props }) {
  const [media, setMedia] = useState(() => window.location.pathname.startsWith('/tv/series/') ? 'tv' : sessionStorage.getItem(`cp-${context}-media`) || 'movie');
  const [mounted, setMounted] = useState(media === 'tv');
  const scrollPositions = useRef({ movie: 0, tv: 0 });
  useEffect(() => { const pop = () => { if (window.location.pathname.startsWith('/tv/series/') || window.history.state?.tvContext === context) { setMedia('tv'); setMounted(true); } }; window.addEventListener('popstate', pop); return () => window.removeEventListener('popstate', pop); }, [context]);
  useEffect(() => {
    if (context !== 'discover' || !movieRequestId) return;
    setMedia('movie');
    sessionStorage.setItem('cp-discover-media', 'movie');
  }, [context, movieRequestId]);
  useEffect(() => {
    if (context !== 'discover' || !mediaRequest) return;
    setMedia(mediaRequest.media);
    if (mediaRequest.media === 'tv') setMounted(true);
    sessionStorage.setItem('cp-discover-media', mediaRequest.media);
  }, [context, mediaRequest]);
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
      { id: 'explore', label: 'Movies', icon: Compass, media: 'movie' },
      { id: 'shows', label: 'TV Shows', icon: Tv, media: 'tv' },
      { id: 'browse', label: 'Browse Indexers', icon: Radio, media: 'movie' },
      { id: 'pick', label: 'Pick My Movie', icon: Bot, media: 'movie' }
    ]
    : [
      { id: 'movie', label: 'Movies', icon: Clapperboard, media: 'movie' },
      { id: 'tv', label: 'TV Shows', icon: Tv, media: 'tv' }
    ];
  const navigation = <SectionTabs className={`media-section-tabs-${context}`} role="tablist" aria-label={context === 'discover' ? 'Discover tools' : 'Library media'}>
    {entries.map(({ id, label, icon: Icon, media: target }) => <SectionTab
      type="button" key={id} aria-pressed={media === target && (context !== 'discover' || discoverTab === id || target === 'tv')}
      className={media === target && (context !== 'discover' || discoverTab === id || target === 'tv') ? 'discover-tab-active' : ''}
      onClick={() => { if (context === 'discover' && target === 'movie') onDiscoverTabChange?.(id); selectMedia(target); }}
    ><Icon size={16} /> {label}</SectionTab>)}
  </SectionTabs>;
  return <>
    <div className="media-workspace-panel" hidden={media !== 'movie'}>{cloneElement(children, { mediaNavigation: navigation, ...(context === 'discover' ? { active: children.props.active !== false && media === 'movie' } : {}) })}</div>
    {mounted && <div className="media-workspace-panel" hidden={media !== 'tv'}><TVWorkspace context={context} mediaNavigation={navigation} {...props} /></div>}
  </>;
}
