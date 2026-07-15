import { getMovieIdentity } from './libraryUtils.js';

export function filterIdentityReviewItems(items, filters) {
  const q = String(filters.query || '').trim().toLowerCase();
  return (items || []).filter((item) => {
    if (filters.identity && filters.identity !== 'all' && item.classification !== filters.identity) return false;
    if (!q) return true;
    const haystack = [
      item.filename,
      item.path,
      item.current?.title,
      item.current?.year,
      item.candidate?.title,
      item.candidate?.name,
      item.candidate?.year,
      ...(item.reasons || [])
    ].filter(Boolean).join(' ').toLowerCase();
    return haystack.includes(q);
  });
}

export function renameModalItem(item) {
  const title = item.suggested_title || getMovieIdentity(item).title;
  const year = item.suggested_year || getMovieIdentity(item).year;
  return { ...item, title: `${title}${year ? ` (${year})` : ''}` };
}

export function metadataStatusLabel(item) {
  if (item.metadata_status === 'pending') return 'Pending metadata';
  if (item.metadata_status === 'conflict') return 'Conflict';
  if (item.metadata_status === 'unverified') return 'Verification gap';
  if (item.metadata_status === 'review') return 'Needs review';
  if (item.metadata_status === 'needs_review') return 'Needs review';
  if (item.in_plex && !item.plex_matched) return 'Plex unmatched';
  if (!item.tmdb_id) return 'TMDB unmatched';
  return 'Unmatched metadata';
}

export function metadataStatusChipClass(item) {
  if (item.metadata_status === 'pending') return 'chip-warning';
  if (item.metadata_status === 'conflict') return 'chip-warning';
  if (item.metadata_status === 'unverified') return 'chip-warning';
  if (item.metadata_status === 'review') return 'chip-warning';
  return 'status-missing';
}
