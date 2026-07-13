export function isUnreleasedMovie(movie) {
  const releaseDate = String(movie?.release_date || '').trim();
  if (!/^\d{4}-\d{2}-\d{2}$/.test(releaseDate)) return false;
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  return releaseDate > `${now.getFullYear()}-${month}-${day}`;
}

const RELEASE_MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

export function formatReleaseDateLabel(value) {
  const releaseDate = String(value || '').trim();
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(releaseDate);
  if (!match) return '';
  const [, year, month, day] = match;
  const monthIndex = Number(month) - 1;
  const dayNumber = Number(day);
  if (monthIndex < 0 || monthIndex > 11 || dayNumber < 1 || dayNumber > 31) return '';
  return `${RELEASE_MONTHS[monthIndex]} ${dayNumber}, ${year}`;
}

export function formatVoteCount(value) {
  const votes = Number(value || 0);
  if (!votes) return '';
  if (votes >= 1000000) return `${(votes / 1000000).toFixed(votes >= 10000000 ? 0 : 1)}M votes`;
  if (votes >= 1000) return `${(votes / 1000).toFixed(votes >= 10000 ? 0 : 1)}K votes`;
  return `${votes} votes`;
}
