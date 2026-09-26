import { useContext, useEffect, useState } from 'react';
import { Film } from 'lucide-react';
import { fetchRelationshipPage, fetchTvRelationshipPage } from '../api/movieRelationships.js';
import { CATALOG_GENERATION_CHANGED_EVENT, fetchOwnershipChecks } from '../api/library.js';
import { MovieRelationshipNavigation } from './MovieRelationshipNavigation.jsx';

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
      if (!cancelled) setState({ results: (data.results || []).slice(0, 16) });
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
      <header>
        <span className="mini-label">MORE LIKE THIS</span>
        <div className="related-source-selector" aria-label="Relationship source">
          {[['recommendations', 'Recommended'], ['similar', 'Similar']].map(([value, label]) => (
            <button type="button" key={value} aria-pressed={source === value} onClick={() => setSource(value)}>{label}</button>
          ))}
        </div>
        {!state.loading && !state.results.length ? (
          <span className="related-compact-status" role="status">
            {state.error || emptyMessage}
            {id && state.error ? <button type="button" className="mini-action" onClick={() => setRetry((value) => value + 1)}>Retry</button> : null}
          </span>
        ) : null}
        <button type="button" className="mini-action" disabled={!id || !(isTv ? onViewAll : canNavigate)} onClick={viewAll}>View all</button>
      </header>
      <div className="related-movie-tiles">
        {state.loading ? Array.from({ length: 16 }, (_, index) => <div className="related-tile related-skeleton" key={index} />) :
          state.results.map((item) => (
            <button type="button" className="related-tile" key={item.tmdb_id} onClick={() => openItem(item)} aria-label={`Open ${item.title} ${isTv ? 'TV series' : 'in Discover'}`}>
              <span className="related-poster">{item.poster_url ? <img src={item.poster_url} alt="" loading="lazy" /> : <Film size={24} />}</span>
              <strong title={item.title}>{item.title}</strong>
              <small>{item.year || '—'} <span>★ {item.tmdb_rating || '—'}</span></small>
              {owned.has(String(item.tmdb_id)) && <span className="related-owned">Owned</span>}
            </button>
          ))}
        {!state.loading && !state.results.length && <p className="related-message" role="status">{state.error || emptyMessage} {id && state.error && <button type="button" className="mini-action" onClick={() => setRetry((value) => value + 1)}>Retry</button>}</p>}
      </div>
    </section>
  );
}
