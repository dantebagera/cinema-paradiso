import { cx } from '../utils/appUtils.js';

export default function ExperimentalBadge({ className = '' }) {
  return <span className={cx('experimental-badge', className)}>Experimental</span>;
}
