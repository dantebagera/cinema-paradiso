import DialogShell from '../../components/ui/DialogShell.jsx';
import { Select } from '../../components/ui/FormField.jsx';
import Badge from '../../components/ui/Badge.jsx';
import WorkspaceEmptyState from '../../components/WorkspaceEmptyState.jsx';
import Button, { StreamButton } from '../../components/ui/Button.jsx';
import Pagination from '../../components/Pagination.jsx';
import WorkspaceChrome from '../../components/WorkspaceChrome.jsx';
import WorkspaceViewActions from '../../components/WorkspaceViewActions.jsx';
import TVSearchControls, { emptyTVQuery } from './TVSearchControls.jsx';
import TVIngestion from './TVIngestion.jsx';
import TVLibraryImport from './TVLibraryImport.jsx';
import TVBulkActionBar from './TVBulkActionBar.jsx';
import TVPosterEditor from './TVPosterEditor.jsx';
import TVAcquisitionReview, { TVMonitoringControls, TVSeasonSelection } from './TVAcquisitionReview.jsx';
import TVFileView from './TVFileView.jsx';
import { useCallback, useEffect, useRef, useState } from 'react';
import { ArrowLeft, Bookmark, Film, MonitorPlay, Play, Plus, RefreshCw, Search, Tv } from 'lucide-react';
import { fetchJson } from '../../api/client.js';
import { ExpandedRating, UnifiedMovieCard } from '../../components/movie-card/MovieCard.jsx';
import { MovieImdbLink, PosterEditButton, PosterStateControls } from '../../components/SharedMovieCards.jsx';
import SelectionCheckbox from '../../components/SelectionCheckbox.jsx';
import { MovieLanguageToggle, useTransientTVLanguage } from '../../components/MovieLanguageToggle.jsx';
import { formatVoteCount } from '../../utils/moviePresentation.js';
import { PersonBioModal, usePersonBiography } from '../../components/PersonCreditCard.jsx';
import RelatedMovieRail from '../../components/RelatedMovieRail.jsx';
import TVSeriesCredits from './TVSeriesCredits.jsx';
import { fetchTvRelationshipPage } from '../../api/movieRelationships.js';
import { withCriterion } from '../search/advancedSearchModel.js';
import { buildTvStreamTemplateUrl } from '../../utils/appUtils.js';
import useCardGridMetrics from '../../hooks/useCardGridMetrics.js';
import { enrichTVCardBatches } from './tvCardEnrichment.js';
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

function tvStatusTone(status) {
  if (status === 'Ended') return 'owned';
  if (status === 'Returning Series') return 'danger';
  return 'neutral';
}

const tvPercentage = (value) => value == null ? '—' : `${value}%`;

