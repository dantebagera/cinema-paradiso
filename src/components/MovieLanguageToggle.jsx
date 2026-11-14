import Button from './ui/Button.jsx';
import { Languages, Loader2 } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { cachedMovieLanguage, fetchTransientMovieLanguage, mergeTransientMovieLanguage } from '../api/movieDetails.js';
import { isArabicMovie } from '../utils/movieLanguage.js';
import { fetchTransientTVLanguage, mergeTransientTVLanguage } from '../api/tvLanguage.js';

function useTransientLanguage(tmdbId, expanded, fetchLanguage) {
  const [localized, setLocalized] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const requestId = useRef(0);

  useEffect(() => {
    requestId.current += 1;
    setLocalized(null);
    setLoading(false);
    setError('');
  }, [expanded, tmdbId]);

  async function toggleLanguage() {
    if (localized) {
      requestId.current += 1;
      setLocalized(null);
      setLoading(false);
      setError('');
      return;
    }
    if (!tmdbId || loading) return;

    const activeRequest = requestId.current + 1;
    requestId.current = activeRequest;
    setLoading(true);
    setError('');
    try {
      const data = await fetchLanguage(tmdbId);
      if (requestId.current === activeRequest) setLocalized(data);
    } catch (caught) {
      if (requestId.current === activeRequest) setError(caught.message);
    } finally {
      if (requestId.current === activeRequest) setLoading(false);
    }
  }

  const activeLocalized = expanded ? localized : null;
  return {
    localized: activeLocalized,
    isArabic: Boolean(activeLocalized),
    toggleProps: {
      available: Boolean(tmdbId),
      isArabic: Boolean(activeLocalized),
      loading,
      error,
      onToggle: toggleLanguage
    }
  };
}

export function useTransientMovieLanguage({ movie, details, expanded }) {
  const tmdbId = String(movie?.tmdb_id || details?.tmdb_id || '').trim();
  const key = tmdbId || movie?.path || movie?.title || '';
  const [selection, setSelection] = useState({});
  const current = selection.key === key ? selection : {};
  const isArabic = current.choice ?? isArabicMovie(movie, details);
  const localized = isArabic ? current.localized || movie?.arabic_display || details?.arabic_display || cachedMovieLanguage(tmdbId) : null;
  const retry = current.retry || 0;
  useEffect(() => {
    let cancelled = false;
    if (!isArabic || !expanded || !tmdbId) return;
    setSelection(previous => ({ ...(previous.key === key ? previous : {}), key, loading: true, error: '' }));
    fetchTransientMovieLanguage(tmdbId).then(data => {
      if (!cancelled) setSelection(previous => ({ ...previous, key, localized: data, loading: false, error: '' }));
    }).catch(error => {
      if (!cancelled) setSelection(previous => ({ ...previous, key, loading: false, error: error.message }));
    });
    return () => { cancelled = true; };
  }, [key, tmdbId, expanded, isArabic, retry]);
  return {
    localized, isArabic,
    ...mergeTransientMovieLanguage(movie, details, isArabic ? localized || {} : null),
    toggleProps: {
      available: Boolean(tmdbId), isArabic,
      loading: Boolean(expanded && isArabic && current.loading), error: isArabic ? current.error : '',
      onToggle: () => setSelection(previous => ({ ...(previous.key === key ? previous : {}), key, choice: !isArabic, loading: false, error: '' })),
      onRetry: () => setSelection(previous => ({ ...previous, key, retry: retry + 1 }))
    }
  };
}

export function useTransientTVLanguage(series) {
  const tmdbId = String(series?.tmdb_id || '').trim();
  const state = useTransientLanguage(tmdbId, true, fetchTransientTVLanguage);
  return { ...state, displaySeries: mergeTransientTVLanguage(series, state.localized) };
}

export function MovieLanguageToggle({ available, isArabic, loading, error, onToggle, onRetry }) {
  if (!available) return null;
  return (
    <div className="movie-language-toolbar">
      {error ? <small className="movie-language-error">{error}</small> : null}
      {error && onRetry ? <Button size="compact" type="button"  onClick={onRetry}>Retry Arabic</Button> : null}
      <Button size="compact"
        type="button"
        className="movie-language-toggle"
        onClick={onToggle}
        disabled={loading && !isArabic}
        aria-pressed={isArabic}
      >
        {loading ? <Loader2 size={14} className="spin" /> : <Languages size={14} />}
        {loading && !isArabic ? 'Loading Arabic...' : (isArabic ? 'English' : 'العربية')}
      </Button>
    </div>
  );
}
