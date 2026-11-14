import { useState } from 'react';
import DiscoverResultGrid from '../../components/DiscoverResultGrid.jsx';
import SelectionCheckbox from '../../components/SelectionCheckbox.jsx';
import AIControlSelectionBar from '../ai-control/AIControlSelectionBar.jsx';
import { TVSeriesCard } from '../tv/TVWorkspace.jsx';
import { IPTVMovieCard, PosterTile } from '../iptv/IPTVCards.jsx';
import { openAIReview } from './aiClient.js';

export default function DomainActionRows({ plan, allRows, rows, selectedKeys, allResultsSelected, onToggleSelection,
  onSelectAll, onClearSelection, onConfirm, confirmDisabled, busy, gridRef }) {
  const [expanded, setExpanded] = useState('');
  return <div className="ai-control-card-results">
    <AIControlSelectionBar selectedCount={allRows.filter(row => selectedKeys.has(row.selection_key)).length}
      allResultsSelected={allResultsSelected} onSelectAll={onSelectAll} onClearSelection={onClearSelection}
      onConfirm={onConfirm} confirmDisabled={confirmDisabled} busy={busy} />
    <DiscoverResultGrid gridRef={gridRef} emptyText="No reviewed targets.">
      {rows.map(row => {
        const key = row.selection_key;
        if (plan.domain === 'tv' && row.series_id) return <TVSeriesCard key={key} series={row} reviewOnly
          selected={selectedKeys.has(key)} onSelect={(_, checked) => onToggleSelection(key, checked)}
          onOpen={() => openAIReview('tv', { series_id: row.series_id })} />;
        if (plan.domain === 'iptv' && row.iptv_ref) {
          const ref = row.iptv_ref;
          if (ref.kind === 'movie') return <IPTVMovieCard key={key} providerId={ref.provider_id} movie={row}
            selectedId={expanded} onToggle={() => setExpanded(current => current === row.movie_key ? '' : row.movie_key)}
            reviewOnly selectable checked={selectedKeys.has(key)} onSelect={() => onToggleSelection(key, !selectedKeys.has(key))} />;
          return <PosterTile key={key} providerId={ref.provider_id} item={row} reviewOnly selectable
            checked={selectedKeys.has(key)} onSelect={() => onToggleSelection(key, !selectedKeys.has(key))}
            onClick={() => openAIReview('iptv', ref)} />;
        }
        return <div className="settings-checkbox-field ai-domain-target" key={key}>
          <SelectionCheckbox checked={selectedKeys.has(key)} onChange={checked => onToggleSelection(key, checked)}
            label={`Select ${row.title || row.name || 'reviewed target'}`} />
          <span><strong>{row.title || row.name || 'Reviewed target'}</strong>{row.category && <small>{row.category}</small>}</span>
        </div>;
      })}
    </DiscoverResultGrid>
  </div>;
}
