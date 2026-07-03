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

export function torrentPrimaryAction(item) {
  const magnet = String(item?.magnet_url || '').trim();
  if (magnet.toLowerCase().startsWith('magnet:')) return { kind: 'magnet', url: magnet };
  const torrent = String(item?.download_url || magnet).trim();
  if (/^https?:\/\//i.test(torrent)) return { kind: 'torrent', url: torrent };
  if (item?.info_url) return { kind: 'source', url: item.info_url };
  return { kind: 'none', url: '' };
}

export function sectionFromPath(pathname, navItems) {
  const section = String(pathname || '').replace(/^\/+/, '').split('/')[0];
  return navItems.some((item) => item.id === section) ? section : 'home';
}

export function topBarSearchEnabled(activeSection, discoverActiveTab) {
  return activeSection === 'home'
    || activeSection === 'library'
    || (activeSection === 'discover' && ['explore', 'browse'].includes(discoverActiveTab));
}

export function streamTemplateTokens(template) {
  const source = String(template || '');
  return ['imdb_id', 'tmdb_id'].filter((token) => source.includes(`{${token}}`));
}

export function buildStreamTemplateUrl(template, ids = {}) {
  const source = String(template || '').trim();
  if (!/^https?:\/\//i.test(source)) {
    throw new Error('Streaming URL template must start with http:// or https://');
  }
  const labels = {
    imdb_id: 'IMDB ID',
    tmdb_id: 'TMDB ID'
  };
  let url = source;
  for (const token of streamTemplateTokens(source)) {
    const value = String(ids[token] || '').trim();
    if (!value) throw new Error(`Missing ${labels[token]} for configured stream link`);
    url = url.replaceAll(`{${token}}`, encodeURIComponent(value));
  }
  return url;
}

export function toYouTubeEmbedUrl(url) {
  if (!url) return '';
  let parsed;
  try {
    parsed = new URL(String(url));
  } catch {
    return '';
  }

  const host = parsed.hostname.replace(/^www\./, '').toLowerCase();
  let videoId = '';
  if (host === 'youtube.com' || host === 'm.youtube.com') {
    if (parsed.pathname === '/watch') videoId = parsed.searchParams.get('v') || '';
    else if (parsed.pathname.startsWith('/embed/')) videoId = parsed.pathname.split('/')[2] || '';
  } else if (host === 'youtu.be') {
    videoId = parsed.pathname.split('/').filter(Boolean)[0] || '';
  }
  if (!/^[\w-]+$/.test(videoId)) return '';
  return `https://www.youtube.com/embed/${videoId}?autoplay=1&rel=0`;
}

export function youtubeTrailerSearchUrl(title, year) {
  const query = [title, year, 'trailer'].filter(Boolean).join(' ');
  return `https://www.youtube.com/results?search_query=${encodeURIComponent(query).replace(/%20/g, '+')}`;
}
