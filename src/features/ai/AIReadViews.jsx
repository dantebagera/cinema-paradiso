import Button from '../../components/ui/Button.jsx';
import { useState } from 'react';
import AIControlResult from '../ai-control/AIControlResult.jsx';
import { TVSeriesCard } from '../tv/TVWorkspace.jsx';
import { IPTVMovieCard, PosterTile } from '../iptv/IPTVCards.jsx';
import DiscoverResultGrid from '../../components/DiscoverResultGrid.jsx';
import { openAIReview } from './aiClient.js';

export default function AIReadViews({ views = [], ...movieProps }) {
  const [expanded, setExpanded] = useState('');
  const prepared = new Set(views.filter(view => view.kind === 'action-plan').map(view => view.plan?.result_set_id || view.plan?.operation?.result_set));
  return views.filter(view => view.kind !== 'action-plan').map((view, index) => {
    if (view.kind === 'open-review') return <section className="ai-control-result" key={index}>
      <p>Open the existing {view.data.surface} workspace to review this request.</p>
      <Button type="button"  onClick={() => openAIReview(
        view.data.surface === 'player' ? 'library' : view.data.surface, view.data.target_ref)}>Open {view.data.surface} review</Button>
    </section>;
    if (view.kind === 'movie-results') return prepared.has(view.result_set) ? null
      : <AIControlResult key={view.result_set} {...movieProps} aiControlPlan={view.plan} readOnly />;
    const payload = view.data || {};
    const items = Array.isArray(payload.items) ? payload.items : [];
    if (view.kind === 'tv-results') return <section className="ai-control-result" key={index}>
      <h3>TV results · {payload.total ?? items.length}</h3>
      <DiscoverResultGrid>{items.map(row => <TVSeriesCard key={row.id || row.tmdb_id} series={row} reviewOnly context="discover"
        onOpen={() => openAIReview('tv', { series_id: row.id, tmdb_id: row.tmdb_id })} />)}</DiscoverResultGrid>
      <Button  type="button" onClick={() => openAIReview('tv')}>Open TV workspace</Button>
    </section>;
    if (view.kind === 'iptv-results') return <section className="ai-control-result" key={index}>
      <h3>IPTV results · {payload.total ?? items.length}</h3>
      <DiscoverResultGrid>{items.map((row, position) => row.media_ref?.kind === 'movie'
        ? <IPTVMovieCard key={row.movie_key || position} providerId={row.media_ref.provider_id} movie={row} reviewOnly
            selectedId={expanded} onToggle={() => setExpanded(current => current === row.movie_key ? '' : row.movie_key)} />
        : <PosterTile key={row.item_id || position} providerId={row.media_ref?.provider_id} item={row} reviewOnly
            onClick={() => openAIReview('iptv', row.media_ref)} />)}</DiscoverResultGrid>
      <Button  type="button" onClick={() => openAIReview('iptv')}>Open IPTV workspace</Button>
    </section>;
    const surface = view.kind.startsWith('tv-') ? 'tv' : view.kind.startsWith('iptv-') ? 'iptv'
      : view.kind === 'movie-match' || view.kind === 'maintenance' || view.kind === 'metadata-review' ? 'cleanup'
      : view.kind === 'copy-job' ? 'downloads' : 'library';
    return <section className="ai-control-result ai-read-result" key={index}>
      <h3>{view.kind.replaceAll('-', ' ')}</h3>
      {payload.title || payload.name ? <p>{payload.title || payload.name}</p> : null}
      {payload.state || payload.status ? <p>{String(payload.state || payload.status).replaceAll('_', ' ')}</p> : null}
      {payload.total != null && <p>{payload.total} results</p>}
      {payload.proposals && <p>{payload.proposals.length} proposals. Explicit review is required before applying changes.</p>}
      {items.slice(0, 20).map((row, rowIndex) => <p key={row.id || rowIndex}><strong>{row.title || row.name || row.provider_title || row.id}</strong>{row.body ? ` · ${row.body}` : ''}{row.state ? ` · ${row.state}` : ''}</p>)}
      {payload.episodes && <p>{payload.episodes.length} episode records in the requested scope</p>}
      {payload.summary && <div className="ai-feature-status">{Object.entries(payload.summary).filter(([, value]) => typeof value === 'number').map(([key, value]) => <p key={key}><span>{key.replaceAll('_', ' ')}</span><strong>{value}</strong></p>)}</div>}
      <Button type="button"  onClick={() => openAIReview(surface)}>Open {surface.replaceAll('-', ' ')} review</Button>
    </section>;
  });
}
