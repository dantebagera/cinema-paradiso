import Pagination from '../../components/Pagination.jsx';
import TVSearchControls, { emptyTVQuery } from './TVSearchControls.jsx';
import TVIngestion from './TVIngestion.jsx';
import TVAcquisitionReview, { TVMonitoringControls } from './TVAcquisitionReview.jsx';
import TVFileView from './TVFileView.jsx';
import { useEffect, useRef, useState } from 'react';
import { ArrowLeft, Bookmark, Clapperboard, Film, Folder, MonitorPlay, Play, Plus, RefreshCw, Search, Tv } from 'lucide-react';
import { fetchJson } from '../../api/client.js';
import { ExpandedRating, UnifiedMovieCard } from '../../components/movie-card/MovieCard.jsx';
import { MovieImdbLink } from '../../components/SharedMovieCards.jsx';
import { MovieLanguageToggle, useTransientTVLanguage } from '../../components/MovieLanguageToggle.jsx';
import { formatVoteCount } from '../../utils/moviePresentation.js';
import { PersonBioModal, PersonCreditCard, usePersonBiography } from '../../components/PersonCreditCard.jsx';
import RelatedMovieRail from '../../components/RelatedMovieRail.jsx';
import { fetchTvRelationshipPage } from '../../api/movieRelationships.js';
import { withCriterion } from '../search/advancedSearchModel.js';
import { buildTvStreamTemplateUrl } from '../../utils/appUtils.js';
import useCardGridMetrics from '../../hooks/useCardGridMetrics.js';
import './tv.css';

