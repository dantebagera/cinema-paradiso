import Badge from '../../components/ui/Badge.jsx';
import Button, { StreamButton } from '../../components/ui/Button.jsx';
import WorkspaceEmptyState from '../../components/WorkspaceEmptyState.jsx';
import {
  AlertTriangle, ArrowRight, Bell, Download, Film, HardDrive, Link as LinkIcon, Loader2, MonitorPlay,
  Play, RefreshCw, ScanSearch, Search, Sparkles, Trash2, Wand2, X
} from 'lucide-react';
import { memo, useCallback, useEffect, useId, useRef, useState } from 'react';
import homeHeaderArtUrl from '../../assets/home-film-projector.png';
import HorizontalCardRail from '../../components/HorizontalCardRail.jsx';
import HomeTrailersPanel from './HomeTrailersPanel.jsx';
import SourceReviewDialog from '../../components/SourceReviewDialog.jsx';
import Tooltip from '../../components/Tooltip.jsx';
import SearchModeSelect from '../search/SearchModeSelect.jsx';
import useDismissiblePopover from '../../hooks/useDismissiblePopover.js';
import { previewSourceReview } from '../../api/sourceReview.js';
import './home.css';
import { movieDisplayTitle } from '../../utils/movieLanguage.js';
import { MovieLanguageToggle, useTransientMovieLanguage } from '../../components/MovieLanguageToggle.jsx';
import { OwnedFileDetailsButton, PosterEditButton, PosterStateControls } from '../../components/SharedMovieCards.jsx';
import { ContinueMovieCard, UnifiedMovieCard, UpcomingMovieCard } from '../../components/movie-card/MovieCard.jsx';
import { useMovieAwardCounts } from '../../components/MovieAwardsContext.jsx';
import { cx, formatCount, movieKey, sortFollowedReleases } from '../../utils/appUtils.js';
import { canonicalOwnedMovie, listsForDiscoverMovie, ownedMovieFor } from '../../discoverUtils.js';
import { getCompactQualityLabel } from '../../utils/libraryUtils.js';
import { formatReleaseDateLabel, formatVoteCount, isUnreleasedMovie } from '../../utils/moviePresentation.js';

