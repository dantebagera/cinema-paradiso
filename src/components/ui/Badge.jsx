const tones = new Set(['neutral', 'owned', 'following', 'warning', 'danger', 'missing']);

// Domain owners supply the meaning; a badge never derives status from a record.
export default function Badge({ kind = 'metadata', size = 'regular', tone = 'neutral', muted = false,
  children, className = '', ...props }) {
  const appearance = kind === 'owned' ? 'unified-owned-badge'
    : kind === 'status' ? `unified-status-chip unified-status-${tones.has(tone) ? tone : 'neutral'}`
      : 'unified-chip';
  return <span {...props} className={[
    'cp-badge', appearance, size === 'compact' && 'cp-badge-compact',
    muted && 'unified-chip-muted', kind === 'metadata' && tone !== 'neutral' && `unified-chip-${tone}`, className
  ].filter(Boolean).join(' ')}>{children}</span>;
}
