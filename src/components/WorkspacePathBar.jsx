import Button from './ui/Button.jsx';
import { RefreshCcw } from 'lucide-react';

export default function WorkspacePathBar({
  history = [],
  currentLabel,
  resetLabel,
  ariaLabel = 'Navigation path',
  onBack,
  onReset,
  onCrumb
}) {
  if (!history.length && !currentLabel) return null;
  return (
    <div className="workspace-path-bar" aria-label={ariaLabel}>
      <Button size="compact" type="button"  onClick={onBack} disabled={!history.length}>
        Back
      </Button>
      <div className="workspace-path-crumbs">
        {history.map((item, index) => (
          <button type="button" aria-label={item.label} key={`${item.label}-${index}`} onClick={() => onCrumb(index)}>
            {item.label}
          </button>
        ))}
        {currentLabel && <span>{currentLabel}</span>}
      </div>
      <Button size="compact" type="button"  onClick={onReset}>
        <RefreshCcw size={13} /> {resetLabel}
      </Button>
    </div>
  );
}