export function TVSeriesCard({ series, onOpen, onPlay, onWatchlist, onWatched, onPosterEdit, onSelect, selected = false, context = 'library', reviewOnly = false }) {
  const action = series.primary_action;
  const total = series.coverage_complete ? series.episode_count : series.listed_episode_count;
  const counts = [series.season_count == null ? '' : `${series.season_count} seas.`, total == null ? '' : `${total} eps.${series.coverage_complete ? '' : ' (est.)'}`].filter(Boolean).join(' · ');
  const countsDescription = [series.season_count == null ? '' : `${series.season_count} seasons`, total == null ? '' : `${total} episodes${series.coverage_complete ? '' : ' estimated'}`].filter(Boolean).join(' · ');
  const dates = series.year_range || series.first_air_date?.slice(0, 4) || 'Dates unknown';
  const position = action?.position_ms ? ` from ${Math.floor(action.position_ms / 60000)}:${String(Math.floor(action.position_ms / 1000) % 60).padStart(2, '0')}` : '';
  const playLabel = action?.target ? `${action.label} ${series.title} ${action.target.code}${position}` : '';
  const watchedDisabledReason = series.id && (series.status !== 'Ended' || !series.coverage_complete)
    ? 'Mark watched is available after an ended show has complete episode metadata' : '';
  return <UnifiedMovieCard title={series.title} year={<><strong>{dates}</strong>{counts && <span title={countsDescription}>· {counts}</span>}{series.available_count > 0 && <><span aria-hidden="true">·</span><span className="tv-offline-percentage">{series.offline_percent == null ? 'Offline % unknown' : `${series.offline_percent}% offline`}</span></>}</>}
    posterUrl={series.poster_url} backdropUrl={series.backdrop_url} rating={series.rating ? Number(series.rating).toFixed(1) : ''} voteCount={series.votes ? `${series.votes} TMDB votes` : ''}
    chips={series.genres || []} statusLabel={series.status_label || series.status || ''} statusTone={tvStatusTone(series.status)}
    mutedChips={[displayLanguage(series.original_language_name || series.original_language), ...(series.origin_country || []), ...(context === 'library' ? [series.quality_label] : [])].filter(Boolean)}
    navigation metadataLabel="TV series metadata" onToggle={() => onOpen(series)} className="tv-series-card"
    selected={selected} showPlayOverlay={!reviewOnly && Boolean(action?.playable)} onPlay={!reviewOnly && action?.playable ? () => onPlay(action.target.episode_id) : undefined}
    playLabel={playLabel} playTitle={playLabel}
    cornerControls={<><PosterStateControls title={series.title} watched={series.series_watched} watchlisted={series.watchlisted}
      onToggleWatched={series.id && !watchedDisabledReason && onWatched ? () => onWatched(series) : undefined}
      watchedDisabledReason={watchedDisabledReason} onToggleWatchlist={onWatchlist ? () => onWatchlist(series) : undefined} />
      <PosterEditButton title={series.title} onEdit={series.id && onPosterEdit ? () => onPosterEdit(series) : undefined} />
      {onSelect && (series.id || series.tmdb_id) && <SelectionCheckbox className="library-selection-checkbox" checked={selected} onChange={(checked) => onSelect(series, checked)} label={`Select ${series.title}`} />}</>}>
    {series.pending_review_count > 0 && <p>{series.pending_review_count} file{series.pending_review_count === 1 ? '' : 's'} need identity review</p>}
    {context === 'continue' && action?.target && <p>{action.target.code} · {action.target.title}</p>}
    {!action?.target && action?.reason && <p>{action.reason}</p>}
    {action?.target && !action.playable && <button type="button" className="tv-missing-next" onClick={(event) => { event.stopPropagation(); onOpen(series); }}>Open {action.target.code}: {action.reason}</button>}
  </UnifiedMovieCard>;
}

function EpisodeVersions({ episode, onClose, onPlay }) {
  const ref = useRef(null);
  useEffect(() => { const previous = document.activeElement; ref.current?.showModal(); return () => previous?.focus(); }, []);
  return <DialogShell as="dialog" size="wide" ref={ref} className="tv-version-dialog" onCancel={onClose} aria-label={`${episode.code} versions`}>
    <h2>{episode.code} · Versions</h2>
    {episode.versions.map((version) => <div key={version.file_id} className="tv-version">
      <strong>{version.facts.quality_class || 'Unknown quality'} · {version.facts.video_codec || 'Unknown codec'}</strong>
      <p>{version.facts.audio_language || 'Unknown language'} · {Math.round(version.size / 1048576)} MB</p><code>{version.path}</code>
      <Button variant="primary"  disabled={!version.available} onClick={() => { onPlay(episode.id, version.file_id); onClose(); }}>Play this version</Button>
    </div>)}
    <Button  onClick={onClose}>Close</Button>
  </DialogShell>;
}

