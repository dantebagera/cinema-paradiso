import { cx } from '../utils/appUtils.js';

export default function DiscoverResultGrid({ error, loading, emptyText, emptyHint, className, children }) {
  const items = Array.isArray(children) ? children.filter(Boolean) : children ? [children] : [];
  if (loading) {
    return <div className={cx('discover-grid', className)}><div className="movie-card skeleton-card" /><div className="movie-card skeleton-card" /><div className="movie-card skeleton-card" /></div>;
  }
  if (error) return <div className="empty-state discover-empty"><strong>Could not load this view.</strong><span>{error}</span></div>;
  if (!items.length) return <div className="empty-state discover-empty"><strong>{emptyText}</strong><span>{emptyHint || 'Check Settings if this depends on TMDB, Prowlarr, or Ollama.'}</span></div>;
  return <div className={cx('discover-grid', className)}>{items}</div>;
}