export default memo(function HomeWorkspace(props) {
  const { stats, statsError, statsUpdatedAt, loading, movies, moviesFallback, upcomingMovies, upcomingError,
    homeTrailers, homeTrailersError, ownership, followed, followedChecking, onScanFollowed,
    selectedMovie, selectedOwnership, selectedDetails, onSelectSection, onOpenDiscoverList, onOpenCleanup,
    onSelectMovie, onOpenHomeTrailer, onRetryHomeTrailers, onLoadMoreHomeTrailers, onRetryStats, onRetryHomeMovies,
    onPlay, onStream, streamingAvailable, streamingLabel, onFindTorrent, onTrailer, onFollow, userLists,
    onToggleSystemList, onEditPoster, onOpenFileDetails, continueWatching = [], onResumeWatching,
    onRestartWatching, onRemoveWatching, onViewWatchingCard, notify } = props;
  const [sourceReview, setSourceReview] = useState(null);
  const sourceRequest = useRef(0);
  const downloadTrigger = useRef(null);
  const [detailSection, setDetailSection] = useState('trending');
  const gridRef = useRef(null);
  const detailRef = useRef(null);
  const origin = useRef(null);
  const restoreGeneration = useRef(0);
  const selectedKey = selectedMovie ? movieKey(selectedMovie) : '';
  const selectedFollowedMovie = followed.find(item => movieKey(item) === selectedKey) || null;
  const closeSourceReview = useCallback(() => {
    const request = ++sourceRequest.current;
    setSourceReview(null);
    // The loading trigger is disabled until React commits the closed state.
    window.requestAnimationFrame(() => {
      if (request === sourceRequest.current && downloadTrigger.current?.getClientRects().length && !downloadTrigger.current.disabled) {
        downloadTrigger.current.focus({ preventScroll: true });
      }
    });
  }, []);
  useDismissiblePopover(Boolean(sourceReview), closeSourceReview, downloadTrigger, gridRef, undefined,
    { dismissOutside: false, workspaceOnly: true });
  useEffect(() => () => { sourceRequest.current += 1; }, []);
  async function downloadAvailable(movies) {
    if (!movies.length) return;
    const request = ++sourceRequest.current;
    setSourceReview({ loading: true, rows: [], error: '', title: 'Download available followed movies' });
    try {
      const data = await previewSourceReview(movies.map(movie => ({
        tmdb_id: movie.tmdb_id || '', imdb_id: movie.imdb_id || '',
        title: movie.title, year: movie.year, poster_url: movie.poster_url
      })));
      if (request !== sourceRequest.current) return;
      setSourceReview({ loading: false, rows: data.rows || [], blocked: data.blocked || [],
        defaults: data.defaults || {}, error: '', title: 'Download available followed movies' });
    } catch (error) {
      if (request === sourceRequest.current) setSourceReview(current => ({ ...current, loading: false, error: error.message }));
    }
  }
  function selectMovie(movie, section) {
    if (movieKey(movie) === selectedKey && section === detailSection) { closeDetails(); return; }
    const workspace = gridRef.current?.closest('.workspace');
    restoreGeneration.current += 1;
    origin.current = { workspace, top: workspace?.scrollTop || 0, element: document.activeElement };
    setDetailSection(section);
    onSelectMovie(movie);
  }
  function closeDetails() {
    const generation = ++restoreGeneration.current;
    onSelectMovie(null);
    requestAnimationFrame(() => requestAnimationFrame(() => {
      const saved = origin.current;
      if (generation !== restoreGeneration.current || !saved || !gridRef.current || gridRef.current.closest('.workspace-panel')?.hidden) return;
      saved.workspace?.scrollTo({ top: saved.top, behavior: 'instant' });
      saved.element?.focus({ preventScroll: true });
      origin.current = null;
    }));
  }
  useEffect(() => {
    if (!selectedKey || gridRef.current?.closest('.workspace-panel')?.hidden) return;
    const frame = requestAnimationFrame(() => detailRef.current?.scrollIntoView({ block: 'nearest', behavior: 'instant' }));
    return () => cancelAnimationFrame(frame);
  }, [selectedKey, detailSection]);
  function detailsFor(section) {
    if (!selectedMovie || detailSection !== section) return null;
    return <div className="home-inline-details" ref={detailRef}>
      <div className="home-details-heading"><span>Movie details</span><button onClick={closeDetails} aria-label="Close movie details"><X size={17} />Close</button></div>
      <MovieInspector movie={selectedMovie} owned={selectedOwnership} details={selectedDetails} followedMovie={selectedFollowedMovie}
        watched={listsForDiscoverMovie(selectedMovie, userLists, selectedOwnership).some(list => list.system_type === 'watched')}
        watchlisted={listsForDiscoverMovie(selectedMovie, userLists, selectedOwnership).some(list => list.system_type === 'watchlist')}
        onClose={closeDetails} onPlay={onPlay} onStream={onStream} streamingAvailable={streamingAvailable} streamingLabel={streamingLabel}
        onFindTorrent={onFindTorrent} onTrailer={onTrailer} onFollow={onFollow}
        onToggleWatched={selectedOwnership ? () => onToggleSystemList('watched', selectedMovie, selectedOwnership) : undefined}
        onToggleWatchlist={() => onToggleSystemList('watchlist', selectedMovie, selectedOwnership)}
        onEditPoster={selectedOwnership ? () => onEditPoster(selectedOwnership, selectedMovie) : undefined} onOpenFileDetails={onOpenFileDetails} />
    </div>;
  }
  return <div ref={gridRef} className="home-grid">
    <section className="hero-panel" aria-labelledby="home-banner-title">
      <img className="home-hero-art" src={homeHeaderArtUrl} alt="" aria-hidden="true" />
      <div className="hero-copy">
        <div className="home-hero-title-row"><h1 id="home-banner-title">Home</h1><p className="screen-kicker">Cinematic archive console</p></div>
        <h2>Your movie archive, under command.</h2>
        <p>A richer movie library. More to discover. AI to guide you. Ready to stream.</p>
      </div>
    </section>
    <div className="home-status-grid">
    <HealthPanel stats={stats} error={statsError} updatedAt={statsUpdatedAt} loading={loading.stats} onRetry={onRetryStats} onOpenLibrary={() => onSelectSection('library')} onOpenCleanup={onOpenCleanup} />
    <section className="home-followed-section"><ReleasePanel followed={followed} checking={followedChecking} onScan={onScanFollowed} onSelectMovie={movie => selectMovie(movie, 'followed')} onDownload={downloadAvailable} downloadTrigger={downloadTrigger} preparing={Boolean(sourceReview?.loading)} /></section>
    {detailsFor('followed')}
    </div>
    <HomeTrailersPanel feed={homeTrailers} loading={loading.trailers} refreshing={loading.trailersRefreshing} loadingMore={loading.trailersMore} error={homeTrailersError} onOpenVideo={onOpenHomeTrailer} onRetry={onRetryHomeTrailers} onLoadMore={onLoadMoreHomeTrailers} />
    {continueWatching.length > 0 && <ContinueWatchingRail items={continueWatching} onResume={onResumeWatching} onRestart={onRestartWatching} onRemove={onRemoveWatching} onViewCard={onViewWatchingCard} />}
    <div className="home-poster-stack">
    <section className="movie-rail home-poster-section" aria-label="Trending movies">
      <HorizontalCardRail label="Trending movies" arrowPlacement="edges" visibleCount={7} minCardWidth={176} trackClassName="home-trending-track" header={<div className="section-heading"><div><h3>{moviesFallback ? 'Movie suggestions' : 'Trending movies'}</h3><p>{moviesFallback ? 'Trending is unavailable. Showing saved suggestions.' : 'Popular this week.'}</p></div><button className="home-section-link" onClick={() => onSelectSection('discover')}>Open Discover<ArrowRight size={15} /></button></div>}>
        {loading.movies ? Array.from({ length: 7 }, (_, index) => <div className="upcoming-movie-card skeleton-card" key={index} />) : movies.map(movie => {
          const display = canonicalOwnedMovie(movie, ownedMovieFor(movie, ownership));
          return <UpcomingMovieCard key={movieKey(movie)} title={movieDisplayTitle(display)} posterUrl={display.poster_url} backdropUrl={display.backdrop_url} releaseLabel={display.year} selected={movieKey(movie) === selectedKey} onSelect={() => selectMovie(movie, 'trending')} />;
        })}
      </HorizontalCardRail>{detailsFor('trending')}
    </section>
    <ComingSoonPanel movies={upcomingMovies} loading={loading.upcoming} error={upcomingError} selectedMovie={selectedMovie} onSelectMovie={movie => selectMovie(movie, 'upcoming')} onViewAll={() => onOpenDiscoverList('upcoming')} onRetry={onRetryHomeMovies}>{detailsFor('upcoming')}</ComingSoonPanel>
    </div>
    {sourceReview && <SourceReviewDialog state={sourceReview} setState={setSourceReview} onClose={closeSourceReview} notify={notify} />}
  </div>;
});

