import { formatCount } from '../utils/appUtils.js';
import Button from './ui/Button.jsx';

export default function Pagination({
  total,
  page,
  totalPages,
  pageStart,
  pageEnd,
  summary = '',
  hasPrevious,
  hasNext,
  ariaLabel = 'Library pagination',
  previousLabel = 'Previous',
  nextLabel = 'Next',
  previousAriaLabel,
  nextAriaLabel,
  onPageChange,
  showSinglePage = false,
  className = ''
}) {
  const knownTotal = Number.isFinite(Number(totalPages)) && totalPages != null;
  const canPrevious = hasPrevious ?? page > 1;
  const canNext = hasNext ?? (knownTotal && page < totalPages);
  if (!showSinglePage && !canPrevious && !canNext && (!knownTotal || totalPages <= 1)) return null;
  const rangeKnown = Number.isFinite(pageStart) && Number.isFinite(pageEnd);
  const rangeLabel = rangeKnown ? `Showing ${formatCount(pageStart + 1)}-${formatCount(pageEnd)}${total == null ? '' : ` of ${formatCount(total)}`}` : '';
  return (
    <nav className={`library-pagination ${className}`} aria-label={ariaLabel}>
      <Button type="button" aria-label={previousAriaLabel} onClick={() => onPageChange(page - 1)} disabled={!canPrevious}>{previousLabel}</Button>
      <div className="library-page-status">
        <strong>{knownTotal ? `Page ${formatCount(page)} of ${formatCount(totalPages)}` : `Page ${formatCount(page)}`}</strong>
        {(summary || rangeLabel) && <span>{summary || rangeLabel}</span>}
      </div>
      <Button type="button" aria-label={nextAriaLabel} onClick={() => onPageChange(page + 1)} disabled={!canNext}>{nextLabel}</Button>
    </nav>
  );
}
