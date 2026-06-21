export function cx(...classes) {
  return classes.filter(Boolean).join(' ');
}

export function formatCount(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '0';
  return Number(value).toLocaleString();
}

export function movieKey(movie) {
  return `${String(movie.title || '').toLowerCase()}|${String(movie.year || '')}`;
}

export function sortFollowedReleases(items) {
  const rank = { available: 0, watching: 1, owned: 2 };
  return [...(items || [])].sort((a, b) => (
    (rank[a.status] ?? 3) - (rank[b.status] ?? 3)
    || Number(b.updated_at || b.followed_at || 0) - Number(a.updated_at || a.followed_at || 0)
  ));
}

export function getUniqueOptions(items, getter) {
  return [...new Set(items.flatMap((item) => {
    const value = getter(item);
    if (Array.isArray(value)) return value.filter(Boolean);
    return value ? [value] : [];
  }))].sort((a, b) => String(a).localeCompare(String(b)));
}

export function torrentSizeBytes(item) {
  return Number(item?.size_bytes || item?.size || 0);
}

export function sectionFromPath(pathname, navItems) {
  const section = String(pathname || '').replace(/^\/+/, '').split('/')[0];
  return navItems.some((item) => item.id === section) ? section : 'home';
}
