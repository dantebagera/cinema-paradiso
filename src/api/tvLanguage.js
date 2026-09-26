import { fetchJson } from './client.js';

export function fetchTransientTVLanguage(tmdbId) {
  const id = String(tmdbId || '').trim();
  if (!/^\d+$/.test(id)) throw new Error('A TMDB TV ID is required for language display.');
  return fetchJson(`/api/tv/translation/${encodeURIComponent(id)}?language=ar-SA`);
}

export function mergeTransientTVLanguage(series, localized) {
  if (!series || !localized) return series;
  return {
    ...series,
    title: localized.title || series.title,
    overview: localized.overview || series.overview,
    genres: localized.genres?.length ? localized.genres : series.genres,
    poster_url: localized.poster_url || series.poster_url,
    backdrop_url: localized.backdrop_url || series.backdrop_url,
  };
}
