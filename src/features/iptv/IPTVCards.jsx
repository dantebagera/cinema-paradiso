import Button from '../../components/ui/Button.jsx';
import { createContext, useContext, useEffect, useRef, useState } from 'react';
import { CheckSquare, Clapperboard, ExternalLink, Heart, Languages, ListPlus, Loader2, Play, WandSparkles, X } from 'lucide-react';
import { iptvApi, iptvImage } from '../../api/iptv.js';
import { PersonCreditCard, PersonBioModal, usePersonBiography } from '../../components/PersonCreditCard.jsx';
import HorizontalCardRail from '../../components/HorizontalCardRail.jsx';
import { MovieExpandedFacts, MovieKeywordRow } from '../../components/SharedMovieCards.jsx';
import { UnifiedMovieCard } from '../../components/movie-card/MovieCard.jsx';
import { useMediaCardArtwork } from '../../components/movie-card/cardArtwork.js';
import { formatCount, movieKey } from '../../utils/appUtils.js';
import { formatVoteCount } from '../../utils/moviePresentation.js';
import './iptv.css';

export const IPTVPeopleNavigationContext = createContext(null);

export function mediaTitle(item) {
  const name = String(item?.name || item?.title || 'Untitled');
  const year = String(item?.year || '').slice(0, 4);
  return year ? name.replace(new RegExp(`\\s*\\(\\s*${year}\\s*\\)\\s*$`), '').trim() || name : name;
}

function movieChipLabel(value) {
  if (typeof value === 'string' || typeof value === 'number') return String(value).trim();
  if (!value || typeof value !== 'object') return '';
  return movieChipLabel(value.name ?? value.label ?? '');
}

export function movieGenreLabels(movie) {
  const values = Array.isArray(movie?.genres)
    ? movie.genres
    : String(movie?.genre || '').split(',');
  return values.map(movieChipLabel).filter(Boolean).slice(0, 3);
}

