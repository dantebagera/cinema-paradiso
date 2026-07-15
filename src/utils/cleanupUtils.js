import { getMovieIdentity } from './libraryUtils.js';

export function filterCleanupItems(items, filters) {
  const q = filters.query.trim().toLowerCase();
  return items.filter((item) => {
    if (q) {
      const haystack = [item.title, item.filename, item.path, item.plex_title, item.plex_year, item.rip_source, item.resolution].filter(Boolean).join(' ').toLowerCase();
      if (!haystack.includes(q)) return false;
    }
    if (filters.resolution !== 'all' && item.resolution !== filters.resolution) return false;
    if (filters.source !== 'all' && item.rip_source !== filters.source) return false;
    if (filters.plex === 'matched' && !item.plex_matched) return false;
    if (filters.plex === 'unmatched' && item.plex_matched) return false;
    return true;
  });
}

export function filterMaintenanceIdentityItems(items, filters) {
  const q = filters.query.trim().toLowerCase();
  return items.filter((item) => {
    if (q) {
      const observations = item.observations || {};
      const haystack = [
        item.filename,
        item.path,
        item.accepted_title,
        item.accepted_year,
        item.suggested_title,
        item.suggested_year,
        item.plex_title,
        item.tmdb_title,
        item.metadata_hint,
        item.plex_hint,
        item.folder,
        observations.parsed?.title,
        observations.parsed?.year,
        observations.plex?.title,
        observations.plex?.year,
        observations.tmdb?.title,
        observations.tmdb?.year,
        ...(item.verification_reasons || []),
      ].filter(Boolean).join(' ').toLowerCase();
      if (!haystack.includes(q)) return false;
    }
    if (filters.plex === 'plex-unmatched' && item.plex_matched) return false;
    if (filters.plex === 'tmdb-unmatched' && item.tmdb_id) return false;
    if (filters.plex === 'pending' && item.metadata_status !== 'pending') return false;
    if (filters.plex === 'conflict' && item.metadata_status !== 'conflict') return false;
    if (filters.plex === 'needs_review' && item.metadata_status !== 'needs_review') return false;
    if (filters.identity && filters.identity !== 'all' && item.metadata_status !== filters.identity) return false;
    return true;
  });
}

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
