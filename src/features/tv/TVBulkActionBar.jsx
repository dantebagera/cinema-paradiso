import { useEffect, useState } from 'react';
import { fetchJson } from '../../api/client.js';

const post = (url, body) => fetchJson(url, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});

export default function TVBulkActionBar({ seriesIds, onClear, onChanged, notify, showAdd = true }) {
  const [lists, setLists] = useState([]);
  const [listId, setListId] = useState('');
  const [dialog, setDialog] = useState(null);
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => { if (!showAdd) return; fetchJson('/api/tv/lists?list_id=watchlist&page_size=1').then(data => setLists(data.lists.filter(row => !row.system))).catch(() => {}); }, [showAdd]);
  async function add() { setBusy(true); setError(''); try { await post(`/api/tv/lists/${listId}/series`, {series_ids:seriesIds}); onChanged(); onClear(); notify('Selected TV shows added to the list', 'success'); } catch (cause) { setError(cause.message); } finally { setBusy(false); } }
  async function open(kind) { setBusy(true); setError(''); setPreview(null); setDialog(kind); try { setPreview(await post(`/api/tv/bulk/${kind}/preview`, {series_ids:seriesIds})); } catch (cause) { setError(cause.message); } finally { setBusy(false); } }
  async function confirm() { setBusy(true); setError(''); try {
    const result = await post(`/api/tv/bulk/${dialog}`, dialog === 'delete' ? {series_ids:seriesIds, token:preview.token} : {series_ids:seriesIds});
    if (dialog === 'delete') notify(`${result.removed.length} TV files moved to Recycle Bin${result.failed.length ? `; ${result.failed.length} failed` : ''}`, result.failed.length ? 'error' : 'success');
    else notify(`${result.tasks.length} one-shot TV download actions started`, 'success');
    setDialog(null); setPreview(null); onClear(); onChanged();
  } catch (cause) { setError(cause.message); } finally { setBusy(false); } }
  return <div className="tv-bulk-actions"><div className="bulk-selection-bar"><strong>{seriesIds.length} selected TV shows</strong><button type="button" onClick={onClear}>Clear</button>
    {showAdd && <><select aria-label="Add selected TV shows to list" value={listId} onChange={event => setListId(event.target.value)}><option value="">Choose TV custom list</option>{lists.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</select><button type="button" disabled={!listId || busy} onClick={add}>Add to a list</button></>}
    <button type="button" disabled={busy} onClick={() => open('delete')}>Delete local files</button><button type="button" disabled={busy} onClick={() => open('download')}>Download released episodes</button></div>
    {error && !dialog && <p role="alert">{error}</p>}
    {dialog && <div className="modal-backdrop"><section className="tv-bulk-dialog" role="dialog" aria-modal="true" aria-label={dialog === 'delete' ? 'Review TV file deletion' : 'Review TV bulk download'}>
      <h2>{dialog === 'delete' ? 'Move exact TV files to Recycle Bin?' : 'Download released missing episodes?'}</h2>
      {busy && !preview && <p role="status">Checking selected shows…</p>}{error && <p role="alert">{error}</p>}
      {dialog === 'delete' && preview && <><p>{preview.video_count} video files and {preview.sidecar_count} paired sidecars. Watch history and TV list membership stay.</p>
        {preview.shows.map(show => <div key={show.series_id}><strong>{show.title}</strong>{show.blocked && <p role="alert">Blocked: {show.reasons.join('; ')}</p>}</div>)}
        <ul className="tv-bulk-paths">{preview.files.map(item => <li key={item.path}>{item.kind}: {item.path}</li>)}</ul></>}
      {dialog === 'download' && preview && <><p>This searches released regular episodes once. Episodes with no source are reported in task history; future episodes are not followed.</p>
        <p>Verified episodes move into the season folder. Completed downloads are removed from qBittorrent.</p>
        {preview.items.map(item => <div key={item.series_id}><p>Show {item.series_id}: {item.counts.released_missing} missing · {item.counts.owned} owned · {item.counts.review} needs review · {item.counts.queued} queued{!item.metadata_complete ? ' · metadata incomplete' : ''}</p>{item.import_destinations?.map(destination=><p key={destination.season}>Season {destination.season}: {destination.state==='ready'?destination.path:destination.reason}</p>)}</div>)}</>}
      <div className="tv-actions"><button type="button" onClick={() => { setDialog(null); setError(''); }}>Cancel</button><button type="button" className="primary-button" disabled={busy || !preview || (dialog === 'delete' && (preview.blocked || !preview.video_count)) || (dialog === 'download' && preview.items.some(item => !item.metadata_complete || item.counts.review))} onClick={confirm}>{dialog === 'delete' ? 'Move listed files to Recycle Bin' : 'Start one-shot downloads'}</button></div>
    </section></div>}
  </div>;
}