function ComingSoonPanel({ movies, loading, error, selectedMovie, onSelectMovie, onViewAll, onRetry, children }) {
  return <section className="coming-soon-panel home-poster-section" aria-labelledby="coming-soon-heading">
    <HorizontalCardRail label="Upcoming movies" arrowPlacement="edges" visibleCount={7} minCardWidth={176} trackClassName="coming-soon-grid" header={<div className="section-heading"><h3 id="coming-soon-heading">Coming soon</h3><button className="home-section-link" onClick={onViewAll}>View all<ArrowRight size={15} /></button></div>}>
      {loading ? Array.from({ length: 7 }, (_, index) => <div className="upcoming-movie-card skeleton-card" key={index} />) : !error && (movies || []).map(movie => <UpcomingMovieCard key={movieKey(movie)} title={movieDisplayTitle(movie)} posterUrl={movie.poster_url} backdropUrl={movie.backdrop_url} releaseLabel={formatReleaseDateLabel(movie.release_date)} selected={movieKey(movie) === movieKey(selectedMovie || {})} onSelect={() => onSelectMovie(movie)} />)}
    </HorizontalCardRail>
    {!loading && (error || !movies?.length) && <div className="home-feed-empty"><Sparkles size={22} /><strong>{error ? 'Upcoming movies are temporarily unavailable.' : 'No upcoming movies are available.'}</strong>{error && <><span>{error}</span><button className="ghost-link" onClick={onRetry}>Retry</button></>}</div>}
    {children}
  </section>;
}

function remainingLabel(seconds) {
  const minutes = Math.max(1, Math.ceil((Number(seconds) || 0) / 60));
  if (minutes < 60) return `${minutes} min remaining`;
  const hours = Math.floor(minutes / 60);
  const remainder = minutes % 60;
  return remainder ? `${hours} hr ${remainder} min remaining` : `${hours} hr remaining`;
}

