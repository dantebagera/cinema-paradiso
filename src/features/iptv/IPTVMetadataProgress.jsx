import { formatCount } from '../../utils/appUtils.js';

export default function IPTVMetadataProgress({ label, processed, total, description, segments, remainingLabel = 'remaining' }) {
  const percent = total ? Math.min(100, processed / total * 100) : 0;
  return <>
    <div className="iptv-progress-heading">
      <strong>{formatCount(processed)} of {formatCount(total)} {description} ({percent.toFixed(2)}%)</strong>
      <span>{formatCount(Math.max(0, total - processed))} {remainingLabel}</span>
    </div>
    <div className="iptv-progress-track" role="progressbar" aria-valuemin="0" aria-valuemax={total || 1}
      aria-valuenow={processed} aria-label={label}>
      {segments.map(([style, , count]) => <span key={style} className={style}
        style={{ width: `${total ? count / total * 100 : 0}%` }} />)}
    </div>
    <div className="iptv-progress-legend">
      {segments.map(([style, name, count]) => <span key={style} className={style}>{formatCount(count)} {name}</span>)}
    </div>
  </>;
}
