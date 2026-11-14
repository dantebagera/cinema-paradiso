import { yearRangeDraft } from '../features/search/advancedSearchModel.js';
import { catalogCountries } from './catalogFilterOptions.js';

export const emptyListFilters = () => ({ genre: '', country: '', minVotes: '0', minRating: '0', yearFrom: '', yearTo: '', sort: 'auto' });
export const hasListFilters = filters => Object.entries(filters).some(([key, value]) => value !== emptyListFilters()[key]);
export const needsListMetadata = filters => Boolean(filters.genre || filters.country || filters.yearFrom || filters.yearTo || Number(filters.minVotes) || Number(filters.minRating) || ['popularity.desc', 'vote_average.desc', 'vote_count.desc', 'primary_release_date.desc'].includes(filters.sort));
// Card summaries may omit required filter fields. Explicit empty values are
// known metadata; absent fields still require enrichment.
export function hasListFilterMetadata(movie, filters) {
  if (!movie) return false;
  const has = (...keys) => keys.some(key => Object.hasOwn(movie, key) && movie[key] != null);
  if (filters.genre && !has('genres', 'genre_ids')) return false;
  if (filters.country && !has('country_flag', 'country', 'countries', 'origin_country', 'production_countries')) return false;
  if ((Number(filters.minRating) || filters.sort === 'vote_average.desc') && !has('tmdb_rating', 'vote_average', 'rating')) return false;
  if ((Number(filters.minVotes) || filters.sort === 'vote_count.desc') && !has('tmdb_vote_count', 'vote_count', 'votes')) return false;
  if ((filters.yearFrom || filters.yearTo || filters.sort === 'primary_release_date.desc') && !has('year', 'release_date', 'first_air_date')) return false;
  if (filters.sort === 'popularity.desc' && !has('popularity')) return false;
  return true;
}
const text = value => String(value ?? '').trim().toLocaleLowerCase();
const number = value => Number(String(value ?? '').replace(/,/g, '')) || 0;
const rating = movie => number(movie.tmdb_rating || movie.vote_average || movie.rating);
const votes = movie => number(movie.tmdb_vote_count || movie.vote_count || movie.votes);
const year = movie => {
  const value = String(movie.release_date || movie.first_air_date || movie.year || '').slice(0, 4);
  return /^\d{4}$/.test(value) ? Number(value) : null;
};

function countryValues(movie) {
  const values = [movie.country_flag, movie.country, ...(movie.origin_country || []), ...(movie.countries || []), ...(movie.production_countries || [])];
  return values.flatMap(value => {
    if (value && typeof value === 'object') return [text(value.iso_3166_1), text(value.name)];
    const chars = [...String(value || '')];
    const flag = chars.length === 2 && chars.every(char => char.codePointAt(0) >= 0x1f1e6 && char.codePointAt(0) <= 0x1f1ff);
    return [text(value), ...(flag ? [text(chars.map(char => String.fromCharCode(char.codePointAt(0) - 0x1f1e6 + 65)).join(''))] : [])];
  });
}

export function filterListRows(rows, filters, genres, metadata) {
  const range = yearRangeDraft(filters.yearFrom, filters.yearTo);
  const genre = genres.find(option => option.value === filters.genre);
  const country = filters.country ? catalogCountries.find(option => option.value === filters.country) || { value: filters.country, label: filters.country } : null;
  const genreTokens = genre?.value ? [text(genre.value), text(genre.label)] : null;
  const countryTokens = country ? [text(country.value), text(country.label)] : null;
  const minRating = Number(filters.minRating), minVotes = Number(filters.minVotes);
  const filterYears = range.ready && (range.from || range.to);
  const fromYear = Number(range.from), toYear = Number(range.to);
  const getters = { 'title.asc': movie => text(movie.title), 'popularity.desc': movie => number(movie.popularity), 'vote_average.desc': rating, 'vote_count.desc': votes, 'primary_release_date.desc': movie => String(movie.release_date || movie.first_air_date || movie.year || '') };
  const sortKey = getters[filters.sort];
  // Default list browsing needs only membership, not merged filter metadata.
  if (!genreTokens && !countryTokens && !minRating && !minVotes && !filterYears && !sortKey) return rows.slice();
  const result = [];
  rows.forEach(row => {
    const movie = metadata(row);
    if (genreTokens) {
      const tokens = [...(movie.genres || []), ...(movie.genre_ids || [])].flatMap(value => typeof value === 'object' ? [text(value.id), text(value.name)] : [text(value)]);
      if (!tokens.includes(genreTokens[0]) && !tokens.includes(genreTokens[1]) && !(genre.value === '878' && tokens.includes('science fiction'))) return;
    }
    if (countryTokens && !countryValues(movie).some(value => countryTokens.includes(value))) return;
    if ((minRating && rating(movie) < minRating) || (minVotes && votes(movie) < minVotes)) return;
    if (filterYears) {
      const actualYear = year(movie);
      if (actualYear === null || (range.from && actualYear < fromYear) || (range.to && actualYear > toYear)) return;
    }
    // Resolve the canonical metadata and sort key once, outside the comparator.
    result.push(sortKey ? { row, key: sortKey(movie) } : row);
  });
  if (sortKey) {
    result.sort((a, b) => filters.sort === 'title.asc' ? a.key.localeCompare(b.key) : typeof a.key === 'string' ? b.key.localeCompare(a.key) : b.key - a.key);
    return result.map(entry => entry.row);
  }
  return result;
}

// TV lists reuse the existing TV predicate/sort contract within their membership.
export function tvListCriteria(filters, genres) {
  const groups = [];
  const add = (type, value) => groups.push({ type, values: [value] });
  const genre = genres.find(option => option.value === filters.genre);
  if (genre?.value) add('genre', { id: genre.value, label: genre.label });
  if (filters.country) add('country', { id: filters.country, label: catalogCountries.find(option => option.value === filters.country)?.label || filters.country });
  if (Number(filters.minRating)) add('rating', { operator: 'at_least', value: Number(filters.minRating) });
  if (Number(filters.minVotes)) add('minimum_votes', { value: Number(filters.minVotes) });
  const range = yearRangeDraft(filters.yearFrom, filters.yearTo);
  if (range.ready && (range.from || range.to)) add('year', range.from && range.to ? { operator: 'between', from: Number(range.from), to: Number(range.to) } : { operator: range.from ? 'at_least' : 'at_most', value: Number(range.from || range.to) });
  return { version: 1, media_type: 'tv', scope: 'discover', mode: 'simple', feed: 'catalog', groups, sort: { key: filters.sort, direction: filters.sort === 'title.asc' ? 'asc' : 'desc' } };
}