function ContinueWatchingRail({ items, onResume, onRestart, onRemove, onViewCard }) {
  const menuGroup = useId();
  return <section className="continue-watching-panel" aria-labelledby="continue-watching-heading">
    <HorizontalCardRail label="Continue Watching" arrowPlacement="header" cardWidth="156px" nativeScrollbar trackClassName="continue-watching-viewport" trackRole="region" trackLabel={items.some(item => item.media_type === 'tv') ? 'Continue Watching movies and TV shows' : 'Continue Watching movies'} header={<div className="section-heading"><div><p className="screen-kicker">Your screening room</p><h3 id="continue-watching-heading">Continue Watching</h3></div></div>}>
        {items.map(item => <ContinueMovieCard key={item.path_key} title={item.media_type === 'tv' ? item.title : movieDisplayTitle(item)} menuGroup={menuGroup} posterUrl={item.poster_url} backdropUrl={item.backdrop_url} progress={item.progress}
          remainingLabel={item.media_type === 'tv' ? `${item.primary_action.label} · ${item.primary_action.target.code} · ${item.primary_action.target.title}${item.primary_action.playable ? '' : ' · Missing locally'}` : remainingLabel(item.remaining_seconds)}
          onResume={() => onResume(item)} onRestart={() => onRestart(item)} onRemove={() => onRemove(item)} onViewCard={item.media_type !== 'tv' ? () => onViewCard(item) : undefined} />)}
    </HorizontalCardRail>
  </section>;
}

function HealthPanel({ stats, loading, error, updatedAt, onRetry, onOpenLibrary, onOpenCleanup }) {
  const cards = [
    { label: 'Files', value: stats?.total_files, detail: `${formatCount(stats?.unique_titles)} unique titles`, icon: HardDrive, tone: 'blue' },
    { label: 'Low quality', value: stats?.low_quality_count, detail: 'below 1080p', icon: AlertTriangle, tone: 'amber', tab: 'low' },
    { label: 'Duplicates', value: stats?.duplicate_groups, detail: `${formatCount(stats?.extra_copies)} extra copies`, icon: Trash2, tone: 'red', tab: 'duplicates' },
    { label: 'Unmatched', value: stats?.unmatched_count, detail: 'files without accepted metadata', icon: LinkIcon, tone: 'violet', tab: 'unmatched' },
    { label: 'Identity review', value: stats?.identity_review_count, detail: `${formatCount(stats?.identity_review_recommended)} recommended corrections`, icon: ScanSearch, tone: 'cyan', tab: 'identity' }
  ];
  return <section className="health-panel" aria-label="Library health">
    <div className="section-heading"><div><p className="screen-kicker">Library health</p><h3>Offline archive status</h3></div>{loading && <Loader2 className="spin" size={18} />}</div>
    {loading && !stats ? <div className="home-health-state" role="status"><Loader2 className="spin" size={22} /><span>Loading library status…</span></div> : !stats ? <div className="home-health-state" role="status"><AlertTriangle size={22} /><div><strong>Library status is unavailable</strong><p>{error || 'Counts could not be refreshed.'}</p></div><button className="ghost-link" onClick={onRetry} disabled={loading}>Retry</button></div> : <>
      {error && <div className="home-health-stale" role="status"><span>Showing last-known library status.</span><button className="home-section-link" onClick={onRetry} disabled={loading}>Retry</button></div>}
      {Number(stats.total_files) === 0 ? <div className="home-health-state"><HardDrive size={25} /><div><strong>Your local library is empty</strong><p>Add your media folders to start organizing your collection.</p></div><button className="ghost-link" onClick={onOpenLibrary}>Add folders<ArrowRight size={15} /></button></div> : <div className="health-cards">{cards.map(card => {
        const Icon = card.icon;
        const Card = card.tab ? 'button' : 'article';
        return <Card key={card.label} type={card.tab ? 'button' : undefined} className={cx('health-card', card.tab && 'health-card-action', `tone-${card.tone}`)} onClick={card.tab ? () => onOpenCleanup(card.tab) : undefined}><Icon size={18} /><strong>{formatCount(card.value)}</strong><span>{card.label}</span><small>{card.detail}</small></Card>;
      })}</div>}
      {updatedAt && <small className="home-health-freshness">{loading ? 'Refreshing…' : `Refreshed ${new Date(updatedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`}</small>}
    </>}
  </section>;
}