export function IPTVMovieCard({ providerId, movie, followed = [], selectedId, detail, detailLoading, onToggle, onPlay, onFavorite, onAddToList, onMatch, onRemoveMatch, locale = 'default', onLocale, selectable = false, checked = false, onSelect, reviewOnly = false }) {
  const expanded = selectedId === movie.movie_key;
  const current = expanded && detail ? { ...movie, ...detail } : movie;
  const genres = movieGenreLabels(current);
  const languageLabel = current.languages?.map((row) => row.name || row.code).filter(Boolean).join(', ') || '';
  const countryLabel = current.countries?.map((row) => row.name || row.code).filter(Boolean).join(', ') || '';
  const sourceLabels = [
    current.category && current.category !== 'unclassified' ? current.category.replace(/^./, (value) => value.toUpperCase()) : '',
    expanded ? languageLabel : '',
    expanded ? countryLabel : '',
    expanded ? current.certification : '',
    Number(movie.source_count || 1) > 1 ? `${movie.source_count} sources` : '',
    movie.quality_claim ? `${movie.quality_claim} claimed` : ''
  ].filter(Boolean);
  const statusLabel = movie.unmatched_reason || (movie.metadata_status === 'matched-manual' ? 'Manual match' : movie.metadata_status === 'matched-auto' ? 'Matched' : movie.metadata_status === 'error-retryable' || movie.metadata_status === 'error-terminal' ? 'Metadata failed' : movie.metadata_status === 'ambiguous' ? 'Ambiguous' : movie.metadata_status === 'unprocessed' ? 'Not processed' : movie.metadata_status === 'classified-non-film' ? 'Classified' : 'Unmatched');
  const isArabic = locale === 'ar-SA' || (locale === 'default' && current.display_locale === 'ar-SA');
  const selectionControl = selectable ? <label className="iptv-card-selection" onClick={(event) => event.stopPropagation()}><input type="checkbox" checked={checked} onChange={onSelect} aria-label={`Select ${movie.provider_title || movie.name}`} /><CheckSquare size={15} /></label> : null;
  return (
    <UnifiedMovieCard ratingsIdentity={movie.matched ? {tmdb_id: movie.tmdb_id} : null}
      title={mediaTitle(current)}
      year={current.year || movie.year}
      posterUrl={movie.matched ? (current.image_url || movie.image_url) : (movie.image_url ? iptvImage(providerId, 'movie', movie.item_id) : '')}
      backdropUrl={movie.matched ? current.backdrop_url : undefined}
      rating={current.rating ? Number(current.rating).toFixed(1) : ''}
      voteCount={formatVoteCount(current.vote_count, { includeLabel: expanded })}
      chips={genres}
      mutedChips={sourceLabels}
      following={followed.some((item) => movieKey(item) === movieKey({ title: mediaTitle(movie), year: movie.year }))}
      expanded={expanded}
      selected={expanded}
      showPlayOverlay={!reviewOnly}
      onPlay={() => onPlay(current)}
      onToggle={() => onToggle(movie)}
      className={`iptv-movie-card${selectable ? ' is-review-card' : ''}`}
      cornerControls={<div className="iptv-movie-corner-actions">{selectionControl}<span className={`iptv-metadata-badge is-${String(movie.metadata_status || 'unmatched').replace(/[^a-z-]/g, '')}`}>{statusLabel}</span>{!reviewOnly && <><FavoriteButton item={movie} onFavorite={onFavorite} /><ListActionButton item={movie} onAddToList={onAddToList} /></>}</div>}
      headerActions={expanded && current.external_url ? <IPTVMovieExternalLink movie={current} /> : null}
      metadataActions={expanded && current.matched && onLocale ? <IPTVMovieLanguageToggle isArabic={isArabic} onLocale={onLocale} /> : null}
      expandedFooter={expanded && !detailLoading && current.matched ? <IPTVPeopleCredits key={providerId} providerId={providerId} movie={current} directors={current.directors} cast={current.cast} /> : null}
    >
      {expanded ? detailLoading ? <div className="iptv-detail-loading"><Loader2 className="spin" size={17} /> Loading provider metadata...</div> : (
        <>
          <p className="movie-card-plot discover-plot-visible" dir={isArabic ? 'rtl' : 'auto'}>{current.plot || current.classification_review_reason || 'No plot supplied by the provider.'}</p>
          <MovieKeywordRow keywords={current.keywords} />
          {!reviewOnly && <div className="card-actions">
            <Button variant="primary" type="button"  onClick={() => onPlay(current)}><Play size={15} /> {Number(current.source_count || 1) > 1 ? 'Choose source' : 'Play'}</Button>
            <Button type="button"  onClick={() => onFavorite(current)}><Heart size={15} fill={current.favorite ? 'currentColor' : 'none'} /> {current.favorite ? 'Favorited' : 'Favorite'}</Button>
            <Button type="button"  onClick={() => onAddToList(current)}><ListPlus size={15} /> Add to list</Button>
            {onMatch && !['sports', 'music'].includes(current.category) ? <Button type="button"  onClick={() => onMatch(current)}><WandSparkles size={15} /> {current.matched ? 'Correct match' : 'Match metadata'}</Button> : null}
            {current.matched && onRemoveMatch ? <Button type="button"  onClick={() => window.confirm('Remove this provider-local metadata match? Raw provider playback will remain available.') && onRemoveMatch(current)}><X size={15} /> Remove match</Button> : null}
          </div>}
          <MovieExpandedFacts movie={current} details={current} />
          <div className="iptv-expanded-provider-facts">
            <span>Provider playlist <strong dir="auto">{current.playlist_name || 'Unknown'}</strong></span>
            <span>Classification <strong>{current.category || 'unclassified'}</strong></span>
            <span>Sources <strong>{formatCount(current.source_count || current.sources?.length || 1)}</strong></span>
            {current.provider_title ? <span>Raw provider title <strong dir="auto">{current.provider_title}{current.provider_year ? ` (${current.provider_year})` : ''}</strong></span> : null}
            {current.detail_title ? <span>Provider detail title <strong dir="auto">{current.detail_title}{current.detail_year ? ` (${current.detail_year})` : ''}</strong></span> : null}
            {current.provider_tmdb_id ? <span>Provider TMDB evidence <strong>{current.provider_tmdb_id}</strong></span> : null}
            {current.tmdb_id ? <span>Accepted TMDB identity <strong>{current.tmdb_id}</strong></span> : null}
            {current.classification_method ? <span>Classification method <strong>{current.classification_method}</strong></span> : null}
            {movie.unmatched_reason ? <span>Why it is unmatched <strong>{movie.unmatched_reason}</strong></span> :
              current.classification_review_reason && <span>Classification review <strong>{current.classification_review_reason}</strong></span>}
            {current.method ? <span>Match evidence <strong>{current.method} · {Number(current.confidence || 0).toFixed(1)}</strong></span> : null}
            {current.collection?.name ? <span>Collection <strong dir="auto">{current.collection.name}</strong></span> : null}
          </div>
        </>
      ) : null}
    </UnifiedMovieCard>
  );
}

function IPTVMovieExternalLink({ movie }) {
  const isIMDb = movie.original_language !== 'ar' && Boolean(movie.imdb_id);
  return <a className={isIMDb ? 'movie-imdb-link' : 'iptv-tmdb-link'} href={movie.external_url} target="_blank" rel="noreferrer" aria-label={`Open ${movie.title || movie.name || 'movie'} on ${isIMDb ? 'IMDb' : 'TMDB'}`}>{isIMDb ? 'IMDb' : 'TMDB'} <ExternalLink size={12} /></a>;
}

