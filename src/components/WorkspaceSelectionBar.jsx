import SelectionCheckbox from './SelectionCheckbox.jsx';
import { formatCount } from '../utils/appUtils.js';
import Button from './ui/Button.jsx';

export default function WorkspaceSelectionBar({ className = '', noun = 'movies', selectedCount, allSelected, onToggleAll, label, onSelectAll, selectAllLabel = 'Select all results', onClear, children, showZeroCount = false, showActionsWhenEmpty = false, clearDisabled = false, checkboxClassName }) {
  return <div className={`bulk-selection-bar workspace-selection-bar ${className}`}>
    {onToggleAll && <SelectionCheckbox className={checkboxClassName} checked={allSelected} onChange={onToggleAll} label={label}/>}
    <span>{selectedCount || showZeroCount ? `${formatCount(selectedCount)} selected` : `Select ${noun}`}</span>
    {onSelectAll && <Button type="button" size="compact" onClick={onSelectAll}>{selectAllLabel}</Button>}
    {(selectedCount > 0 || showActionsWhenEmpty) && <><Button type="button" size="compact" onClick={onClear} disabled={clearDisabled}>Clear</Button>{children}</>}
  </div>;
}
