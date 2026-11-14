import Button from './ui/Button.jsx';
import { useContext, useEffect, useRef, useState } from 'react';
import { Film } from 'lucide-react';
import { fetchRelationshipPage, fetchTvRelationshipPage } from '../api/movieRelationships.js';
import { CATALOG_GENERATION_CHANGED_EVENT, fetchOwnershipChecks } from '../api/library.js';
import { MovieRelationshipNavigation } from './MovieRelationshipNavigation.jsx';
import { useMediaCardArtwork, useMediaPosterSource, usePrioritizedCardPoster } from './movie-card/cardArtwork.js';
import Tooltip from './Tooltip.jsx';
import { movieDisplayTitle } from '../utils/movieLanguage.js';
import HorizontalCardRail from './HorizontalCardRail.jsx';

export default function RelatedMovieRail({ movie, mediaType = 'movie', onNavigate, onViewAll }) {
  const navigate = useContext(MovieRelationshipNavigation);
  const [source, setSource] = useState('recommendations');
  const [state, setState] = useState({ loading: true, results: [] });
  const [owned, setOwned] = useState(new Set());
  const [retry, setRetry] = useState(0);
  const id = movie?.tmdb_id;
  const isTv = mediaType === 'tv';
  const emptyMessage = `No ${isTv ? 'series' : 'movies'} from this TMDB source yet.`;
  const canNavigate = isTv ? Boolean(onNavigate) : Boolean(navigate);
  const viewAll = () => isTv ? onViewAll?.({ source: 'all' }) : navigate?.(movie, null, { source: 'all' });
  const openItem = (item) => isTv ? onNavigate?.(item, { source }) : navigate?.(movie, item, { source });
  useEffect(() => {
    let cancelled = false;
    setState({ loading: true, results: [] });
    if (!id) { setState({ results: [], error: `Match this ${isTv ? 'series' : 'movie'} to TMDB to see related ${isTv ? 'series' : 'movies'}.` }); return; }
    (isTv ? fetchTvRelationshipPage : fetchRelationshipPage)(id, source).then((data) => {
      if (!cancelled) setState({ results: data.results || [] });
    }).catch((error) => { if (!cancelled) setState({ results: [], error: error.message }); });
    return () => { cancelled = true; };
  }, [id, source, retry, isTv]);
  useEffect(() => {
    let cancelled = false;
    if (isTv) {
      setOwned(new Set(state.results.filter((item) => item.available_count > 0).map((item) => String(item.tmdb_id))));
      return;
    }
    async function refresh() {
      try {
        const checks = await fetchOwnershipChecks(state.results);
        if (!cancelled) setOwned(new Set(checks.filter((item) => item.found).map((item) => String(item.tmdb_id))));
      } catch { /* Ownership failure must not remove relationship results. */ }
    }
    setOwned(new Set());
    refresh();
    window.addEventListener(CATALOG_GENERATION_CHANGED_EVENT, refresh);
    return () => { cancelled = true; window.removeEventListener(CATALOG_GENERATION_CHANGED_EVENT, refresh); };
  }, [state.results, isTv]);
  return (
    <section className="related-movie-rail" aria-label="More like this" aria-busy={state.loading || undefined}>
      <HorizontalCardRail label="related titles" trackClassName="related-movie-tiles" arrowPlacement="edges" visibleCount={1} minCardWidth={104}
        cardWidth={state.loading || state.results.length ? 'calc(var(--related-poster-height) * 2 / 3)' : undefined} resetKey={`${id}-${source}-${retry}`}
        header={<>
        <span className="mini-label">MORE LIKE THIS</span>
        <div className="related-source-selector" aria-label="Relationship source">
          {[['recommendations', 'Recommended'], ['similar', 'Similar']].map(([value, label]) => (
            <button type="button" key={value} aria-pressed={source === value} onClick={() => setSource(value)}>{label}</button>
          ))}
        </div>
        <Button size="compact" type="button"  disabled={!id || !(isTv ? onViewAll : canNavigate)} onClick={viewAll}>View all</Button>
      </>}>
        {state.loading ? Array.from({ length: 20 }, (_, index) => <div className="related-tile related-skeleton" key={index} />) :
          state.results.map((item) => (
            <RelatedMovieTile key={item.tmdb_id} item={item} owned={owned.has(String(item.tmdb_id))} isTv={isTv} onOpen={() => openItem(item)} />
          ))}
        {!state.loading && !state.results.length && <p className="related-message" role="status">{state.error || emptyMessage} {id && state.error && <Button size="compact" type="button"  onClick={() => setRetry((value) => value + 1)}>Retry</Button>}</p>}
      </HorizontalCardRail>
    </section>
  );
}

function RelatedMovieTile({ item, owned, isTv, onOpen }) {
  const cardRef = useRef(null);
  const posterRef = useRef(null);
  const imageRef = useRef(null);
  const artworkStyle = useMediaCardArtwork(cardRef, item.backdrop_url, item.poster_url);
  const posterSource = useMediaPosterSource(posterRef, item.poster_url);
  usePrioritizedCardPoster(posterRef, imageRef, item.poster_url);
  const title = isTv ? item.title : movieDisplayTitle(item);
  return <Tooltip title={title} description={item.year || 'Year unavailable'}>
    <button ref={cardRef} type="button" className="related-tile" style={artworkStyle} onClick={onOpen} aria-label={`Open ${title} ${isTv ? 'TV series' : 'in Discover'}`}>
      <span ref={posterRef} className="related-poster">{item.poster_url ? <img ref={imageRef} src={posterSource} alt="" loading="lazy" fetchPriority="high" /> : <Film size={24} />}</span>
      <span className="related-rating" aria-label={`Rating ${item.tmdb_rating || 'unavailable'}`}>★ {item.tmdb_rating || '—'}</span>
      {owned && <span className="related-owned">Owned</span>}
    </button>
  </Tooltip>;
}
