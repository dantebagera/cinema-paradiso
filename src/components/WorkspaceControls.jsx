import { useId, useLayoutEffect, useState } from 'react';
import { ChevronDown, ChevronUp, SlidersHorizontal } from 'lucide-react';
import { formatCount } from '../utils/appUtils.js';

// Presentation only: opening controls never runs a search or changes selection.
export default function WorkspaceControls({ search, filters, selection, actions, loadedCount = 0, countLabel = 'loaded', selectedCount = 0, summary, notice, expanded: controlledExpanded, onExpandedChange, autoCollapseKey = '' }) {
  const [localExpanded, setLocalExpanded] = useState(false);
  const [temporaryExpanded, setTemporaryExpanded] = useState(false);
  useLayoutEffect(() => setTemporaryExpanded(false), [autoCollapseKey]);
  // A card temporarily hides controls without overwriting the user's preference.
  // Manual toggles during card viewing last only until that card closes or changes.
  const expanded = autoCollapseKey ? temporaryExpanded : controlledExpanded ?? localExpanded;
  function toggleExpanded() {
    const next = !expanded;
    if (autoCollapseKey) {
      setTemporaryExpanded(next);
      return;
    }
    if (controlledExpanded === undefined) setLocalExpanded(next);
    onExpandedChange?.(next);
  }
  const bodyId = useId();
  return <section className="workspace-controls" aria-label="Search, filters and selection">
    <div className="workspace-controls-strip">
      <button type="button" className="workspace-controls-toggle" aria-label="Search, filters & selection" aria-expanded={expanded} aria-controls={bodyId} onClick={toggleExpanded}>
        <span className="workspace-controls-heading">
          <SlidersHorizontal size={16}/><span>Search, filters & selection</span>{expanded ? <ChevronUp size={16}/> : <ChevronDown size={16}/>}
        </span>
        <span className="workspace-controls-summary" role="status">
          <span>{formatCount(loadedCount)} {countLabel}</span>
          {summary && <span title={summary}>{summary}</span>}
          {selectedCount > 0 && <strong>Selected: {formatCount(selectedCount)}</strong>}
        </span>
      </button>
      {actions && <div className="workspace-controls-actions">{actions}</div>}
    </div>
    {notice && <div className="workspace-controls-notice">{notice}</div>}
    <div id={bodyId} className="workspace-controls-body" hidden={!expanded}>
      {search}
      {filters && <div className="workspace-controls-filters">{filters}</div>}
      {selection}
    </div>
  </section>;
}