const RELEASE_LABELS = { all: 'All', available: 'Available', monitoring: 'Monitoring', awaiting: 'Awaiting release', owned: 'Owned' };

function releaseStatus(movie) {
  if (movie.status === 'available' || movie.status === 'owned') return movie.status;
  return isUnreleasedMovie(movie) ? 'awaiting' : 'monitoring';
}

function ReleasePanel({ followed, checking, onScan, onSelectMovie, onDownload, downloadTrigger, preparing }) {
  const [filter, setFilter] = useState('all');
  const listRef = useRef(null);
  const sorted = sortFollowedReleases(followed);
  const available = sorted.filter(movie => releaseStatus(movie) === 'available');
  const visible = sorted.filter(movie => filter === 'all' || releaseStatus(movie) === filter);
  return (
    <section className="release-panel">
      <p className="screen-kicker">Release watchlist</p>
      <div className="section-heading">
        <h3>Followed movies</h3>
        <div className="release-heading-actions">
          <Tooltip title="Download all available movies" description="Uses CP's shared bulk source review, regardless of the active filter.">
            <button ref={downloadTrigger} type="button" className="release-sync-button release-download-button"
              aria-label="Download all available followed movies" disabled={!available.length || preparing} onClick={() => onDownload(available)}>
              {preparing ? <Loader2 className="spin" size={17} /> : <Download size={17} />}
            </button>
          </Tooltip>
          <span className={cx('release-available-indicator', available.length > 0 && 'release-available-indicator-hot')}
            role="img" aria-label={`${formatCount(available.length)} available followed movies`}>
            <Bell size={18} aria-hidden="true" /><span className="release-available-badge" aria-hidden="true">{formatCount(available.length)}</span>
          </span>
          <button
            type="button"
            className="release-sync-button"
            onClick={onScan}
            disabled={checking}
            aria-label={checking ? 'Scanning followed releases' : 'Scan followed releases'}
            title={checking ? 'Scanning followed releases' : 'Scan followed releases'}
          >
            <RefreshCw className={checking ? 'spin' : ''} size={17} />
          </button>
          <span className="release-filter-count" aria-live="polite" aria-label={`${formatCount(visible.length)} movies in ${RELEASE_LABELS[filter]}`}>{formatCount(visible.length)}</span>
          <SearchModeSelect className="release-status-filter" aria-label="Filter followed movies" value={filter}
            onChange={event => { setFilter(event.target.value); listRef.current?.scrollTo({ top: 0 }); }}>
            {['all', 'available', 'monitoring', 'awaiting'].map(value => <option key={value} value={value}>{RELEASE_LABELS[value]}</option>)}
          </SearchModeSelect>
        </div>
      </div>
      <div className="release-list" ref={listRef}>
        {visible.length ? visible.map((movie, index) => (
          <button
            className={cx('release-item', `release-item-${movie.status || 'watching'}`, `release-status-${releaseStatus(movie)}`)}
            key={`${movie.tmdb_id || movie.title}-${index}`}
            onClick={() => onSelectMovie(movie)}
            type="button"
          >
            <span className="release-pulse" />
            <span>
              <strong dir="auto">{movieDisplayTitle(movie)}</strong>
              <small>{movie.year || 'Unknown year'}</small>
            </span>
            <em>{RELEASE_LABELS[releaseStatus(movie)]}</em>
          </button>
        )) : (
          <WorkspaceEmptyState size="compact" >
            <strong>{followed.length ? 'No followed releases in this filter.' : 'No followed releases yet.'}</strong>
            <span>{followed.length ? 'Choose another filter to see your followed movies.' : 'Use Follow on a Discover card to watch for a proper WEBRip, Blu-ray, or BDRip copy.'}</span>
          </WorkspaceEmptyState>
        )}
      </div>
    </section>
  );
}

