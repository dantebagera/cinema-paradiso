import Badge from './ui/Badge.jsx';
import DialogShell, { DialogHeader } from './ui/DialogShell.jsx';
import Button, { StreamButton } from './ui/Button.jsx';
import IPTVAvailabilityBadge from './IPTVAvailabilityBadge.jsx';
import {
  AlertTriangle, Bell, Bookmark, BookOpen, Check, Clapperboard, ExternalLink, Film, Loader2,
  FileText, MonitorPlay, Pencil, Play, RefreshCcw, Search, Sparkles, Trash2, Wand2, X
} from 'lucide-react';
import { useCallback, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { mergeCanonicalMovieDetails } from '../api/movieDetails.js';
import SelectionCheckbox from './SelectionCheckbox.jsx';
import { MovieLanguageToggle, useTransientMovieLanguage } from './MovieLanguageToggle.jsx';
import { UnifiedMovieCard } from './movie-card/MovieCard.jsx';
import { cx, formatCount } from '../utils/appUtils.js';
import {
  getCompactQualityLabel, getLocaleTag, getMovieIdentity, getRolePeople
} from '../utils/libraryUtils.js';
import {
  formatReleaseDateLabel, formatVoteCount, isUnreleasedMovie
} from '../utils/moviePresentation.js';
import { canonicalOwnedMovie } from '../discoverUtils.js';
import RelatedMovieRail from './RelatedMovieRail.jsx';
import HorizontalCardRail from './HorizontalCardRail.jsx';
import { PersonBioModal, PersonCreditCard, usePersonBiography } from './PersonCreditCard.jsx';
import { useMovieAwardCounts, usePersonAwardCounts } from './MovieAwardsContext.jsx';

function usePendingPlay(onPlay, path) {
  const [pending, setPending] = useState(false);
  const pendingRef = useRef(false);

  const play = useCallback(async () => {
    if (!onPlay || !path || pendingRef.current) return null;
    pendingRef.current = true;
    setPending(true);
    try {
      return await onPlay(path);
    } finally {
      pendingRef.current = false;
      setPending(false);
    }
  }, [onPlay, path]);

  return { pending, play };
}

function MoviePlayButton({ pending, onPlay }) {
  return (
    <Button variant="play"
      type="button"
      className="movie-play-action"
      onClick={onPlay}
      disabled={pending}
      aria-busy={pending || undefined}
    >
      {pending ? <Loader2 size={15} className="spin" /> : <Play size={15} />}
      {pending ? 'Opening player…' : 'Play'}
    </Button>
  );
}

export function MoviePlotDetailsButton({ movie }) {
  const [open, setOpen] = useState(false);
  const plot = movie?.summary || movie?.plot || '';
  if (plot.length <= 200) return null;
  return <>
    <Button type="button" className="movie-plot-action" onClick={() => setOpen(true)}><BookOpen size={15} /> Read full plot</Button>
    {open && createPortal(<div className="modal-backdrop" onClick={() => setOpen(false)}>
      <DialogShell size="plot" className="movie-plot-dialog" role="dialog" aria-modal="true" aria-label={`Plot of ${movie.title}`} onClick={(event) => event.stopPropagation()} onKeyDown={(event) => { if (event.key === 'Escape') setOpen(false); }}>
        <DialogHeader as="header"><h3>{movie.title}</h3><Button size="compact" type="button"  autoFocus onClick={() => setOpen(false)}>Close</Button></DialogHeader>
        <p dir="auto">{plot}</p>
      </DialogShell>
    </div>, document.body)}
  </>;
}

export function PosterEditButton({ title, onEdit }) {
  if (!onEdit) return null;
  return (
    <button
      type="button"
      className="poster-edit-trigger"
      aria-label={`Edit poster for ${title || 'movie'}`}
      title="Edit poster"
      onClick={(event) => {
        event.stopPropagation();
        onEdit();
      }}
    >
      <Pencil size={17} />
    </button>
  );
}

export function OwnedFileDetailsButton({ owned, onOpenFileDetails }) {
  const ownedItem = owned?.canonical_card || owned?.library_item || owned;
  if (!ownedItem?.path || !onOpenFileDetails) return null;
  return (
    <Button type="button"  onClick={() => onOpenFileDetails(ownedItem)}>
      <FileText size={15} /> File details
    </Button>
  );
}

export function PosterStateControls({
  title,
  watched,
  watchlisted,
  onToggleWatched,
  onToggleWatchlist,
  watchedDisabledReason,
  notify
}) {
  if (!onToggleWatched && !onToggleWatchlist && !watchedDisabledReason) return null;
  return (
    <>
      {(onToggleWatched || watchedDisabledReason) && (
        <button
          type="button"
          className={cx('poster-state-control', 'poster-state-watched', watched && 'poster-state-control-active')}
          aria-label={watchedDisabledReason || (watched ? `Mark ${title} as unwatched` : `Mark ${title} as watched`)}
          title={watchedDisabledReason || (watched ? 'Mark as unwatched' : 'Mark as watched')}
          disabled={Boolean(watchedDisabledReason)}
          onClick={(event) => {
            event.stopPropagation();
            onToggleWatched();
          }}
        >
          <Check size={17} />
        </button>
      )}
      {onToggleWatchlist && (
        <button
          type="button"
          className={cx('poster-state-control', 'poster-state-watchlist', watchlisted && 'poster-state-control-active')}
          aria-label={watchlisted ? `Remove ${title} from watchlist` : `Add ${title} to watchlist`}
          title={watchlisted ? 'Remove from watchlist' : 'Add to watchlist'}
          onClick={(event) => {
            event.stopPropagation();
            onToggleWatchlist();
          }}
        >
          <Bookmark size={16} fill={watchlisted ? 'currentColor' : 'none'} />
        </button>
      )}
    </>
  );
}

export function DiscoverMovieCard({
  iptvAvailability,
  movie,
  reason,
  owned,
  followed,
  expanded,
  details,
  collection,
  collectionStatus,
  collectionError,
  itemLists,
  onPlay,
  onStream,
  streamingAvailable,
  streamingLabel,
  onFindTorrent,
  onFollow,
  onTrailer,
  onToggleDetails,
  onPersonBrowse,
  onPersonDiscover,
  onPersonAwardDiscover,
  onCollectionBrowse,
  onCollectionRetry,
  onListBrowse,
  onEditLists,
  onRemoveFromList,
  onEditPoster,
  onOpenFileDetails,
  watched,
  watchlisted,
  onToggleWatched,
  onToggleWatchlist,
  selected,
  onSelect
}) {
  const ownedItem = owned?.canonical_card || owned?.library_item || {};
  const ownedCanonical = ownedItem.canonical_metadata || {};
  const baseDisplayMovie = canonicalOwnedMovie(movie, owned);
  const baseDisplayDetails = ownedCanonical.accepted ? {
    ...mergeCanonicalMovieDetails(ownedCanonical, details || {}),
    loading: details?.loading,
    error: details?.error,
    trailer_url: details?.trailer_url || ownedCanonical.trailer_url || ''
  } : details;
  const languageView = useTransientMovieLanguage({
    movie: baseDisplayMovie,
    details: baseDisplayDetails,
    expanded
  });
  const displayMovie = languageView.displayMovie;
  const awardCounts = useMovieAwardCounts(baseDisplayMovie, { enabled: true });
  const displayDetails = languageView.displayDetails;
  const displayCollection = languageView.isArabic && displayDetails?.collection?.id
    ? { ...(collection || {}), ...displayDetails.collection }
    : (collection?.id ? collection : displayMovie.collection || {});
  const lowQuality = Boolean(owned?.maintenance_upgrade_candidate);
  const unreleased = !owned && isUnreleasedMovie(displayMovie);
  const ownedPath = owned?.path || '';
  const playAction = usePendingPlay(onPlay, ownedPath);
  return (
    <UnifiedMovieCard ratingsIdentity={displayMovie}
      availability={iptvAvailability && Number(movie.tmdb_id) > 0
        ? <IPTVAvailabilityBadge movie={movie} providers={iptvAvailability.providers} onStream={onStream} /> : undefined}
      className={cx('discover-movie-card', 'movie-awards-consumer', expanded && 'discover-card-expanded')}
      awardCounts={awardCounts}
      title={displayMovie.title}
      year={displayMovie.year}
      posterUrl={displayMovie.poster_url}
      backdropUrl={displayDetails?.backdrop_url || displayMovie.backdrop_url || displayMovie.poster_url}
      rating={displayMovie.tmdb_rating}
      voteCount={formatVoteCount(displayMovie.tmdb_vote_count, { includeLabel: expanded })}
      chips={(displayMovie.genres || []).slice(0, 2)}
      mutedChips={[
        displayMovie.language,
        displayMovie.country_flag || displayMovie.country,
        {
          label: expanded ? displayDetails?.certification || displayMovie.certification : '',
          tone: 'certification'
        },
        owned ? getCompactQualityLabel(ownedItem) : ''
      ]}
      statusLabel={owned ? (lowQuality ? 'Upgrade candidate' : '') : (unreleased ? 'Unreleased' : (followed ? '' : 'Not in library'))}
      statusTone={owned ? (lowQuality ? 'warning' : 'neutral') : (unreleased ? 'warning' : 'missing')}
      following={followed}
      ownedBadge={Boolean(owned)}
      expanded={expanded}
      onToggle={onToggleDetails}
      headerActions={expanded ? (
        <MovieImdbLink
          imdbId={displayDetails?.imdb_id || displayMovie.imdb_id}
          title={displayMovie.title}
        />
      ) : null}
      metadataActions={expanded ? (
        <MovieLanguageToggle {...languageView.toggleProps} />
      ) : null}
      showPlayOverlay={Boolean(owned)}
      onPlay={ownedPath ? playAction.play : undefined}
      playPending={playAction.pending}
      cornerControls={(
        <>
          <PosterStateControls
            title={displayMovie.title}
            watched={watched}
            watchlisted={watchlisted}
            onToggleWatched={owned ? onToggleWatched : undefined}
            onToggleWatchlist={onToggleWatchlist}
          />
          <PosterEditButton title={displayMovie.title} onEdit={owned ? onEditPoster : undefined} />
          <SelectionCheckbox
            className="discover-selection-checkbox"
            checked={Boolean(selected)}
            onChange={onSelect}
            label={`Select ${displayMovie.title}`}
          />
        </>
      )}
      expandedBody={expanded ? (
        <MovieExpandedCuration
          movie={displayMovie}
          details={displayDetails}
          collection={displayCollection}
          collectionStatus={collectionStatus}
          collectionError={collectionError}
          itemLists={itemLists}
          onCollectionBrowse={onCollectionBrowse}
          onCollectionRetry={onCollectionRetry}
          onListBrowse={onListBrowse}
          onEditLists={onEditLists}
          onRemoveFromList={onRemoveFromList}
        />
      ) : null}
      expandedFooter={expanded ? (
        <MovieExpandedDetails
          movie={baseDisplayMovie}
          details={displayDetails}
          directors={displayMovie.directors}
          cast={displayMovie.cast}
          onPersonBrowse={onPersonBrowse}
          onPersonDiscover={onPersonDiscover}
          onPersonAwardDiscover={onPersonAwardDiscover}
        />
      ) : null}
    >
      {expanded && (
        <>
          {reason && <p className="ai-reason"><Sparkles size={14} /> {reason}</p>}
          <p className="movie-card-plot discover-plot-visible" dir={languageView.isArabic ? 'rtl' : undefined}>
            {displayMovie.summary || displayMovie.plot || 'No plot summary is available yet.'}
          </p>
          <MovieKeywordRow keywords={displayDetails?.keywords || displayMovie.keywords} />
          <div className="card-actions">
            {owned ? (
              <>
                <MoviePlayButton pending={playAction.pending} onPlay={playAction.play} />
                <OwnedFileDetailsButton owned={ownedItem} onOpenFileDetails={onOpenFileDetails} />
                {lowQuality && (
                  <Button type="button"  onClick={() => onFindTorrent(baseDisplayMovie, true)}>
                    <Wand2 size={15} /> Find upgrade
                  </Button>
                )}
              </>
            ) : (
              <>
                {!unreleased && (
                  <Button variant="primary" type="button"  onClick={() => onFindTorrent(movie)}>
                    <Search size={15} /> Find sources
                  </Button>
                )}
                {!unreleased && streamingAvailable && (
                  <StreamButton type="button"  onClick={() => onStream(movie)}>
                     {streamingLabel}
                  </StreamButton>
                )}
              </>
            )}
            <Button type="button"  onClick={() => onTrailer(baseDisplayMovie)}>
              <Film size={15} /> Trailer
            </Button>
            <MoviePlotDetailsButton movie={displayMovie} />
            {!owned && (
              <Button type="button"  onClick={() => onFollow(movie)}>
                <Bell size={15} /> {followed ? 'Following' : 'Follow'}
              </Button>
            )}
          </div>
          <MovieExpandedFacts movie={displayMovie} details={displayDetails} />
        </>
      )}
    </UnifiedMovieCard>
  );
}

export function MovieExpandedFacts({ movie, details }) {
  const releaseDate = movie?.release_date || details?.release_date || '';
  const releaseDateLabel = isUnreleasedMovie({ release_date: releaseDate }) ? formatReleaseDateLabel(releaseDate) : '';
  const writers = (details?.writers || movie?.writers || []).filter((writer) => writer?.name);
  const visibleWriters = writers.slice(0, 2);
  const remainingWriters = Math.max(0, writers.length - visibleWriters.length);

  if (!details?.tagline && !details?.runtime && !releaseDateLabel && !writers.length) return null;

  return (
    <div className="movie-expanded-facts">
      {releaseDateLabel || details?.tagline ? (
        <div className="movie-expanded-primary-facts">
          {releaseDateLabel && <div><span>Release date</span><strong>Releases {releaseDateLabel}</strong></div>}
          {details?.tagline && <div><span>Tagline</span><strong dir="auto">{details.tagline}</strong></div>}
        </div>
      ) : null}
      {writers.length ? (
        <div className="movie-expanded-writers">
          <span>Writer{writers.length === 1 ? '' : 's'}</span>
          <strong dir="auto">
            {visibleWriters.map((writer) => writer.name).join(', ')}
            {remainingWriters ? ` +${remainingWriters} more` : ''}
          </strong>
        </div>
      ) : null}
      {details?.runtime ? (
        <div className="movie-expanded-runtime">
          <span>Runtime</span>
          <strong>{details.runtime} min</strong>
        </div>
      ) : null}
    </div>
  );
}

export function MovieKeywordRow({ keywords = [] }) {
  const normalizedKeywords = keywords
    .map((keyword) => typeof keyword === 'string' ? keyword : keyword?.name)
    .filter(Boolean);
  if (!normalizedKeywords.length) return null;
  const visibleKeywords = normalizedKeywords.slice(0, 4);
  const remainingKeywords = normalizedKeywords.length - visibleKeywords.length;

  return (
    <div className="movie-keyword-row" aria-label="Movie keywords">
      <span className="movie-keyword-label">Keywords</span>
      {visibleKeywords.map((keyword) => (
        <Badge size="compact" muted className="movie-keyword-chip" dir="auto" key={keyword}>{keyword}</Badge>
      ))}
      {remainingKeywords > 0 ? <Badge size="compact" muted>+{remainingKeywords}</Badge> : null}
    </div>
  );
}

export function MovieImdbLink({ imdbId, title }) {
  const normalizedId = String(imdbId || '').trim();
  if (!/^tt\d+$/i.test(normalizedId)) return null;
  return (
    <a
      className="movie-imdb-link"
      href={`https://www.imdb.com/title/${encodeURIComponent(normalizedId)}/`}
      target="_blank"
      rel="noreferrer"
      aria-label={`Open ${title || 'movie'} on IMDb`}
      title="Open on IMDb"
    >
      IMDb <ExternalLink size={12} />
    </a>
  );
}

export function MovieExpandedCuration({
  movie,
  details,
  collection,
  collectionStatus = 'empty',
  collectionError = '',
  itemLists = [],
  onCollectionBrowse,
  onCollectionRetry,
  onListBrowse,
  onEditLists,
  onRemoveFromList,
  onEditCollection,
  onResetCollection,
  emptyListText = 'Not in any user list yet.'
}) {
  const activeCollection = collection?.id ? collection : details?.collection || {};
  const canBrowseCollection = Boolean(onCollectionBrowse);
  const canBrowseLists = Boolean(onListBrowse);
  const visibleItemLists = itemLists.slice(0, 5);
  const hiddenListCount = Math.max(0, itemLists.length - visibleItemLists.length);
  const collectionTotal = Array.isArray(activeCollection.parts) ? activeCollection.parts.length : null;
  const collectionOwned = Number.isFinite(activeCollection.owned_count) ? activeCollection.owned_count : null;
  const collectionDetail = ['idle', 'loading'].includes(collectionStatus)
    ? 'Loading collection...'
    : collectionStatus === 'error'
      ? 'Collection details unavailable'
      : collectionTotal !== null && collectionTotal > 0 && collectionOwned !== null
        ? `${formatCount(collectionTotal)} movies • ${formatCount(collectionOwned)} owned`
        : collectionTotal !== null && collectionTotal > 0
          ? `${formatCount(collectionTotal)} movies`
          : collectionOwned !== null
            ? `${formatCount(collectionOwned)} owned`
            : 'Collection members unavailable';

  return (
    <aside
      className={cx('movie-expanded-curation', activeCollection?.id && 'movie-expanded-curation-has-collection')}
      aria-label="Collection and lists"
    >
      {activeCollection?.id && (
        <div className="collection-panel">
          {canBrowseCollection ? (
            <button
              type="button"
              className="collection-main-action"
              onClick={() => onCollectionBrowse(activeCollection)}
              aria-busy={collectionStatus === 'loading'}
            >
              <Clapperboard size={17} />
              <span>
                <strong dir="auto">{activeCollection.name}</strong>
                <small>{collectionDetail}</small>
              </span>
            </button>
          ) : null}
          {(collectionStatus === 'error' && onCollectionRetry) || onEditCollection ? (
            <div className="collection-actions">
              {collectionStatus === 'error' && onCollectionRetry ? (
                <Button size="compact"
                  type="button"

                  onClick={onCollectionRetry}
                  title={collectionError || 'Retry loading collection details'}
                >
                  <RefreshCcw size={13} /> Retry
                </Button>
              ) : null}
              {onEditCollection ? (
                <Button size="compact" type="button"  onClick={() => onEditCollection(activeCollection)}>Edit</Button>
              ) : null}
              {activeCollection.is_edited && onResetCollection ? (
                <Button variant="danger" size="compact" type="button"  onClick={() => onResetCollection(activeCollection)}>
                  <RefreshCcw size={13} /> Reset
                </Button>
              ) : null}
            </div>
          ) : null}
        </div>
      )}
      <div className="lists-panel">
        <div className="lists-panel-header">
          <span className="mini-label">Lists</span>
          {onEditLists ? <Button size="compact" type="button"  onClick={onEditLists}>Add to list</Button> : null}
        </div>
        {itemLists.length ? (
          <div className="list-chip-row">
            {visibleItemLists.map((list) => (
              <Badge size="compact" muted className="list-chip" key={list.id}>
                <button type="button" onClick={canBrowseLists ? () => onListBrowse(list) : undefined}>{list.name}</button>
                {onRemoveFromList ? (
                  <button type="button" aria-label={`Remove ${movie.title} from ${list.name}`} onClick={() => onRemoveFromList(list.id)}>
                    <Trash2 size={13} />
                  </button>
                ) : null}
              </Badge>
            ))}
            {hiddenListCount ? <span className="list-chip-overflow">+{hiddenListCount} more</span> : null}
          </div>
        ) : (
          <small>{emptyListText}</small>
        )}
      </div>
    </aside>
  );
}

export function MovieExpandedDetails({
  movie,
  details,
  directors,
  cast,
  onPersonBrowse,
  onPersonDiscover,
  onPersonAwardDiscover
}) {
  const { personBio, openPersonBio, closePersonBio } = usePersonBiography();
  const loading = details?.loading;
  const allDirectors = details?.directors?.length ? details.directors : directors?.length ? directors : details?.director?.name ? [details.director] : [];
  const expandedDirectors = allDirectors;
  const expandedCast = details?.cast?.length ? details.cast : cast || [];
  const canBrowsePeople = Boolean(onPersonBrowse);
  const personFilmographyAction = onPersonDiscover || onPersonBrowse;

  return (
    <div className="movie-expanded-details">
      <div className="movie-expanded-credits-slot">
      {loading ? (
        <div className="people-loading"><Loader2 size={15} className="spin" /> Loading TMDB details...</div>
      ) : details?.error ? (
        <p className="discover-detail-error"><AlertTriangle size={15} /> {details.error}</p>
      ) : (
        <section className="movie-expanded-credits-panel" aria-label="Director and top cast">
          <HorizontalCardRail label="cast" className="credit-card-rail" trackClassName="movie-expanded-people-grid" arrowPlacement="edges" resetKey={movie?.tmdb_id}
            header={<span className="mini-label">Director &amp; top cast</span>}>
            {expandedDirectors.length ? (
              expandedDirectors.map((person) => (
                <AwardPersonCreditCard
                  key={`director-${person.id || person.name}`}
                  person={person}
                  role="director"
                  canBrowse={canBrowsePeople}
                  onBrowse={onPersonBrowse}
                  onDiscover={personFilmographyAction}
                  onAwardDiscover={onPersonAwardDiscover}
                  onBio={openPersonBio}
                />
              ))
            ) : (
              <small className="movie-expanded-credit-empty">No director data found.</small>
            )}
            {expandedCast.length ? (
              expandedCast.map((person) => (
                <AwardPersonCreditCard
                  key={`${person.id || person.name}-${person.character || ''}`}
                  person={person}
                  role="actor"
                  canBrowse={canBrowsePeople}
                  onBrowse={onPersonBrowse}
                  onDiscover={personFilmographyAction}
                  onAwardDiscover={onPersonAwardDiscover}
                  onBio={openPersonBio}
                />
              ))
            ) : (
              <small className="movie-expanded-credit-empty">No cast data found.</small>
            )}
          </HorizontalCardRail>
        </section>
      )}
      </div>
      <RelatedMovieRail
        key={movie?.tmdb_id || details?.tmdb_id || 'unmatched'}
        movie={{ ...(movie || {}), tmdb_id: movie?.tmdb_id || details?.tmdb_id || '' }}
      />
      {personBio && (
        <PersonBioModal
          state={personBio}
          onClose={closePersonBio}
        />
      )}
    </div>
  );
}

function AwardPersonCreditCard(props) {
  const counts = usePersonAwardCounts(props.person?.id, props.role, { enabled: true });
  return <PersonCreditCard {...props} awardCounts={counts} />;
}

export function LibraryMovieCard({
  item,
  followed = false,
  expanded,
  details,
  collection,
  collectionStatus,
  collectionError,
  itemLists,
  onToggle,
  onPlay,
  onFindTorrent,
  onTrailer,
  onPersonFilter,
  onPersonDiscover,
  onPersonAwardDiscover,
  onCollectionBrowse,
  onCollectionRetry,
  onEditCollection,
  onResetCollection,
  onListFilter,
  onEditLists,
  onRemoveFromList,
  onEditPoster,
  onCorrectMetadata,
  onOpenFileDetails,
  watched,
  watchlisted,
  onToggleWatched,
  onToggleWatchlist,
  showOwnedBadge = true,
  selected,
  onSelect
}) {
  const identity = getMovieIdentity(item);
  const canonical = item.canonical_metadata || {};
  const lowQuality = item.maintenance_upgrade_candidate === true;
  const genres = (canonical.genres?.length ? canonical.genres : item.plex_genres || []).slice(0, expanded ? 10 : 3);
  const directors = getRolePeople(item, details, 'director');
  const cast = getRolePeople(item, details, 'actor').slice(0, 9);
  const locale = getLocaleTag(item);
  const movieForSearch = {
    title: identity.title,
    year: identity.year,
    imdb_id: canonical.imdb_id || item.imdb_id || '',
    tmdb_id: canonical.tmdb_id || item.tmdb_id || ''
  };
  const awardCounts = useMovieAwardCounts(movieForSearch, { enabled: true });
  const posterUrl = canonical.poster_url || item.plex_poster || '';
  const canonicalDetails = details ? {
    ...mergeCanonicalMovieDetails(canonical, details),
    loading: details.loading,
    error: details.error,
    trailer_url: details.trailer_url || canonical.trailer_url || ''
  } : canonical;
  const baseDisplayMovie = {
    ...canonical,
    title: identity.title,
    year: identity.year,
    tmdb_id: canonical.tmdb_id || item.tmdb_id || '',
    poster_url: posterUrl,
    genres,
    summary: canonical.summary || canonical.plot || details?.summary || details?.plot || item.plex_summary || '',
    plot: canonical.plot || canonical.summary || details?.plot || details?.summary || item.plex_summary || ''
  };
  const languageView = useTransientMovieLanguage({
    movie: baseDisplayMovie,
    details: canonicalDetails,
    expanded
  });
  const displayMovie = languageView.displayMovie;
  const displayDetails = languageView.displayDetails;
  const displayCollection = languageView.isArabic && displayDetails?.collection?.id
    ? { ...(collection || {}), ...displayDetails.collection }
    : (collection?.id ? collection : canonical.collection || {});
  const playAction = usePendingPlay(onPlay, item.path);

  return (
    <UnifiedMovieCard ratingsIdentity={displayMovie}
      className={cx('library-movie-card', 'movie-awards-consumer', expanded && 'library-movie-card-expanded')}
      awardCounts={awardCounts}
      title={displayMovie.title}
      year={displayMovie.year}
      posterUrl={displayMovie.poster_url}
      backdropUrl={displayDetails?.backdrop_url || displayMovie.backdrop_url || displayMovie.poster_url}
      rating={displayMovie.rating || displayMovie.tmdb_rating || item.plex_rating}
      voteCount={formatVoteCount(displayMovie.tmdb_vote_count, { includeLabel: expanded })}
      chips={(displayMovie.genres || genres).slice(0, 2)}
      mutedChips={[
        locale,
        {
          label: expanded ? displayDetails?.certification || displayMovie.certification : '',
          tone: 'certification'
        },
        getCompactQualityLabel(item)
      ]}
      statusLabel={lowQuality ? 'Upgrade candidate' : ''}
      statusTone={lowQuality ? 'warning' : 'neutral'}
      following={followed}
      ownedBadge={showOwnedBadge}
      expanded={expanded}
      selected={selected}
      onToggle={onToggle}
      headerActions={expanded ? (
        <MovieImdbLink
          imdbId={displayDetails?.imdb_id || displayMovie.imdb_id}
          title={displayMovie.title}
        />
      ) : null}
      metadataActions={expanded ? (
        <MovieLanguageToggle {...languageView.toggleProps} />
      ) : null}
      showPlayOverlay={Boolean(item.path)}
      onPlay={playAction.play}
      playPending={playAction.pending}
      cornerControls={(
        <>
          <PosterStateControls
            title={identity.title}
            watched={watched}
            watchlisted={watchlisted}
            onToggleWatched={onToggleWatched}
            onToggleWatchlist={onToggleWatchlist}
          />
          <PosterEditButton title={identity.title} onEdit={onEditPoster} />
          <SelectionCheckbox
            className="library-selection-checkbox"
            checked={Boolean(selected)}
            onChange={onSelect}
            label={`Select ${identity.title}`}
          />
        </>
      )}
      expandedBody={expanded ? (
        <MovieExpandedCuration
          movie={displayMovie}
          details={displayDetails}
          collection={displayCollection}
          collectionStatus={collectionStatus}
          collectionError={collectionError}
          itemLists={itemLists}
          onCollectionBrowse={onCollectionBrowse}
          onCollectionRetry={onCollectionRetry}
          onListBrowse={onListFilter}
          onEditLists={onEditLists}
          onRemoveFromList={onRemoveFromList}
          onEditCollection={onEditCollection}
          onResetCollection={onResetCollection}
          emptyListText="No user lists yet."
        />
      ) : null}
      expandedFooter={expanded ? (
        <MovieExpandedDetails
          movie={baseDisplayMovie}
          details={displayDetails}
          directors={languageView.isArabic ? displayDetails?.directors : directors}
          cast={languageView.isArabic ? displayDetails?.cast : cast}
          onPersonBrowse={onPersonFilter}
          onPersonDiscover={onPersonDiscover ? (role, person) => onPersonDiscover({ title: identity.title, year: identity.year }, role, person) : undefined}
          onPersonAwardDiscover={onPersonAwardDiscover ? (role, person, award) => onPersonAwardDiscover(movieForSearch, role, person, award) : undefined}
        />
      ) : null}
    >
      {expanded && (
        <>
          <p className="library-summary movie-summary-expanded" dir={languageView.isArabic ? 'rtl' : undefined}>
            {displayMovie.summary || displayMovie.plot || 'No plot summary is available yet.'}
          </p>
          <MovieKeywordRow keywords={displayDetails?.keywords || displayMovie.keywords} />
          <div className="library-card-actions">
            <MoviePlayButton pending={playAction.pending} onPlay={playAction.play} />
            <Button type="button"  onClick={onTrailer}>
              <Film size={15} /> Trailer
            </Button>
            <MoviePlotDetailsButton movie={displayMovie} />
            <Button type="button"  onClick={onCorrectMetadata}>
              <Pencil size={15} /> Correct metadata
            </Button>
            <OwnedFileDetailsButton owned={item} onOpenFileDetails={onOpenFileDetails} />
            {lowQuality && (
              <Button variant="upgrade" type="button"  onClick={() => onFindTorrent(movieForSearch, true)}>
                <Wand2 size={15} /> Find upgrade
              </Button>
            )}
          </div>
          <MovieExpandedFacts movie={displayMovie} details={displayDetails} />
        </>
      )}
    </UnifiedMovieCard>
  );
}
