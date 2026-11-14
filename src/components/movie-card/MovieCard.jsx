import Badge from '../ui/Badge.jsx';
import { CalendarDays, ChevronDown, ChevronRight, Film, Loader2, MoreHorizontal, Play, RotateCcw, Star, X } from 'lucide-react';
import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { centeredWorkspaceScroll } from './expandedCardViewport.js';
import { useMediaCardArtwork, useMediaPosterSource, usePrioritizedCardPoster } from './cardArtwork.js';
import { MovieAwards } from '../MovieAwards.jsx';
import { MovieRatings } from './MovieRatings.jsx';
import { ratingsIdentity as normalizeRatingsIdentity } from '../../api/movieRatings.js';
import { positiveAwards } from '../../api/movieAwards.js';
import useMovieCardScrollReturn from '../../hooks/useMovieCardScrollReturn.js';

function cx(...classes) {
  return classes.filter(Boolean).join(' ');
}

function stopCardToggle(event) {
  event.stopPropagation();
}

export function ExpandedRating({ rating, voteCount }) {
  if (!rating) return null;
  return (
    <div className="unified-expanded-rating" aria-label={`Rating ${rating}${voteCount ? `, ${voteCount}` : ''}`}>
      <span><Star size={18} fill="currentColor" /><strong>{rating}</strong></span>
      {voteCount ? <small>{voteCount}</small> : null}
    </div>
  );
}

export function UnifiedMoviePoster({
  title,
  posterUrl,
  large,
  className = '',
  children,
  showPlayOverlay,
  onPlay,
  playLabel,
  playTitle,
  playPending = false
}) {
  const [imageFailed, setImageFailed] = useState(false);
  const posterRef = useRef(null);
  const imageRef = useRef(null);
  const posterSource = useMediaPosterSource(posterRef, posterUrl, large);
  usePrioritizedCardPoster(posterRef, imageRef, imageFailed ? '' : posterUrl);

  useEffect(() => setImageFailed(false), [posterUrl]);

  return (
    <div ref={posterRef} className={cx('unified-movie-poster', large && 'unified-movie-poster-large', className)}>
      {posterUrl && !imageFailed ? (
        <img ref={imageRef} src={posterSource} alt={`${title} poster`} loading="lazy" fetchPriority="high" onError={() => setImageFailed(true)} />
      ) : (
        <Film size={large ? 42 : 30} />
      )}
      {children}
      {showPlayOverlay && onPlay ? (
        <button
          type="button"
          className={cx('movie-card-play-overlay', playPending && 'movie-card-play-overlay-pending')}
          aria-label={playPending ? `Opening ${title} in Cinema Paradiso Player` : playLabel || `Play ${title}`}
          aria-busy={playPending || undefined}
          title={playPending ? 'Opening playerâ€¦' : playTitle || 'Play'}
          disabled={playPending}
          onClick={(event) => {
            event.stopPropagation();
            onPlay();
          }}
        >
          {playPending
            ? <Loader2 size={30} className="spin" />
            : <Play size={34} fill="currentColor" />}
        </button>
      ) : null}
    </div>
  );
}