export function TVSeriesPage({ id, tmdbId, onAdded, onBack, onPlay, onStream, onTrailer, onPersonCredits, onRelatedOpen, onRelatedViewAll, initialSeason, onSeasonChange, streaming, notify }) {
  const [baseSeries, setSeries] = useState(null), [season, setSeason] = useState(initialSeason ?? null), [episodes, setEpisodes] = useState([]);
  const [page, setPage] = useState(1), [pages, setPages] = useState(1), [error, setError] = useState(''), [versions, setVersions] = useState(null), [revision, setRevision] = useState(0), [searchTarget, setSearchTarget] = useState(null);
  const { personBio, openPersonBio, closePersonBio } = usePersonBiography();
  const [selected,setSelected] = useState([]), [includeOwned,setIncludeOwned] = useState(false);
  const [choosingSeasons, setChoosingSeasons] = useState(false);
  const languageView = useTransientTVLanguage(baseSeries);
  const series = languageView.displaySeries;
  const downloadTarget = (extra={}) => ({...(id?{series_id:id}:{tmdb_id:tmdbId}),season,missing_only:!includeOwned,upgrade:includeOwned,...extra});
  const reviewSeasons = seasons => { setChoosingSeasons(false); setSearchTarget({...(id ? {series_id:id} : {tmdb_id:tmdbId}), seasons}); };
  useEffect(() => { setSearchTarget(null); setChoosingSeasons(false); setSelected([]); setIncludeOwned(false); }, [id, tmdbId]);
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
  if (error) return <WorkspaceEmptyState size="compact"  role="alert"><strong>{error}</strong><Button onClick={() => setRevision((r) => r + 1)}>Retry</Button><Button onClick={onBack}>Back</Button></WorkspaceEmptyState>;
  if (!series) return <div className="loading-state" role="status">Loading series…</div>;
  const streamUrl = streaming?.enabled && buildTvStreamTemplateUrl(streaming.tv_url_template, series.stream_target);
  const denominator = series.coverage_complete ? series.episode_count : '—';
  const statusLabel = series.status_label || series.status || '';
  return <section className="tv-series-page" aria-label={`${series.title} series page`}>
    <header className="tv-series-header" style={series.backdrop_url ? { backgroundImage: `linear-gradient(90deg, #111 30%, #1119), url("${series.backdrop_url}")` } : undefined}>
      {series.poster_url ? <img src={series.poster_url} alt="" /> : <Tv size={64} />}
      <div className="tv-series-header-summary"><div className="tv-series-heading"><div><Button size="compact" type="button"  onClick={onBack}><ArrowLeft size={14} />Back to TV Shows</Button><h1 dir="auto">{series.title}</h1><p>{series.year_range}</p></div>
        <div className="unified-movie-header-meta"><ExpandedRating rating={series.rating ? Number(series.rating).toFixed(1) : ''} voteCount={formatVoteCount(series.votes)} /><MovieImdbLink imdbId={series.external_ids?.imdb_id} title={series.title} /></div>
      </div>
        <div className="tv-series-badges" aria-label="Series genres, language, and country">
          {(series.genres || []).map(genre => <Badge  key={`genre-${genre}`}>{genre}</Badge>)}
          <Badge tone="neutral" muted >{displayLanguage(series.original_language_name || series.original_language)}</Badge>
          {(series.origin_country?.length ? series.origin_country : ['Country unknown']).map(country => <Badge tone="neutral" muted  key={`country-${country}`}>{country}</Badge>)}
          {statusLabel && <Badge kind="status" tone={tvStatusTone(series.status)} >{statusLabel}</Badge>}
          <span className="unified-chip-row-actions"><MovieLanguageToggle {...languageView.toggleProps} /></span>
        </div>
        <p>{series.season_count} {series.season_count === 1 ? 'season' : 'seasons'} · {series.episode_count} {id ? 'released episodes' : 'episodes listed'} · {series.available_count} available</p>
        {id && <p className="tv-series-progress">{series.available_count || 0} / {denominator} eps. offline ({tvPercentage(series.offline_percent)}) · {series.completed_count || 0} / {denominator} watched ({tvPercentage(series.watched_percent)})</p>}
      </div>
      <div className="tv-series-header-details">
        <p dir="auto">{series.overview}</p>{series.metadata_notice && <p role="status">{series.metadata_notice}</p>}{series.runtime && <p>{series.runtime} min per episode</p>}
        <p><a href={`https://www.themoviedb.org/tv/${series.tmdb_id}`} target="_blank" rel="noreferrer">TMDB</a></p>
        <div className="card-actions"><Button variant="play" type="button"  disabled={!series.primary_action.playable} onClick={() => onPlay(series.primary_action.target.episode_id)}><Play size={15} />{series.primary_action.label}</Button>
          {streamUrl && <StreamButton type="button"  onClick={() => onStream(series, series.stream_target)}>{streaming.label || 'Stream'}</StreamButton>}
          <Button type="button"  disabled={!series.trailer_url} onClick={() => onTrailer?.(series, series.trailer_url)}><Film size={15} />{series.trailer_url ? 'Trailer' : 'Trailer unavailable'}</Button>
          {!id && <Button variant="primary" type="button"  onClick={async () => { try { const added = await post('/api/tv/series', { tmdb_id: tmdbId }); onAdded(added.id); } catch (e) { notify(e.message, 'error'); } }}><Plus size={15} />Add to library</Button>}
          {id && <Button type="button"  onClick={async () => { try { await post(`${base}/watchlist`, { watchlisted: !series.watchlisted }); setRevision((r) => r + 1); } catch (e) { notify(e.message, 'error'); } }}><Bookmark size={15} fill={series.watchlisted ? 'currentColor' : 'none'} />{series.watchlisted ? 'Remove from watchlist' : 'Add to watchlist'}</Button>}
          {id && <Button type="button"  onClick={async () => { try { await post(`/api/tv/series/${id}/refresh`); setRevision((r) => r + 1); } catch (e) { notify(e.message, 'error'); } }}><RefreshCw size={15} />Refresh metadata</Button>}
        </div>{!series.primary_action.playable && series.primary_action.reason && <p>{series.primary_action.reason}</p>}
      </div>
    </header>
    <TVSeriesCredits series={series} onPersonCredits={onPersonCredits} onBio={openPersonBio} />
    <RelatedMovieRail movie={series} mediaType="tv" onNavigate={onRelatedOpen} onViewAll={({source})=>onRelatedViewAll?.({tmdbId:series.tmdb_id,title:series.title,source})}/>
    {id && <TVMonitoringControls key={id} seriesId={id} series={series} season={season} notify={notify} />}
    <label className="tv-season-label">Season <Select aria-label="TV season" value={season ?? ''} onChange={(e) => { const nextSeason=Number(e.target.value); setSeason(nextSeason); onSeasonChange?.(nextSeason); setPage(1); setSelected([]); }}>
      {series.seasons.map((item) => <option key={item.number} value={item.number}>{item.title} · {item.available}/{item.episodes} available · {item.completed} watched</option>)}
    </Select><Button variant="primary"  disabled={season===null} onClick={()=>setSearchTarget(downloadTarget())}>Download season</Button><Button variant="primary"  disabled={!series.seasons.some(item => item.number > 0)} onClick={() => reviewSeasons(series.seasons.filter(item => item.number > 0).map(item => item.number))}>Download all seasons</Button><Button  onClick={() => setChoosingSeasons(true)}>Choose seasons…</Button></label>
    <div className="tv-actions tv-episode-selection"><Button onClick={()=>selectEpisodes(false)}>Select all released</Button><Button onClick={()=>selectEpisodes(true)}>Select missing</Button><Button onClick={()=>setSelected([])} disabled={!selected.length}>Clear selection</Button><span>{selected.length} episodes selected</span><label><input type="checkbox" checked={includeOwned} onChange={e=>setIncludeOwned(e.target.checked)}/>Include owned episodes (upgrade)</label><Button variant="primary"  disabled={!selected.length} onClick={()=>setSearchTarget(downloadTarget({episode_numbers:selected}))}>Download selected</Button></div>
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
        <div className="tv-actions"><Button variant="play"  disabled={!episode.released || !episode.available || Boolean(episode.reconciliation_required)} onClick={() => onPlay(episode.id)}>{episode.position_ms && !episode.completed ? 'Resume' : 'Play'}</Button>
          {stream && <StreamButton onClick={() => onStream(series, target)}>{streaming.label || 'Stream'}</StreamButton>}
          {episode.versions.length > 0 && <Button  onClick={() => setVersions(episode)}>Versions ({episode.versions.length})</Button>}
          {episode.released && <Button  onClick={() => setSearchTarget(downloadTarget({season:episode.season_number,episode:episode.episode_number}))}>Download episode</Button>}
          <Button  disabled={!id || episode.preview || !episode.released} onClick={() => mark(episode)}>{episode.completed ? 'Mark unwatched' : 'Mark watched'}</Button>
        </div>
      </article>;
    })}</div>
    <Pagination page={page} totalPages={pages} ariaLabel="Episodes pagination" onPageChange={setPage} summary={`Season ${season}`}/>

    {searchTarget && <TVAcquisitionReview target={searchTarget} onClose={() => setSearchTarget(null)} notify={notify} />}
    {choosingSeasons && <TVSeasonSelection series={baseSeries} seriesId={id} tmdbId={tmdbId} onReview={reviewSeasons} onClose={() => setChoosingSeasons(false)} />}
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
    <Button  onClick={onBack}><ArrowLeft size={16}/>Back to series</Button>
    <header><p className="screen-kicker">TV SHOWS</p><h1>{title}</h1><p>{listing.kind === 'related' ? 'Recommended and similar series from TMDB.' : 'TV credits from TMDB.'}</p></header>
    {listing.kind === 'related' && <div className="related-source-selector" aria-label="Relationship source">{[['all','All'],['recommendations','Recommended'],['similar','Similar']].map(([value,label])=><Button type="button" key={value} aria-pressed={source===value} onClick={()=>{setSource(value);setPage(1);}}>{label}</Button>)}</div>}
    {(!measured || !items?.length) && <div ref={gridRef} className="tv-series-grid library-grid-metrics-probe" aria-hidden="true" />}
    {data?.notice && <p role="status">{data.notice}</p>}
    {error ? <WorkspaceEmptyState size="compact"  role="alert"><strong>{error}</strong><Button onClick={()=>setRetry(n=>n+1)}>Retry</Button></WorkspaceEmptyState> : !data ? <div className="loading-state" role="status">Loading TV shows…</div> : <>
      {pagination('TV results page controls above results')}
      {items?.length ? <div ref={gridRef} className="tv-series-grid">{items.map(series=><TVSeriesCard key={series.tmdb_id} series={series} context="discover" onOpen={onOpen} onPlay={onPlay}/>)}</div> : <WorkspaceEmptyState size="compact" >No TV shows found.</WorkspaceEmptyState>}
      {data.continue_scan && <Button onClick={()=>setRetry(n=>n+1)}>Continue searching</Button>}
      {pagination('TV results pagination')}
    </>}
  </section>;
}

