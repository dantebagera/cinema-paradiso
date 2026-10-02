import { useState } from 'react';
import MovieListsWorkspace from './MovieListsWorkspace.jsx';
import TVListsWorkspace from './TVListsWorkspace.jsx';

export default function ListsWorkspace({ tvEnabled, ...props }) {
  const [media, setMedia] = useState(() => sessionStorage.getItem('cp-lists-media') || 'movie');
  const selected = tvEnabled ? media : 'movie';
  function choose(value) { setMedia(value); sessionStorage.setItem('cp-lists-media', value); }
  return <>
    {tvEnabled && <div className="media-section-tabs lists-media-tabs" role="tablist" aria-label="Lists media">
      <button type="button" role="tab" aria-selected={selected === 'movie'} className={selected === 'movie' ? 'discover-tab-active' : ''} onClick={() => choose('movie')}>Movies</button>
      <button type="button" role="tab" aria-selected={selected === 'tv'} className={selected === 'tv' ? 'discover-tab-active' : ''} onClick={() => choose('tv')}>TV Shows</button>
    </div>}
    <div hidden={selected !== 'movie'}><MovieListsWorkspace {...props} /></div>
    {tvEnabled && <div hidden={selected !== 'tv'}><TVListsWorkspace notify={props.notify} /></div>}
  </>;
}