export function UnifiedMovieCard({
  title,
  year,
  posterUrl,
  backdropUrl = '',
  rating,
  voteCount,
  awardCounts = null,
  ratingsIdentity = null,
  chips = [],
  mutedChips = [],
  statusLabel = '',
  statusTone = 'neutral',
  following = false,
  ownedBadge = false,
  expanded = false,
  selected = false,
  className = '',
  posterClassName = '',
  bodyClassName = '',
  cornerControls,
  headerActions,
  metadataActions,
  availability,
  showPlayOverlay = false,
  onPlay,
  playLabel,
  playTitle,
  playPending = false,
  onToggle,
  navigation = false,
  metadataLabel = 'Movie metadata',
  children,
  expandedBody,
  expandedFooter,
  aside
}) {
  const interactive = Boolean(onToggle);
  const rtIdentity = normalizeRatingsIdentity(ratingsIdentity);
  const cardRef = useRef(null);
  const artworkStyle = useMediaCardArtwork(cardRef, backdropUrl, posterUrl, expanded);
  const captureScrollOrigin = useMovieCardScrollReturn(cardRef, expanded);
  useLayoutEffect(() => {
    if (!expanded) return;
    if (cardRef.current?.closest('.workspace')?.dataset.restoringCard) return;
    let firstFrame;
    let secondFrame;
    let observedCuration;
    const syncPosterHeight = () => {
      const card = cardRef.current;
      const body = card?.querySelector('.unified-movie-body');
      const curation = body?.querySelector('.movie-expanded-curation');
      if (!card || !body) return;
      if (curation && curation !== observedCuration) {
        if (observedCuration) observer.unobserve(observedCuration);
        observer.observe(curation);
        observedCuration = curation;
      }
      if (!curation || window.innerWidth <= 720 || window.innerHeight <= 950) {
        card.style.removeProperty('--expanded-movie-card-content-height');
        return;
      }
      const height = Math.ceil(curation.getBoundingClientRect().bottom - body.getBoundingClientRect().top);
      const nextHeight = `${height}px`;
      if (card.style.getPropertyValue('--expanded-movie-card-content-height') !== nextHeight) {
        card.style.setProperty('--expanded-movie-card-content-height', nextHeight);
      }
    };
    const centerCard = () => {
      const card = cardRef.current;
      const workspace = card?.closest('.workspace');
      if (!workspace || workspace.dataset.restoringCard || !card.getClientRects().length || window.innerWidth <= 720) return;
      const bounds = workspace.getBoundingClientRect();
      const chrome = [...workspace.querySelectorAll('.workspace-chrome')].find(element => element.getClientRects().length);
      workspace.scrollTo({
        top: centeredWorkspaceScroll(card.getBoundingClientRect(), { ...bounds.toJSON(), scrollTop: workspace.scrollTop }, chrome?.getBoundingClientRect().height || 0),
        behavior: 'instant'
      });
    };
    const scheduleCenter = () => {
      cancelAnimationFrame(firstFrame);
      cancelAnimationFrame(secondFrame);
      firstFrame = requestAnimationFrame(() => {
        syncPosterHeight();
        secondFrame = requestAnimationFrame(() => {
          syncPosterHeight();
          centerCard();
        });
      });
    };
    const observer = new ResizeObserver(scheduleCenter);
    observer.observe(cardRef.current);
    const body = cardRef.current.querySelector('.unified-movie-body');
    if (body) observer.observe(body);
    const chrome = [...cardRef.current.closest('.workspace')?.querySelectorAll('.workspace-chrome') || []].find(element => element.getClientRects().length);
    if (chrome) observer.observe(chrome);
    scheduleCenter();
    return () => {
      observer.disconnect();
      cancelAnimationFrame(firstFrame);
      cancelAnimationFrame(secondFrame);
      cardRef.current?.style.removeProperty('--expanded-movie-card-content-height');
    };
  }, [expanded]);
  const displayTitle = title || 'Untitled';
  const titleLength = displayTitle.length;
  const longTitle = titleLength > 28;
  const veryLongTitle = titleLength > 46;

  function handleKeyDown(event) {
    if (event.target !== event.currentTarget) return;
    if (!interactive) return;
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      onToggle();
    }
  }

  function collapseFromMain(event) {
    // Capture plain content clicks before body sections stop propagation. Leave
    // nested actions and portaled dialogs to their own handlers.
    if (!expanded || !interactive || !event.currentTarget.contains(event.target)) return;
    if (event.target.closest('button, a, input, select, textarea, label, summary, [role="button"], [role="checkbox"], [contenteditable="true"], [data-movie-rating]')) return;
    event.stopPropagation();
    onToggle();
  }

  return (
    <article
      ref={cardRef}
      className={cx(
        'unified-movie-card',
        expanded && 'unified-movie-card-expanded',
        rtIdentity && 'unified-movie-card-ratings',
        selected && 'unified-movie-card-selected',
        interactive && 'unified-movie-card-interactive',
        className
      )}
      style={expanded ? undefined : artworkStyle}
      onClickCapture={captureScrollOrigin}
      onKeyDownCapture={captureScrollOrigin}
      onClick={expanded ? undefined : navigation ? (event) => { if (!event.target.closest('button, a, input, select, summary')) onToggle(); } : onToggle}
      onKeyDown={handleKeyDown}
      tabIndex={interactive ? 0 : undefined}
      aria-expanded={interactive && !navigation ? Boolean(expanded || selected) : undefined}
      role={navigation ? 'link' : undefined}
      aria-label={navigation ? `Open ${displayTitle}` : undefined}
    >
      <div className="unified-movie-main" onClickCapture={collapseFromMain} style={expanded ? artworkStyle : undefined}>
        <UnifiedMoviePoster
          title={displayTitle}
          posterUrl={posterUrl}
          className={posterClassName}
          showPlayOverlay={showPlayOverlay}
          onPlay={onPlay}
          playLabel={playLabel}
          playTitle={playTitle}
          playPending={playPending}
          large={expanded}
        >
          {cornerControls}
        </UnifiedMoviePoster>

        <div className={cx('unified-movie-body', bodyClassName)}>
          <header className="unified-movie-header">
            <div className="unified-movie-title-block">
              <h3 dir="auto" className={cx(longTitle && 'unified-title-long', veryLongTitle && 'unified-title-very-long')}>
                {displayTitle}
              </h3>
              <span>{year || 'Unknown year'}</span>
            </div>
            <div className="unified-movie-header-meta">
              {expanded ? <MovieAwards counts={awardCounts} /> : null}
              {expanded && rtIdentity ? <MovieRatings identity={rtIdentity} cardRef={cardRef} expanded /> : null}
              {rating && expanded ? <ExpandedRating rating={rating} voteCount={voteCount} /> : null}
              {headerActions ? (
                <span className="unified-header-actions" onClick={stopCardToggle}>
                  {headerActions}
                </span>
              ) : null}
              {interactive ? (
                <span className="unified-expand-affordance" aria-hidden="true">
                  {navigation ? <ChevronRight size={18} /> : <ChevronDown size={18} />}
                </span>
              ) : null}
            </div>
          </header>

          <div className="unified-chip-row" aria-label={metadataLabel}>
            {chips.filter(Boolean).map((chip) => (
              <Badge  dir="auto" key={chip}>{chip}</Badge>
            ))}
            {following ? <Badge kind="status" tone="following" >Following</Badge> : null}
            {ownedBadge ? <Badge kind="owned" >Owned</Badge> : null}
            {mutedChips.map((chip, index) => {
              const label = typeof chip === 'object' ? chip?.label : chip;
              if (!label) return null;
              const tone = typeof chip === 'object' ? chip?.tone : '';
              return (
                <Badge muted tone={tone || 'neutral'}

                  dir="auto"
                  key={`${label}-${index}`}
                >
                  {label}
                </Badge>
              );
            })}
            {statusLabel ? (
              <Badge kind="status" tone={statusTone} >{statusLabel}</Badge>
            ) : null}
            {metadataActions ? (
              <div className="unified-chip-row-actions" onClick={stopCardToggle}>
                {metadataActions}
              </div>
            ) : null}
          </div>

          {availability}
          <div className="unified-movie-extra" onClick={navigation ? undefined : stopCardToggle}>
            {children}
          </div>

          {expandedBody ? (
            <div className="unified-movie-expanded-body" onClick={stopCardToggle}>
              {expandedBody}
            </div>
          ) : null}

          {!expanded && (rating || rtIdentity || positiveAwards(awardCounts).length) ? (
            <div className="unified-rating-row">
              {rating ? <span className="unified-rating">
                <Star size={16} fill="currentColor" />
                {rating}{voteCount ? ` - ${voteCount}` : ''}
              </span> : null}
              {rtIdentity ? <MovieRatings identity={rtIdentity} cardRef={cardRef} /> : null}
              <MovieAwards counts={awardCounts} />
            </div>
          ) : null}
        </div>
      </div>
      {aside ? (
        <div className="unified-movie-aside" onClick={stopCardToggle}>
          {aside}
        </div>
      ) : null}
      {expandedFooter ? (
        <div className="unified-movie-expanded-row" onClick={stopCardToggle}>
          {expandedFooter}
        </div>
      ) : null}
    </article>
  );
}

