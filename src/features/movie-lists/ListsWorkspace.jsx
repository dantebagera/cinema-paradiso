import SectionTabs, { SectionTab } from '../../components/ui/SectionTabs.jsx';
import { useId, useLayoutEffect, useRef, useState } from 'react';
import { Clapperboard, Tv } from 'lucide-react';
import MovieListsWorkspace from './MovieListsWorkspace.jsx';
import TVListsWorkspace from './TVListsWorkspace.jsx';

export default function ListsWorkspace({ tvEnabled, ...props }) {
  const [media, setMedia] = useState(() => sessionStorage.getItem('cp-lists-media') || 'movie');
  const selected = tvEnabled ? media : 'movie';
  const id = useId();
  const tabRefs = useRef([]);
  const focusTab = useRef(null);
  useLayoutEffect(() => {
    if (focusTab.current === null) return;
    tabRefs.current[focusTab.current]?.focus();
    focusTab.current = null;
  }, [selected]);
  function choose(value) { setMedia(value); sessionStorage.setItem('cp-lists-media', value); }
  function navigateTabs(event, index) {
    const next = { ArrowLeft: 1 - index, ArrowRight: 1 - index, Home: 0, End: 1 }[event.key];
    if (next == null) return;
    event.preventDefault();
    focusTab.current = next;
    choose(next === 0 ? 'movie' : 'tv');
  }
  const navigation = tvEnabled && <SectionTabs className="lists-media-tabs" role="tablist" aria-label="Lists media">
      {['movie', 'tv'].map((value, index) => <SectionTab
        key={value} ref={(node) => { tabRefs.current[index] = node; }}
        id={`${id}-${value}-tab`} aria-controls={`${id}-${value}-panel`}
        type="button" role="tab" aria-selected={selected === value} tabIndex={selected === value ? 0 : -1}
        className={selected === value ? 'discover-tab-active' : ''}
        onKeyDown={(event) => navigateTabs(event, index)} onClick={() => { focusTab.current = index; choose(value); }}
      >{value === 'movie' ? <Clapperboard size={16}/> : <Tv size={16}/>} {value === 'movie' ? 'Movies' : 'TV Shows'}</SectionTab>)}
    </SectionTabs>;
  return <>
    <div id={`${id}-movie-panel`} role={tvEnabled ? 'tabpanel' : undefined} aria-labelledby={tvEnabled ? `${id}-movie-tab` : undefined} hidden={selected !== 'movie'}><MovieListsWorkspace {...props} mediaNavigation={selected === 'movie' ? navigation : null} /></div>
    {tvEnabled && <div id={`${id}-tv-panel`} role="tabpanel" aria-labelledby={`${id}-tv-tab`} hidden={selected !== 'tv'}><TVListsWorkspace notify={props.notify} onBrowseTV={props.onBrowseTV} mediaNavigation={selected === 'tv' ? navigation : null} /></div>}
  </>;
}