function IPTVMovieLanguageToggle({ isArabic, onLocale }) {
  return <div className="movie-language-toolbar"><Button size="compact" type="button" className="movie-language-toggle" onClick={() => onLocale(isArabic ? 'en-US' : 'ar-SA')} aria-pressed={isArabic}><Languages size={14} />{isArabic ? 'English' : 'العربية'}</Button></div>;
}

function IPTVPeopleCredits({ providerId, movie, directors = [], cast = [] }) {
  const { onBrowse, onDiscover } = useContext(IPTVPeopleNavigationContext) || {};
  const { personBio, openPersonBio, closePersonBio } = usePersonBiography(
    (personId, options) => iptvApi.person(providerId, personId, options)
  );
  const credits = [
    ...directors.slice(0, 2).map((person) => ({ ...person, role: 'Director', director: true })),
    ...cast.slice(0, 8).map((person) => ({ ...person, role: person.character || 'Cast', director: false }))
  ];
  if (!credits.length) return null;
  return (
    <div className="movie-expanded-details iptv-movie-expanded-details">
      <section className="movie-expanded-credits-panel" aria-label="Director and top cast">
        <HorizontalCardRail label="cast" className="credit-card-rail" trackClassName="movie-expanded-people-grid"
          arrowPlacement="edges" header={<span className="mini-label">Director &amp; top cast</span>}>
          {credits.map((person, index) => (
            <PersonCreditCard key={`${person.id || person.name}-${index}`} person={person}
              role={person.director ? 'director' : 'actor'} canBrowse={Boolean(onBrowse && person.id)}
              unavailableReason={!person.id ? 'Filmography unavailable: no TMDB person ID for this credit.' : undefined}
              onBrowse={onBrowse} onDiscover={onDiscover ? (role, credit) => onDiscover(
                { title: mediaTitle(movie), year: movie.year }, role, credit, { fullFilmography: true }
              ) : undefined}
              onBio={openPersonBio} />
          ))}
        </HorizontalCardRail>
      </section>
      {personBio && <PersonBioModal state={personBio} onClose={closePersonBio} />}
    </div>
  );
}

export function PosterTile({ providerId, item, active, onClick, onFavorite, onAddToList, reviewOnly = false, selectable = false, checked = false, onSelect }) {
  const posterUrl = item.image_url ? iptvImage(providerId, item.kind, item.item_id) : '';
  const cardRef = useRef(null);
  const artworkStyle = useMediaCardArtwork(cardRef, '', item.kind === 'series' ? posterUrl : '');
  return (
    <article ref={cardRef} className={`iptv-poster-tile ${active ? 'is-active' : ''}`} style={artworkStyle} onClick={onClick} tabIndex="0" onKeyDown={(event) => { if (event.key === 'Enter') onClick(); }}>
      <div><ProviderImage src={posterUrl} alt={`${item.name} poster`} fallback={Clapperboard} />{selectable && <label className="iptv-card-selection" onClick={event => event.stopPropagation()}><input type="checkbox" checked={checked} onChange={onSelect} aria-label={`Select ${item.name}`} /><CheckSquare size={15} /></label>}{!reviewOnly && <div className="iptv-poster-actions"><FavoriteButton item={item} onFavorite={onFavorite} /><ListActionButton item={item} onAddToList={onAddToList} /></div>}</div>
      <strong dir="auto">{mediaTitle(item)}</strong>
      <span>{item.year || (item.kind === 'live' ? 'Live channel' : 'Provider title')}</span>
    </article>
  );
}

export function FavoriteButton({ item, onFavorite, className = '' }) {
  const action = item.favorite ? 'Remove from favorites' : 'Add to favorites';
  return (
    <button
      type="button"
      className={className}
      aria-label={`${action}: ${item.name}`}
      title={action}
      onClick={(event) => { event.stopPropagation(); onFavorite(item); }}
    >
      <Heart size={16} fill={item.favorite ? 'currentColor' : 'none'} />
    </button>
  );
}

export function ListActionButton({ item, onAddToList, className = '' }) {
  return (
    <button
      type="button"
      className={className}
      aria-label={`Add ${item.name} to list`}
      title="Add to list"
      onClick={(event) => { event.stopPropagation(); onAddToList(item); }}
    >
      <ListPlus size={16} />
    </button>
  );
}

export function ProviderImage({ src, fallbackSrc = '', alt, fallback: Fallback }) {
  const [failedSources, setFailedSources] = useState(0);
  useEffect(() => setFailedSources(0), [src, fallbackSrc]);
  const secondarySource = fallbackSrc && fallbackSrc !== src ? fallbackSrc : '';
  const activeSource = failedSources === 0 ? src : failedSources === 1 ? secondarySource : '';
  if (!activeSource) return <Fallback size={24} />;
  return <img src={activeSource} alt={alt} loading="lazy" onError={() => setFailedSources((value) => value + 1)} />;
}