export function ContinueMovieCard({
  title,
  posterUrl,
  backdropUrl,
  progress = 0,
  remainingLabel,
  menuGroup,
  onResume,
  onRestart,
  onRemove,
  onViewCard
}) {
  const displayTitle = title || 'Untitled';
  const boundedProgress = Math.max(0, Math.min(1, Number(progress) || 0));
  const cardRef = useRef(null);
  const artworkStyle = useMediaCardArtwork(cardRef, backdropUrl, posterUrl);

  return (
    <article ref={cardRef} className="continue-movie-card" style={artworkStyle}>
      <UnifiedMoviePoster
        title={displayTitle}
        posterUrl={posterUrl}
        className="continue-movie-poster"
        showPlayOverlay
        onPlay={onResume}
      >
        <details className="continue-movie-menu" name={menuGroup} onClick={stopCardToggle}>
          <summary role="button" aria-label={`More options for ${displayTitle}`} title="More options">
            <MoreHorizontal size={17} />
          </summary>
          <div>
            <button
              type="button"
              onClick={(event) => {
                event.currentTarget.closest('details')?.removeAttribute('open');
                onRestart();
              }}
            >
              <RotateCcw size={14} /> Restart
            </button>
            <button
              type="button"
              onClick={(event) => {
                event.currentTarget.closest('details')?.removeAttribute('open');
                onRemove();
              }}
            >
              <X size={14} /> Remove
            </button>
            {onViewCard && (
              <button
                type="button"
                onClick={(event) => {
                  event.currentTarget.closest('details')?.removeAttribute('open');
                  onViewCard();
                }}
              >
                <Film size={14} /> View card
              </button>
            )}
          </div>
        </details>
      </UnifiedMoviePoster>
      <div
        className="continue-movie-progress"
        role="progressbar"
        aria-label={`${displayTitle} playback progress`}
        aria-valuemin="0"
        aria-valuemax="100"
        aria-valuenow={Math.round(boundedProgress * 100)}
      >
        <span style={{ width: `${boundedProgress * 100}%` }} />
      </div>
      <h3 dir="auto" title={displayTitle}>{displayTitle}</h3>
      <p>{remainingLabel}</p>
    </article>
  );
}

export function UpcomingMovieCard({
  title,
  posterUrl,
  backdropUrl,
  releaseLabel,
  selected = false,
  onSelect
}) {
  const displayTitle = title || 'Untitled';
  const cardRef = useRef(null);
  const artworkStyle = useMediaCardArtwork(cardRef, backdropUrl, posterUrl);

  return (
    <button
      type="button"
      ref={cardRef}
      className={cx('upcoming-movie-card', selected && 'upcoming-movie-card-selected')}
      style={artworkStyle}
      onClick={onSelect}
      aria-pressed={selected}
      aria-label={`Inspect ${displayTitle}${releaseLabel ? `, ${releaseLabel}` : ''}`}
    >
      <UnifiedMoviePoster
        title={displayTitle}
        posterUrl={posterUrl}
        className="upcoming-movie-poster"
      />
      <span className="upcoming-movie-copy">
        <strong dir="auto" title={displayTitle}>{displayTitle}</strong>
        <small><CalendarDays size={13} /> {releaseLabel || 'Release date pending'}</small>
      </span>
    </button>
  );
}