const TV_CARD_PAGE_TARGET = 40;
const post = (url, data = {}) => fetchJson(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
const initialSeries = () => Number(window.location.pathname.match(/^\/tv\/series\/(\d+)/)?.[1]) || null;
function displayLanguage(value) {
  const text = String(value || '').trim();
  if (!/^[a-z]{2,3}$/i.test(text)) return text || 'Language unknown';
  try { return new Intl.DisplayNames(['en'], { type: 'language' }).of(text.toLowerCase()) || text; }
  catch { return text; }
}

export function TVSeriesCard({ series, onOpen, onPlay, context = 'library' }) {
  const action = series.primary_action;
  const total = series.listed_episode_count ?? series.episode_count;
  const counts = series.season_count == null ? '' : `${series.season_count} ${series.season_count === 1 ? 'season' : 'seasons'}${total == null ? '' : ` · ${total} episodes`}`;
  const dates = series.year_range || series.first_air_date?.slice(0, 4) || 'Dates unknown';
  return <UnifiedMovieCard title={series.title} year={<><strong>{dates}</strong>{counts && <span>· {counts}</span>}</>}
    posterUrl={series.poster_url} rating={series.rating ? Number(series.rating).toFixed(1) : ''} voteCount={series.votes ? `${series.votes} TMDB votes` : ''}
    chips={series.genres || []} statusLabel={series.status_label || series.status || ''}
    mutedChips={[displayLanguage(series.original_language_name || series.original_language), ...(series.origin_country || []), series.available_count > 0 ? `${series.available_count} episodes available` : '', ...(context === 'library' ? [series.quality_label] : [])].filter(Boolean)}
    navigation metadataLabel="TV series metadata" onToggle={() => onOpen(series)} className="tv-series-card">
    {context === 'library' && <p>{series.available_count || 0} of {series.episode_count || 0} available · {series.completed_count || 0} watched</p>}
    {context === 'continue' && action?.target && <p>{action.target.code} · {action.target.title}</p>}
    {action?.playable && <div className="tv-actions"><button className="primary-button" onClick={() => onPlay(action.target.episode_id)}><Play size={14} />{action.label}</button></div>}
  </UnifiedMovieCard>;
}

function EpisodeVersions({ episode, onClose, onPlay }) {
  const ref = useRef(null);
  useEffect(() => { const previous = document.activeElement; ref.current?.showModal(); return () => previous?.focus(); }, []);
  return <dialog ref={ref} className="tv-version-dialog" onCancel={onClose} aria-label={`${episode.code} versions`}>
    <h2>{episode.code} · Versions</h2>
    {episode.versions.map((version) => <div key={version.file_id} className="tv-version">
      <strong>{version.facts.quality_class || 'Unknown quality'} · {version.facts.video_codec || 'Unknown codec'}</strong>
      <p>{version.facts.audio_language || 'Unknown language'} · {Math.round(version.size / 1048576)} MB</p><code>{version.path}</code>
      <button className="primary-button" disabled={!version.available} onClick={() => { onPlay(episode.id, version.file_id); onClose(); }}>Play this version</button>
    </div>)}
    <button className="secondary-button" onClick={onClose}>Close</button>
  </dialog>;
}

export function TVSeriesPage({ id, tmdbId, onAdded, onBack, onPlay, onStream, onTrailer, onPersonCredits, onRelatedOpen, onRelatedViewAll, initialSeason, onSeasonChange, streaming, notify }) {
  const [baseSeries, setSeries] = useState(null), [season, setSeason] = useState(initialSeason ?? null), [episodes, setEpisodes] = useState([]);
  const [page, setPage] = useState(1), [pages, setPages] = useState(1), [error, setError] = useState(''), [versions, setVersions] = useState(null), [revision, setRevision] = useState(0), [searchTarget, setSearchTarget] = useState(null);
  const [castLimit,setCastLimit] = useState(20);
  const { personBio, openPersonBio, closePersonBio } = usePersonBiography();
  const [selected,setSelected] = useState([]), [includeOwned,setIncludeOwned] = useState(false);
  const languageView = useTransientTVLanguage(baseSeries);
  const series = languageView.displaySeries;
  const downloadTarget = (extra={}) => ({...(id?{series_id:id}:{tmdb_id:tmdbId}),season,missing_only:!includeOwned,upgrade:includeOwned,...extra});
  async function selectEpisodes(missing) {
    try {
      const data = await fetchJson(id ? `/api/tv/series/${id}/selection?season=${season}` : `/api/tv/preview/${tmdbId}/seasons/${season}`);
      setSelected(data.items.filter(e=>e.released && !e.reconciliation_required && (!missing || !e.available)).map(e=>e.episode_number));
    } catch(e) { notify(e.message,'error'); }
  }
  const base = id ? `/api/tv/series/${id}` : `/api/tv/preview/${tmdbId}`;
  useEffect(() => { let alive = true; setSeries(null); setError(''); fetchJson(base).then((row) => { if (alive) { setSeries(row); setSeason((old) => old ?? row.default_season); } }).catch((e) => alive && setError(e.message)); return () => { alive = false; }; }, [base, revision]);
  useEffect(() => { if (season === null) return; let alive = true; setEpisodes([]); fetchJson(`${base}/seasons/${season}?page=${page}`).then((data) => { if (alive) { setEpisodes(data.items); setPages(data.total_pages); } }).catch((e) => alive && setError(e.message)); return () => { alive = false; }; }, [base, season, page, revision]);
  async function mark(episode) { try { await post(`/api/tv/episodes/${episode.id}/progress`, { completed: !episode.completed, restart: Boolean(episode.completed) }); setRevision((r) => r + 1); } catch (e) { notify(e.message, 'error'); } }
  if (error) return <div className="empty-state" role="alert"><strong>{error}</strong><button onClick={() => setRevision((r) => r + 1)}>Retry</button><button onClick={onBack}>Back</button></div>;
  if (!series) return <div className="loading-state" role="status">Loading series…</div>;
  const streamUrl = streaming?.enabled && buildTvStreamTemplateUrl(streaming.tv_url_template, series.stream_target);
  return <section className="tv-series-page" aria-label={`${series.title} series page`}>
    <button className="secondary-button" onClick={onBack}><ArrowLeft size={16} />Back to TV Shows</button>
    <header className="tv-series-header" style={series.backdrop_url ? { backgroundImage: `linear-gradient(90deg, #111 30%, #1119), url("${series.backdrop_url}")` } : undefined}>
      {series.poster_url ? <img src={series.poster_url} alt="" /> : <Tv size={64} />}
      <div><div className="tv-series-heading"><div><p className="screen-kicker">TV SHOW</p><h1 dir="auto">{series.title}</h1><p>{series.year_range} · {series.status_label}</p></div>
        <div className="unified-movie-header-meta"><ExpandedRating rating={series.rating ? Number(series.rating).toFixed(1) : ''} voteCount={formatVoteCount(series.votes)} /><MovieImdbLink imdbId={series.external_ids?.imdb_id} title={series.title} /></div>
      </div>
        <div className="tv-series-badges" aria-label="Series genres, language, and country">
          {(series.genres || []).map(genre => <span className="unified-chip" key={`genre-${genre}`}>{genre}</span>)}
          <span className="unified-chip unified-chip-muted">{displayLanguage(series.original_language_name || series.original_language)}</span>
          {(series.origin_country?.length ? series.origin_country : ['Country unknown']).map(country => <span className="unified-chip unified-chip-muted" key={`country-${country}`}>{country}</span>)}
          <span className="unified-chip-row-actions"><MovieLanguageToggle {...languageView.toggleProps} /></span>
        </div>
        <p>{series.season_count} {series.season_count === 1 ? 'season' : 'seasons'} · {series.episode_count} {id ? 'released episodes' : 'episodes listed'} · {series.available_count} available</p><p dir="auto">{series.overview}</p>{series.metadata_notice && <p role="status">{series.metadata_notice}</p>}{series.runtime && <p>{series.runtime} min per episode</p>}
        <p><a href={`https://www.themoviedb.org/tv/${series.tmdb_id}`} target="_blank" rel="noreferrer">TMDB</a></p>
        <div className="card-actions"><button type="button" className="btn btn-primary btn-green" disabled={!series.primary_action.playable} onClick={() => onPlay(series.primary_action.target.episode_id)}><Play size={15} />{series.primary_action.label}</button>
          {streamUrl && <button type="button" className="btn btn-secondary btn-green-outline" onClick={() => onStream(series, series.stream_target)}><MonitorPlay size={15} />{streaming.label || 'Stream'}</button>}
          <button type="button" className="btn btn-secondary" disabled={!series.trailer_url} onClick={() => onTrailer?.(series, series.trailer_url)}><Film size={15} />{series.trailer_url ? 'Trailer' : 'Trailer unavailable'}</button>
          {!id && <button type="button" className="btn btn-primary" onClick={async () => { try { const added = await post('/api/tv/series', { tmdb_id: tmdbId }); onAdded(added.id); } catch (e) { notify(e.message, 'error'); } }}><Plus size={15} />Add to library</button>}
          {id && <button type="button" className="btn btn-secondary" onClick={async () => { try { await post(`${base}/watchlist`, { watchlisted: !series.watchlisted }); setRevision((r) => r + 1); } catch (e) { notify(e.message, 'error'); } }}><Bookmark size={15} fill={series.watchlisted ? 'currentColor' : 'none'} />{series.watchlisted ? 'Remove from watchlist' : 'Add to watchlist'}</button>}
          {id && <button type="button" className="btn btn-secondary" onClick={async () => { try { await post(`/api/tv/series/${id}/refresh`); setRevision((r) => r + 1); } catch (e) { notify(e.message, 'error'); } }}><RefreshCw size={15} />Refresh metadata</button>}
        </div>{!series.primary_action.playable && <p>{series.primary_action.reason}</p>}
      </div>
    </header>
    <section aria-label="Series cast" className="tv-main-cast"><h2>Cast and creators</h2>{series.cast?.length ? <><div className="movie-expanded-people-grid tv-cast">{series.cast.slice(0,castLimit).map((credit,i)=>{
      const person = { ...credit, id: credit.tmdb_id, profile_url: credit.portrait_url, character: credit.role };
      const role = credit.kind || 'actor';
      return <PersonCreditCard key={`${credit.tmdb_id}-${credit.role}-${i}`} person={person} role={role} canBrowse={Boolean(credit.tmdb_id && onPersonCredits)} onBrowse={onPersonCredits} onDiscover={onPersonCredits} onBio={openPersonBio}/>;
    })}</div>{series.cast.length>castLimit&&<button className="secondary-button tv-more-cast" onClick={()=>setCastLimit(n=>n+20)}>More cast</button>}</> : <p>{series.metadata_notice ? 'Cast could not be loaded.' : 'No cast information available.'}</p>}</section>
    <RelatedMovieRail movie={series} mediaType="tv" onNavigate={onRelatedOpen} onViewAll={({source})=>onRelatedViewAll?.({tmdbId:series.tmdb_id,title:series.title,source})}/>
    {id && <TVMonitoringControls seriesId={id} season={season} onSearch={setSearchTarget} notify={notify} />}
    <label className="tv-season-label">Season <select aria-label="TV season" value={season ?? ''} onChange={(e) => { const nextSeason=Number(e.target.value); setSeason(nextSeason); onSeasonChange?.(nextSeason); setPage(1); setSelected([]); }}>
      {series.seasons.map((item) => <option key={item.number} value={item.number}>{item.title} · {item.available}/{item.episodes} available · {item.completed} watched</option>)}
    </select><button className="primary-button" disabled={season===null} onClick={()=>setSearchTarget(downloadTarget())}>Download season</button></label>
    <div className="tv-actions tv-episode-selection"><button onClick={()=>selectEpisodes(false)}>Select all released</button><button onClick={()=>selectEpisodes(true)}>Select missing</button><button onClick={()=>setSelected([])} disabled={!selected.length}>Clear selection</button><span>{selected.length} episodes selected</span><label><input type="checkbox" checked={includeOwned} onChange={e=>setIncludeOwned(e.target.checked)}/>Include owned episodes (upgrade)</label><button className="primary-button" disabled={!selected.length} onClick={()=>setSearchTarget(downloadTarget({episode_numbers:selected}))}>Download selected</button></div>
    <Pagination page={page} totalPages={pages} ariaLabel="Episodes page controls above results" onPageChange={setPage} summary={`Season ${season}`}/>

    {id && !episodes.some(e=>e.preview) && <TVIngestion seriesId={id} episodes={episodes} onChanged={() => setRevision((r) => r + 1)} />}
    <div className="tv-episode-list">{episodes.map((episode) => {
      const target = { ...episode, episode_id: episode.id, tmdb_id: series.tmdb_id };
      const stream = streaming?.enabled && buildTvStreamTemplateUrl(streaming.tv_url_template, target);
      return <article className="tv-episode" key={episode.id} aria-label={`${episode.code} ${episode.title}`}>
        <div><label className="tv-episode-check"><input type="checkbox" aria-label={`Select ${episode.code}`} disabled={!episode.released || Boolean(episode.reconciliation_required)} checked={selected.includes(episode.episode_number)} onChange={e=>setSelected(old=>e.target.checked?[...old,episode.episode_number]:old.filter(n=>n!==episode.episode_number))}/><strong>{episode.code} · {episode.title}</strong></label><p>{episode.air_date || 'Release date unknown'} · {episode.runtime ? `${episode.runtime} min` : 'Runtime unknown'} · {episode.completed ? 'Watched' : episode.position_ms ? 'In progress' : 'Unwatched'}</p>
          <p>{episode.reconciliation_required ? 'Metadata needs review' : !episode.released ? 'Unaired / release unknown' : episode.available ? 'Available locally' : 'Missing locally'}</p>
          {episode.overview && <p>{episode.overview}</p>}
          {episode.guest_stars?.length > 0 && <p>Guests: {episode.guest_stars.map((person) => `${person.name} (${person.role})`).join(' · ')}</p>}
          {episode.duration_ms > 0 && <progress aria-label={`${episode.code} progress`} value={episode.position_ms || 0} max={episode.duration_ms} />}
        </div>
        <div className="tv-actions"><button className="primary-button" disabled={!episode.released || !episode.available || Boolean(episode.reconciliation_required)} onClick={() => onPlay(episode.id)}>{episode.position_ms && !episode.completed ? 'Resume' : 'Play'}</button>
          {stream && <button className="secondary-button" onClick={() => onStream(series, target)}>{streaming.label || 'Stream'}</button>}
          {episode.versions.length > 0 && <button className="secondary-button" onClick={() => setVersions(episode)}>Versions ({episode.versions.length})</button>}
          {episode.released && <button className="secondary-button" onClick={() => setSearchTarget(downloadTarget({season:episode.season_number,episode:episode.episode_number}))}>Download episode</button>}
          <button className="secondary-button" disabled={!id || episode.preview || !episode.released} onClick={() => mark(episode)}>{episode.completed ? 'Mark unwatched' : 'Mark watched'}</button>
        </div>
      </article>;
    })}</div>
    <Pagination page={page} totalPages={pages} ariaLabel="Episodes pagination" onPageChange={setPage} summary={`Season ${season}`}/>

    {searchTarget && <TVAcquisitionReview target={searchTarget} onClose={() => setSearchTarget(null)} notify={notify} />}
    {versions && <EpisodeVersions episode={versions} onClose={() => setVersions(null)} onPlay={onPlay} />}
    {personBio && <PersonBioModal state={personBio} onClose={closePersonBio}/>}
  </section>;
}

function TVContextListing({ listing, onBack, onOpen, onPlay, onStream, streaming }) {
  const [page, setPage] = useState(1);
  const { gridRef, measured, pageSize } = useCardGridMetrics({ target: TV_CARD_PAGE_TARGET, max: 100, bias: 'lower' });
  const [source, setSource] = useState(listing.source || 'all');
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  useEffect(() => { setPage(1); setSource(listing.source || 'all'); }, [listing]);
  useEffect(() => { setPage(1); }, [pageSize]);
  useEffect(() => {
    if (!measured) return undefined;
    const controller = new AbortController();
    let alive = true;
    setData(null); setError('');
    const request = listing.kind === 'related'
      ? fetchTvRelationshipPage(listing.tmdbId, source, page, pageSize)
      : post('/api/tv/catalog/search', {scope:'discover',query:withCriterion(emptyTVQuery('discover'),'person',{id:String(listing.person.id),label:listing.person.name,role:listing.person.role}),page,page_size:pageSize,extras:{}});
    request.then(result => { if (alive) setData(result); }).catch(cause => { if (alive && cause.name !== 'AbortError') setError(cause.message); });
    return () => { alive = false; controller.abort(); };
  }, [listing, source, page, pageSize, measured, retry]);
  const items = listing.kind === 'related' ? data?.results : data?.items;
  const title = listing.kind === 'related' ? `More like ${listing.title}` : `${listing.person.name} · TV shows`;
  const pagination = (label) => <Pagination page={page} total={data?.total_results ?? data?.total} totalPages={data?.total_pages} hasNext={data?.has_next} pageStart={(page-1)*(data?.page_size||pageSize)} pageEnd={(page-1)*(data?.page_size||pageSize)+(items?.length||0)} ariaLabel={label} onPageChange={setPage}/>;
  return <section className="tv-workspace tv-context-listing" aria-label={title}>
    <button className="secondary-button" onClick={onBack}><ArrowLeft size={16}/>Back to series</button>
    <header><p className="screen-kicker">TV SHOWS</p><h1>{title}</h1><p>{listing.kind === 'related' ? 'Recommended and similar series from TMDB.' : 'TV credits from TMDB.'}</p></header>
    {listing.kind === 'related' && <div className="related-source-selector" aria-label="Relationship source">{[['all','All'],['recommendations','Recommended'],['similar','Similar']].map(([value,label])=><button type="button" key={value} aria-pressed={source===value} onClick={()=>{setSource(value);setPage(1);}}>{label}</button>)}</div>}
    {(!measured || !items?.length) && <div ref={gridRef} className="tv-series-grid library-grid-metrics-probe" aria-hidden="true" />}
    {data?.notice && <p role="status">{data.notice}</p>}
    {error ? <div className="empty-state" role="alert"><strong>{error}</strong><button onClick={()=>setRetry(n=>n+1)}>Retry</button></div> : !data ? <div className="loading-state" role="status">Loading TV shows…</div> : <>
      {pagination('TV results page controls above results')}
      {items?.length ? <div ref={gridRef} className="tv-series-grid">{items.map(series=><TVSeriesCard key={series.tmdb_id} series={series} context="discover" onOpen={onOpen} onPlay={onPlay}/>)}</div> : <div className="empty-state">No TV shows found.</div>}
      {data.continue_scan && <button onClick={()=>setRetry(n=>n+1)}>Continue searching</button>}
      {pagination('TV results pagination')}
    </>}
  </section>;
}

export default function TVWorkspace({ context, streaming, onStream, onTrailer, notify, mediaNavigation }) {
  const [query, setQuery] = useState(() => emptyTVQuery(context)), [page, setPage] = useState(1);
  const { gridRef, measured, pageSize } = useCardGridMetrics({ target: TV_CARD_PAGE_TARGET, max: 100, bias: 'lower' });
  const [data, setData] = useState(null), [error, setError] = useState(''), [revision, setRevision] = useState(0), [seriesId, setSeriesId] = useState(context === 'library' ? initialSeries : null), [previewId, setPreviewId] = useState(() => window.history.state?.tvContext === context ? window.history.state?.tvPreview || null : null);
  const [listing, setListing] = useState(() => window.history.state?.tvContext === context ? window.history.state?.tvListing || null : null);
  const [status, setStatus] = useState('');
  const [fileView, setFileView] = useState(false);
  const origin = useRef(null);
  useEffect(() => { setPage(1); }, [pageSize]);
  useEffect(() => { const pop = () => { const state = window.history.state?.tvContext === context ? window.history.state : {}; setSeriesId(context === 'library' ? initialSeries() : null); setPreviewId(state.tvPreview || null); setListing(state.tvListing || null); }; window.addEventListener('popstate', pop); return () => window.removeEventListener('popstate', pop); }, [context]);
  useEffect(() => { if (!measured) return undefined; let alive = true; const controller = new AbortController(); setError(''); setData(null); fetchJson('/api/tv/catalog/search', { signal: controller.signal, method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ scope: context, query, page, page_size: pageSize, extras: context === 'library' ? { status } : {} }) }).then((result) => alive && setData(result)).catch((e) => alive && e.name !== 'AbortError' && setError(e.message)); return () => { alive = false; controller.abort(); }; }, [context, query, page, pageSize, measured, status, revision]);
  useEffect(()=>{
    if(context!=='discover' || !data?.items?.length) return;
    const controller=new AbortController(); const ids=data.items.filter(r=>r.season_count==null || !r.status).map(r=>r.tmdb_id);
    if(!ids.length)return;
    for(let start=0;start<ids.length;start+=20){
      fetchJson('/api/tv/catalog/enrich',{method:'POST',signal:controller.signal,headers:{'Content-Type':'application/json'},body:JSON.stringify({ids:ids.slice(start,start+20)})}).then(result=>setData(current=>current?{...current,items:current.items.map(row=>{const extra=result.items.find(r=>r.tmdb_id===row.tmdb_id);return extra?{...row,...extra,id:row.id,available_count:row.available_count,completed_count:row.completed_count,watchlisted:row.watchlisted}:row;})}:current)).catch(()=>{});
    }
    return ()=>controller.abort();
  },[context,query,page,revision,Boolean(data)]);
  function open(series) { origin.current = document.activeElement; setListing(null); setSeriesId(series.id || null); setPreviewId(series.id ? null : series.tmdb_id); window.history.pushState({tvContext:context,tvBack:true,...(series.id ? {} : {tvPreview:series.tmdb_id})}, '', series.id ? `/tv/series/${series.id}` : `/${context}`); }
  function openListing(next) { origin.current = document.activeElement; setSeriesId(null); setPreviewId(null); setListing(next); window.history.pushState({tvContext:context,tvListing:next,tvBack:true}, '', `/${context}`); }
  function back() { if (window.history.state?.tvBack) { window.history.back(); return; } setPreviewId(null); setSeriesId(null); setListing(null); setRevision(r=>r+1); window.history.pushState({}, '', `/${context}`); setTimeout(() => origin.current?.focus(), 0); }
  async function play(episodeId, fileId) { try { const result = await post(`/api/tv/episodes/${episodeId}/play`, { file_id: fileId }); notify(result.fallback ? result.reason : 'Opening episode', 'success'); } catch (e) { notify(e.message, 'error'); } }
  if (seriesId || previewId) return <TVSeriesPage key={seriesId ? `local-${seriesId}` : `preview-${previewId}`} id={seriesId} tmdbId={previewId} initialSeason={window.history.state?.tvSeason} onSeasonChange={next=>window.history.replaceState({...window.history.state,tvSeason:next},'')} onAdded={(id) => { setSeriesId(id); setPreviewId(null); window.history.pushState({tvContext:context,tvBack:true}, '', `/tv/series/${id}`); }} onTrailer={onTrailer} streaming={streaming} onStream={onStream} onPlay={play} notify={notify} onBack={back} onPersonCredits={(role,person)=>openListing({kind:'person',person:{id:person.id,name:person.name,role}})} onRelatedOpen={open} onRelatedViewAll={details=>openListing({kind:'related',...details})}/>;
  if (listing) return <TVContextListing listing={listing} onBack={back} onOpen={open} onPlay={play} onStream={onStream} streaming={streaming}/>;
  return <section className={`tv-workspace${context === 'discover' ? ' discover-workspace tv-discover-workspace' : ' library-workspace tv-library-workspace'}`} aria-label={`${context === 'discover' ? 'Discover' : 'Library'} TV Shows`}>
    <header className={context === 'discover' ? 'library-header discover-header' : 'library-header'}>
      <div><p className="screen-kicker">{context === 'discover' ? 'FIND YOUR NEXT SERIES' : 'LOCAL TV LIBRARY'}</p><h2>{fileView && context === 'library' ? 'TV Files' : 'TV Shows'}</h2><p>Series, seasons, specials, and every episode.</p></div>
      {context === 'discover' && <div className="settings-summary"><strong>{data?.items?.length ?? 0}</strong><span>loaded titles</span></div>}
      {context === 'library' && <div className="library-header-actions"><div className="library-view-row"><div className="segmented-control library-view-switch" role="group" aria-label="TV library mode"><button type="button" className={!fileView ? 'segment-active' : ''} onClick={() => setFileView(false)}><Clapperboard size={18}/> Media View</button><button type="button" className={fileView ? 'segment-active' : ''} onClick={() => setFileView(true)}><Folder size={18}/> File View</button></div><button type="button" className="btn btn-secondary library-rescan-button" aria-label="Refresh TV catalog" onClick={() => setRevision(value => value + 1)}><RefreshCw size={19}/></button></div></div>}
    </header>
    {mediaNavigation}
    {fileView && context === 'library' ? <TVFileView onOpenSeries={open} onPlay={play}/> : <>
    {(!measured || !data?.items?.length) && <div ref={gridRef} className="tv-series-grid library-grid-metrics-probe" aria-hidden="true" />}
    <TVSearchControls scope={context} query={query} status={status} onStatusChange={(next) => { setStatus(next); setPage(1); }} onRun={(next) => { setQuery(next); setPage(1); }} onClear={() => setStatus('')} onRefresh={() => setRevision((r) => r + 1)} loading={!data && !error} />
    {data?.notice && <p role="status">{data.notice}</p>}
    {error ? <div className="empty-state" role="alert"><strong>{error}</strong><button onClick={()=>setRevision(r=>r+1)}>Retry</button></div> : !data ? <div className="loading-state" role="status">Loading TV shows…</div> : <>
      <Pagination total={data.total} page={page} totalPages={data.total_pages} hasNext={data.has_next} pageStart={(page-1)*(data.page_size||pageSize)} pageEnd={(page-1)*(data.page_size||pageSize)+data.items.length} ariaLabel="TV page controls above results" onPageChange={setPage}/>
      {!data.items.length?<div className="empty-state"><strong>{data.continue_scan?'Still looking for matching series.':query.groups.length || status?'No series match your search.':'No TV series yet.'}</strong></div>:<div ref={gridRef} className="tv-series-grid">{data.items.map(series=><TVSeriesCard key={series.tmdb_id} series={series} context={context} onOpen={open} onPlay={play}/>)}</div>}
      {data.continue_scan && <button onClick={()=>setRevision(r=>r+1)}>Continue searching</button>}
      <Pagination total={data.total} page={page} totalPages={data.total_pages} hasNext={data.has_next} pageStart={(page-1)*(data.page_size||pageSize)} pageEnd={(page-1)*(data.page_size||pageSize)+data.items.length} ariaLabel="TV pagination" onPageChange={setPage}/>
    </>}
    </>}
  </section>;
}
