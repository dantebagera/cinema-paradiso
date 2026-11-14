export function trailerPresentation(video) {
  const original = String(video.title || '').trim();
  const type = /fan[ -]?edit/i.test(original) ? 'Fan edit'
    : /featurette|behind.the.scenes/i.test(original) ? 'Featurette'
    : /teaser/i.test(original) ? (/official/i.test(original) ? 'Official teaser' : 'Teaser')
    : /official/i.test(original) ? 'Official trailer' : 'Trailer';
  const year = original.match(/\b(20\d{2})\b/)?.[1] || '';
  const title = String(video.movie_title || original
    .replace(/\s*[|–—]\s*.*$/, '')
    .replace(/\s*(?:[-:]\s*)?(?:official\s+)?(?:teaser\s+trailer|trailer|teaser|featurette|fan[ -]?edit|behind.the.scenes)\b.*$/i, '')
    .replace(/\s*\(20\d{2}\)\s*$/, '')).trim() || original || 'Untitled video';
  return { title, type, key: `${title.toLocaleLowerCase().replace(/[^\p{L}\p{N}]/gu, '')}:${year}` };
}

export function groupHomeTrailers(videos, source = 'all') {
  const groups = new Map();
  for (const video of videos || []) {
    if (source !== 'all' && video.source_id !== source) continue;
    const presentation = trailerPresentation(video);
    const group = groups.get(presentation.key) || { ...presentation, videos: [] };
    if (!group.videos.some(item => item.video_id === video.video_id)) group.videos.push(video);
    groups.set(presentation.key, group);
  }
  return [...groups.values()];
}
