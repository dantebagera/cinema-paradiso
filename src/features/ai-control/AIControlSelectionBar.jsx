import Button from '../../components/ui/Button.jsx';
import { Check, CirclePlus, Loader2, Search } from 'lucide-react';
import WorkspaceSelectionBar from '../../components/WorkspaceSelectionBar.jsx';

export default function AIControlSelectionBar({ selectedCount, allResultsSelected, onSelectAll, onClearSelection,
  onAddToList, onFindSources, onConfirm, confirmDisabled, busy }) {
  return <WorkspaceSelectionBar className="discover-bulk-selection ai-control-card-toolbar"
    checkboxClassName="discover-selection-master" selectedCount={selectedCount} allSelected={allResultsSelected}
    onToggleAll={checked => checked ? onSelectAll() : onClearSelection()} label="Select all AI Control results"
    onSelectAll={onSelectAll} onClear={onClearSelection} clearDisabled={!selectedCount} showZeroCount showActionsWhenEmpty>
    {onAddToList && <Button size="compact" type="button"  onClick={onAddToList} disabled={!selectedCount}><CirclePlus size={13} /> Add to list</Button>}
    {onFindSources && <Button variant="source" size="compact" type="button"  onClick={onFindSources} disabled={!selectedCount || busy}><Search size={13} /> Find sources</Button>}
    {onConfirm && <Button variant="primary" type="button" className="ai-control-confirm-action" onClick={onConfirm} disabled={confirmDisabled}>
      {busy ? <Loader2 size={15} className="spin" /> : <Check size={15} />} Confirm action
    </Button>}
  </WorkspaceSelectionBar>;
}
