import Button from '../../components/ui/Button.jsx';
import { Input } from '../../components/ui/FormField.jsx';
import { useState } from 'react';
import { fetchJson } from '../../api/client.js';
import Pagination from '../../components/Pagination.jsx';

const post = (url, body) => fetchJson(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });

export default function TVMaintenanceTab({ data = {}, notify, onRefresh, onPageChange }) {
  const [queries, setQueries] = useState({});
  const [candidates, setCandidates] = useState({});
  const [selections, setSelections] = useState({});
  const [episodeScopes, setEpisodeScopes] = useState({});
  const [busy, setBusy] = useState(false);
  const counts = data.counts || {};

  async function run(action) {
    setBusy(true);
    try { await action(); onRefresh(); }
    catch (error) { notify(error.message, 'error'); }
    finally { setBusy(false); }
  }

  async function find(item) {
    const query = queries[item.path] ?? item.title_hint ?? '';
    await run(async () => {
      const result = await fetchJson(`/api/tv/discover?query=${encodeURIComponent(query)}`);
      setCandidates((current) => ({ ...current, [item.path]: result.items || [] }));
    });
  }

  async function approveFolder(item) {
    const choice = selections[item.path];
    if (!choice) return;
    await run(async () => {
      const series = await post('/api/tv/series', { tmdb_id: choice.tmdb_id });
      await post('/api/tv/library/assignments', { path: item.path, kind: 'folder', series_id: series.id });
      notify(`${choice.title} assigned. The TV scan will link its episodes.`, 'success');
    });
  }

  async function applyEpisode(item) {
    const scope = episodeScopes[item.path] || {};
    const season = Number(scope.season ?? item.claim?.season_number);
    const numbers = String(scope.episodes ?? (item.claim?.episode_numbers || []).join(',')).split(',')
      .map((part) => Number(part.trim())).filter((value) => Number.isInteger(value) && value > 0);
    if (!Number.isInteger(season) || season < 0 || !numbers.length) {
      notify('Enter a season and one or more episode numbers.', 'error');
      return;
    }
    await run(async () => {
      const selection = await fetchJson(`/api/tv/series/${item.series_id}/selection?season=${season}`);
      const rows = numbers.map((number) => selection.items.find((row) => row.episode_number === number));
      if (rows.some((row) => !row || !row.id)) throw new Error('The selected episode is not in the local TV catalog. Refresh its metadata first.');
      await post(`/api/tv/review/${item.review_id}/apply`, { episode_ids: rows.map((row) => row.id) });
      notify('Episode file linked.', 'success');
    });
  }

  const refreshDiscovery = () => run(async () => { await post('/api/tv/library/discovery', {}); });
  const scanApproved = () => run(async () => { const result = await post('/api/tv/library/scan', {}); notify(`${result.accepted} linked; ${result.needs_review} need review.`, 'success'); });

  return <section aria-label="TV identity review" className="tv-maintenance">
    <div className="tv-actions"><Button type="button" disabled={busy} onClick={refreshDiscovery}>Find new TV folders</Button><Button type="button" disabled={busy} onClick={scanApproved}>Scan assigned TV files</Button></div>
    <p role="status">{counts.unidentified_folders || 0} unidentified folders · {counts.unresolved_episode_files || 0} unresolved episode files · {counts.conflicts || 0} conflicts · {counts.scan_errors || 0} scan errors · {counts.exclusions || 0} exclusions</p>
    <Pagination page={data.page || 1} total={data.total || 0} totalPages={data.total_pages || 1} pageStart={((data.page || 1)-1)*(data.page_size || 50)} pageEnd={((data.page || 1)-1)*(data.page_size || 50)+(data.items?.length || 0)} ariaLabel="TV maintenance pages" onPageChange={onPageChange} />
    {!data.items?.length && <p>No TV identity or file reviews match this search.</p>}
    {(data.items || []).map((item) => <article className="tv-import-group" key={`${item.kind}:${item.path}`}>
      <h3>{item.series_title || item.title_hint || (item.kind === 'exclusion' ? 'Excluded TV-root item' : 'Unidentified TV folder')}</h3>
      <p>{item.kind.replace('_', ' ')} · {item.state} · {item.files ?? 'folder'} {item.files === 1 ? 'file' : 'files'}</p>
      <code>{item.path}</code><p>{item.reason}</p>
      {item.sample_filenames?.length > 0 && <p>Examples: {item.sample_filenames.join(' · ')}</p>}
      {item.claim && <p>Parsed: {item.claim.series_title || 'title unknown'} · season {item.claim.season_number ?? 'unknown'} · episodes {(item.claim.episode_numbers || []).join(', ') || 'unknown'}</p>}
      {item.kind === 'show_folder' && <div className="tv-import-picker">
        <label>Find series <Input value={queries[item.path] ?? item.title_hint ?? ''} onChange={(event) => setQueries((current) => ({ ...current, [item.path]: event.target.value }))} /></label>
        <Button type="button" disabled={busy} onClick={() => find(item)}>Search TV identities</Button>
        <div className="tv-import-candidates">{(candidates[item.path] || item.candidates || []).map((candidate) =>
          <button type="button" key={candidate.tmdb_id} className={selections[item.path]?.tmdb_id === candidate.tmdb_id ? 'selected' : ''}
            onClick={() => setSelections((current) => ({ ...current, [item.path]: candidate }))}>{candidate.title} · {candidate.year || candidate.first_air_date?.slice(0, 4) || 'year unknown'} · TMDB TV {candidate.tmdb_id}</button>)}</div>
        {selections[item.path] && <Button type="button" disabled={busy} onClick={() => approveFolder(item)}>Assign folder to {selections[item.path].title}</Button>}
        <Button type="button" disabled={busy} onClick={() => run(() => post('/api/tv/maintenance/exclusions', { path: item.path, kind: 'folder', reason: 'Reviewed as non-TV or extra content' }))}>Exclude this folder from TV</Button>
      </div>}
      {item.kind === 'episode_file' && <div className="tv-import-picker">
        <label>Season <Input type="number" min="0" value={episodeScopes[item.path]?.season ?? item.claim?.season_number ?? ''}
          onChange={(event) => setEpisodeScopes((current) => ({ ...current, [item.path]: { ...current[item.path], season: event.target.value } }))} /></label>
        <label>Episode numbers, comma separated <Input value={episodeScopes[item.path]?.episodes ?? (item.claim?.episode_numbers || []).join(',')}
          onChange={(event) => setEpisodeScopes((current) => ({ ...current, [item.path]: { ...current[item.path], episodes: event.target.value } }))} /></label>
        <Button type="button" disabled={busy} onClick={() => applyEpisode(item)}>Verify and link this file</Button>
        <Button type="button" disabled={busy} onClick={() => run(() => post('/api/tv/maintenance/exclusions', { path: item.path, kind: 'file', reason: 'Reviewed as non-episode content' }))}>Exclude this file</Button>
      </div>}
      {item.kind === 'exclusion' && <Button type="button" disabled={busy} onClick={() => run(() => fetchJson('/api/tv/maintenance/exclusions', { method: 'DELETE', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path: item.path }) }))}>Remove exclusion</Button>}
    </article>)}
  </section>;
}