export default function TVWorkspace({ context, streaming, onStream, onTrailer, notify, mediaNavigation, onOpenMaintenance }) {
  const [query, setQuery] = useState(() => emptyTVQuery(context)), [page, setPage] = useState(1);
  const { columns, gridRef, measured, pageSize } = useCardGridMetrics({ target: TV_CARD_PAGE_TARGET, max: 100, bias: 'lower' });
  const gridNode = useRef(null);
  const attachGrid = useCallback(node => { gridNode.current = node; gridRef(node); }, [gridRef]);
  const [auxiliaryReady, setAuxiliaryReady] = useState(false);
  const [data, setData] = useState(null), [error, setError] = useState(''), [revision, setRevision] = useState(0), [seriesId, setSeriesId] = useState(context === 'library' ? initialSeries : null), [previewId, setPreviewId] = useState(() => window.history.state?.tvContext === context ? window.history.state?.tvPreview || null : null);
  const [listing, setListing] = useState(() => window.history.state?.tvContext === context ? window.history.state?.tvListing || null : null);
  const [status, setStatus] = useState('');
  const [fileView, setFileView] = useState(false);
  const [selectedRows, setSelectedRows] = useState(() => new Map());
  const [selectionError, setSelectionError] = useState('');
  const [posterEditor, setPosterEditor] = useState(null);
  const origin = useRef(null);
  useEffect(() => { setPage(1); }, [pageSize]);
  useEffect(() => { const pop = () => { const state = window.history.state?.tvContext === context ? window.history.state : {}; setSeriesId(context === 'library' ? initialSeries() : null); setPreviewId(state.tvPreview || null); setListing(state.tvListing || null); }; window.addEventListener('popstate', pop); return () => window.removeEventListener('popstate', pop); }, [context]);
  useEffect(() => { if (!measured) return undefined; let alive = true; const controller = new AbortController(); setError(''); setData(null); fetchJson('/api/tv/catalog/search', { signal: controller.signal, method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ scope: context, query, page, page_size: pageSize, extras: context === 'library' ? { status } : {} }) }).then((result) => { if(alive){setData(result);setAuxiliaryReady(true);} }).catch((e) => {if(alive && e.name !== 'AbortError'){setError(e.message);setAuxiliaryReady(true);}}); return () => { alive = false; controller.abort(); }; }, [context, query, page, pageSize, measured, status, revision]);
  useEffect(()=>{
    if(context!=='discover' || !data?.items?.length) return;
    const controller=new AbortController(); const ids=data.items.filter(r=>r.season_count==null || !r.status).map(r=>r.tmdb_id);
    if(!ids.length)return;
    const workspaceBounds=gridNode.current?.closest('main.workspace')?.getBoundingClientRect();
    const top=Math.max(0,workspaceBounds?.top||0),bottom=Math.min(window.innerHeight,workspaceBounds?.bottom||window.innerHeight);
    let priorityIds=Array.from(gridNode.current?.children||[]).flatMap((card,index)=>{
      const rect=card.getBoundingClientRect();
      return rect.width>0&&rect.bottom>top&&rect.top<bottom ? [data.items[index].tmdb_id] : [];
    });
    if(!priorityIds.length)priorityIds=data.items.slice(0,Math.max(1,columns)).map(row=>row.tmdb_id);
    enrichTVCardBatches(ids,priorityIds,
      batch=>fetchJson('/api/tv/catalog/enrich',{method:'POST',signal:controller.signal,headers:{'Content-Type':'application/json'},body:JSON.stringify({ids:batch})}),
      result=>setData(current=>current?{...current,items:current.items.map(row=>{const extra=result.items.find(r=>r.tmdb_id===row.tmdb_id);return extra?{...row,...extra,id:row.id,available_count:row.available_count,completed_count:row.completed_count,watchlisted:row.watchlisted}:row;})}:current),controller.signal);
    return ()=>controller.abort();
  },[context,query,page,revision,Boolean(data)]);
  function open(series) { origin.current = document.activeElement; setListing(null); setSeriesId(series.id || null); setPreviewId(series.id ? null : series.tmdb_id); window.history.pushState({tvContext:context,tvBack:true,...(series.id ? {} : {tvPreview:series.tmdb_id})}, '', series.id ? `/tv/series/${series.id}` : `/${context}`); }
  function openListing(next) { origin.current = document.activeElement; setSeriesId(null); setPreviewId(null); setListing(next); window.history.pushState({tvContext:context,tvListing:next,tvBack:true}, '', `/${context}`); }
  function back() { if (window.history.state?.tvBack) { window.history.back(); return; } setPreviewId(null); setSeriesId(null); setListing(null); setRevision(r=>r+1); window.history.pushState({}, '', `/${context}`); setTimeout(() => origin.current?.focus(), 0); }
  async function play(episodeId, fileId) { try { const result = await post(`/api/tv/episodes/${episodeId}/play`, { file_id: fileId }); notify(result.fallback ? result.reason : 'Opening episode', 'success'); } catch (e) { notify(e.message, 'error'); } }
  async function toggleWatchlist(series) {
    try {
      const id = series.id || (await post('/api/tv/series', { tmdb_id: series.tmdb_id })).id;
      await post(`/api/tv/series/${id}/watchlist`, { watchlisted: !series.watchlisted });
      setRevision((value) => value + 1);
    } catch (e) { notify(e.message, 'error'); }
  }
  async function toggleWatched(series) {
    try {
      await post(`/api/tv/series/${series.id}/watched`, { watched: !series.series_watched });
      setRevision((value) => value + 1);
    } catch (e) { notify(e.message, 'error'); }
  }
  function select(series, checked) {
    setSelectedRows(current => {
      const next = new Map(current);
      const key = series.tmdb_id ? `tmdb:${series.tmdb_id}` : `local:${series.id}`;
      if (checked) next.set(key, { ...series, id: series.id || current.get(key)?.id });
      else next.delete(key);
      return next;
    });
  }
  function clearSelection(completed) {
    setSelectionError('');
    setSelectedRows(current => {
      if (!completed) return new Map();
      const next = new Map(current);
      for (const row of completed) next.delete(row.tmdb_id ? `tmdb:${row.tmdb_id}` : `local:${row.id}`);
      return next;
    });
  }
  if (seriesId || previewId) return <TVSeriesPage key={seriesId ? `local-${seriesId}` : `preview-${previewId}`} id={seriesId} tmdbId={previewId} initialSeason={window.history.state?.tvSeason} onSeasonChange={next=>window.history.replaceState({...window.history.state,tvSeason:next},'')} onAdded={(id) => { setSeriesId(id); setPreviewId(null); window.history.pushState({tvContext:context,tvBack:true}, '', `/tv/series/${id}`); }} onTrailer={onTrailer} streaming={streaming} onStream={onStream} onPlay={play} notify={notify} onBack={back} onPersonCredits={(role,person)=>openListing({kind:'person',person:{id:person.id,name:person.name,role}})} onRelatedOpen={open} onRelatedViewAll={details=>openListing({kind:'related',...details})}/>;
  if (listing) return <TVContextListing listing={listing} onBack={back} onOpen={open} onPlay={play} onStream={onStream} streaming={streaming}/>;
  const viewActions = context === 'library' && <WorkspaceViewActions fileView={fileView} label="TV library mode" onMediaView={() => setFileView(false)} onFileView={() => setFileView(true)} onRefresh={() => setRevision(value => value + 1)} refreshLabel="Refresh TV catalog"><TVLibraryImport onOpenMaintenance={onOpenMaintenance} ready={auxiliaryReady}/></WorkspaceViewActions>;
  return <section className={`tv-workspace${context === 'discover' ? ' discover-workspace tv-discover-workspace' : ' library-workspace tv-library-workspace'}`} aria-label={`${context === 'discover' ? 'Discover' : 'Library'} TV Shows`}>
    {fileView && context === 'library' ? <TVFileView onOpenSeries={open} onPlay={play} mediaNavigation={mediaNavigation} viewActions={viewActions}/> : <>
    {(!measured || !data?.items?.length) && <div ref={attachGrid} className="tv-series-grid library-grid-metrics-probe" aria-hidden="true" />}
    <WorkspaceChrome navigation={mediaNavigation}>
    <TVSearchControls actions={viewActions} ready={context !== 'library' || auxiliaryReady} onControlsOpen={() => setAuxiliaryReady(true)} scope={context} query={query} status={status} onStatusChange={(next) => { setStatus(next); setPage(1); }} onRun={(next) => { setQuery(next); setPage(1); }} onClear={() => setStatus('')} onRefresh={() => setRevision((r) => r + 1)} loading={!data && !error} loadedCount={data?.items?.length || 0} selectedCount={selectedRows.size} selectionError={selectionError}
      selection={<TVBulkActionBar ready={auxiliaryReady} seriesRows={[...selectedRows.values()]} onResolved={series => select(series, true)}
        allSelected={Boolean(data?.items?.length) && data.items.every(series => selectedRows.has(series.tmdb_id ? `tmdb:${series.tmdb_id}` : `local:${series.id}`))}
        onToggleAll={checked => data?.items?.forEach(series => select(series, checked))}
        onSelectAll={() => data?.items?.forEach(series => select(series, true))} onClear={clearSelection}
        onChanged={() => setRevision(value => value + 1)} onError={setSelectionError} notify={notify}/>}/>
    </WorkspaceChrome>
    {data?.notice && <p role="status">{data.notice}</p>}
    {error ? <WorkspaceEmptyState size="compact"  role="alert"><strong>{error}</strong><Button onClick={()=>setRevision(r=>r+1)}>Retry</Button></WorkspaceEmptyState> : !data ? <div className="loading-state" role="status">Loading TV shows…</div> : <>
      <Pagination total={data.total} page={page} totalPages={data.total_pages} hasNext={data.has_next} pageStart={(page-1)*(data.page_size||pageSize)} pageEnd={(page-1)*(data.page_size||pageSize)+data.items.length} ariaLabel="TV page controls above results" onPageChange={setPage}/>

      {!data.items.length?<WorkspaceEmptyState size="compact" ><strong>{data.continue_scan?'Still looking for matching series.':query.groups.length || status?'No series match your search.':'No TV series yet.'}</strong></WorkspaceEmptyState>:<div ref={attachGrid} className="tv-series-grid">{data.items.map(series=><TVSeriesCard key={series.tmdb_id} series={series} context={context} onOpen={open} onPlay={play} onWatchlist={toggleWatchlist} onWatched={toggleWatched} onPosterEdit={setPosterEditor} onSelect={select} selected={selectedRows.has(series.tmdb_id ? `tmdb:${series.tmdb_id}` : `local:${series.id}`)}/>)}</div>}
      {data.continue_scan && <Button onClick={()=>setRevision(r=>r+1)}>Continue searching</Button>}
      <Pagination total={data.total} page={page} totalPages={data.total_pages} hasNext={data.has_next} pageStart={(page-1)*(data.page_size||pageSize)} pageEnd={(page-1)*(data.page_size||pageSize)+data.items.length} ariaLabel="TV pagination" onPageChange={setPage}/>
    </>}
    {posterEditor && <TVPosterEditor series={posterEditor} onClose={() => setPosterEditor(null)} onSaved={() => setRevision(value => value + 1)} notify={notify} />}
    </>}
  </section>;
}