function MovieInspector({
  movie, owned, details, followedMovie, watched, watchlisted,
  onClose, onPlay, onStream, streamingAvailable, streamingLabel, onFindTorrent, onFollow,
  onTrailer, onToggleWatched, onToggleWatchlist, onEditPoster, onOpenFileDetails
}) {
  const baseDisplayMovie = canonicalOwnedMovie(movie, owned);
  const ownedItem = owned?.canonical_card || owned?.library_item || {};
  const ownedCanonical = ownedItem.canonical_metadata || {};
  const baseDisplayDetails = ownedCanonical.accepted ? {
    ...(details || {}),
    ...ownedCanonical,
    loading: details?.loading,
    error: details?.error,
    trailer_url: details?.trailer_url || ownedCanonical.trailer_url || ''
  } : details;
  const { displayMovie, displayDetails, toggleProps } = useTransientMovieLanguage({ movie: baseDisplayMovie, details: baseDisplayDetails, expanded: true });
  const lowQuality = Boolean(owned?.maintenance_upgrade_candidate);
  const unreleased = !owned && isUnreleasedMovie(displayMovie);
  const releaseAvailable = followedMovie?.status === 'available';
  const sourceActionsAllowed = releaseAvailable || !unreleased;
  const releaseDateLabel = unreleased ? formatReleaseDateLabel(displayMovie.release_date) : '';
  const cast = displayDetails?.cast || displayMovie.cast || [];
  const trailerUrl = displayDetails?.trailer_url || '';

  const awardCounts = useMovieAwardCounts(displayMovie, { enabled: true });
  return <UnifiedMovieCard ratingsIdentity={displayMovie} className="home-detail-card movie-awards-consumer" expanded onToggle={onClose} title={displayMovie.title} year={displayMovie.year}
    posterUrl={displayMovie.poster_url} backdropUrl={displayDetails?.backdrop_url || displayMovie.backdrop_url}
    awardCounts={awardCounts} rating={displayMovie.tmdb_rating} voteCount={formatVoteCount(displayMovie.tmdb_vote_count)} chips={displayMovie.genres || []}
    mutedChips={[displayMovie.language, displayMovie.country_flag || displayMovie.country, owned ? getCompactQualityLabel(ownedItem) : '']}
    statusLabel={owned ? (lowQuality ? 'Upgrade candidate' : 'In library') : unreleased ? 'Unreleased' : 'Not in library'}
    ownedBadge={Boolean(owned)} following={Boolean(followedMovie)}
    cornerControls={<><PosterStateControls title={displayMovie.title} watched={watched} watchlisted={watchlisted} onToggleWatched={owned ? onToggleWatched : undefined} onToggleWatchlist={onToggleWatchlist} /><PosterEditButton title={displayMovie.title} onEdit={owned ? onEditPoster : undefined} /></>}
    metadataActions={<>
        <MovieLanguageToggle {...toggleProps} />
        {owned ? (
          <>
            <Button variant="play" type="button"  onClick={() => onPlay(owned.path)}>
              <Play size={15} /> Play from HDD
            </Button>
            <OwnedFileDetailsButton owned={ownedItem} onOpenFileDetails={onOpenFileDetails} />
            {lowQuality && (
              <Button type="button"  onClick={() => onFindTorrent(baseDisplayMovie, true)}>
                <Wand2 size={15} /> Find upgrade
              </Button>
            )}
          </>
        ) : (
          <>
            {sourceActionsAllowed && (
              <Button variant="primary" type="button"  onClick={() => onFindTorrent(baseDisplayMovie)}>
                <Search size={15} /> Find torrent
              </Button>
            )}
            <Button type="button"  onClick={() => onFollow(baseDisplayMovie)}>
              <Bell size={15} /> {followedMovie ? 'Following' : 'Follow release'}
            </Button>
          </>
        )}
        {sourceActionsAllowed && streamingAvailable && (
          <StreamButton type="button"  onClick={() => onStream(baseDisplayMovie)}>
             {streamingLabel}
          </StreamButton>
        )}
        {displayDetails && (
          <Button type="button"  onClick={() => onTrailer(baseDisplayMovie, trailerUrl)}>
            <Film size={15} /> Play trailer
          </Button>
        )}
    </>}
    expandedBody={<div className="home-detail-body">
      {releaseDateLabel && <p>Releases {releaseDateLabel}</p>}
      <p className="plot-text">{displayDetails?.summary || displayDetails?.plot || displayMovie.summary || displayMovie.plot || 'No plot summary is available yet.'}</p>
      <div className="cast-strip"><span className="mini-label">Top cast</span>{displayDetails?.error ? <small role="status">Details could not be refreshed: {displayDetails.error}</small> : !displayDetails ? <small>Loading cast…</small> : cast.length ? cast.slice(0, 5).map(person => <Badge size="compact" muted className="cast-chip" key={person.id || person.name}>{person.name}</Badge>) : <small>No cast data found.</small>}</div>
    </div>} />;
}
