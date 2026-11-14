import DialogShell from '../../components/ui/DialogShell.jsx';
import Button from '../../components/ui/Button.jsx';
import { Select } from '../../components/ui/FormField.jsx';
import { useCallback, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import WorkspaceSelectionBar from '../../components/WorkspaceSelectionBar.jsx';
import { fetchJson } from '../../api/client.js';
import useDismissiblePopover from '../../hooks/useDismissiblePopover.js';

const post = (url, body) => fetchJson(url, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});

export default function TVBulkActionBar({ seriesIds = [], seriesRows, onResolved, allSelected, onToggleAll, onSelectAll, onClear, onChanged, onError, notify, showAdd = true, ready = true }) {
  const rows = seriesRows || seriesIds.map(id => ({ id }));
  const localIds = rows.filter(row => row.id).map(row => row.id);
  const [lists, setLists] = useState([]);
  const [listId, setListId] = useState('');
  const [dialog, setDialog] = useState(null);
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [reviewIds, setReviewIds] = useState([]);
  const [reviewRows, setReviewRows] = useState([]);
  const ownerRef = useRef(null);
  const panelRef = useRef(null);
  const reviewRequest = useRef(0);
  useEffect(() => () => { reviewRequest.current += 1; }, []);
  const dismissReview = useCallback(() => {
    reviewRequest.current += 1;
    setDialog(null); setPreview(null); setError(''); setBusy(false);
  }, []);
  useDismissiblePopover(Boolean(dialog), dismissReview, ownerRef, panelRef, undefined,
    { dismissOutside: false, dismissEscape: false, workspaceOnly: true });
  function showError(message) { setError(message); onError?.(message); }
  useEffect(() => { if (!showAdd || !ready) return; fetchJson('/api/tv/lists').then(data => setLists(data.lists.filter(row => !row.system))).catch(() => {}); }, [showAdd, ready]);
  async function membership(watchlist = false) {
    setBusy(true); showError('');
    try {
      const resolved = [];
      for (const row of rows) {
        const id = row.id || (await post('/api/tv/series', { tmdb_id: row.tmdb_id })).id;
        if (!id) throw new Error('TV catalog did not return a series identity. Please retry.');
        const next = { ...row, id };
        onResolved?.(next);
        resolved.push(id);
        if (watchlist) await post(`/api/tv/series/${id}/watchlist`, { watchlisted: true });
      }
      if (!watchlist) await post(`/api/tv/lists/${listId}/series`, { series_ids: resolved });
      onChanged(); onClear(rows); notify(watchlist ? 'Selected TV shows added to Watchlist' : 'Selected TV shows added to the list', 'success');
    } catch (cause) { showError(cause.message); notify(cause.message, 'error'); }
    finally { setBusy(false); }
  }
  async function open(kind) {
    const request = ++reviewRequest.current;
    setBusy(true); showError(''); setPreview(null); setReviewIds(localIds); setReviewRows(rows.filter(row => row.id)); setDialog(kind);
    try {
      const result = await post(`/api/tv/bulk/${kind}/preview`, {series_ids:localIds});
      if (request === reviewRequest.current) setPreview(result);
    } catch (cause) { if (request === reviewRequest.current) showError(cause.message); }
    finally { if (request === reviewRequest.current) setBusy(false); }
  }
  async function confirm() { setBusy(true); setError(''); try {
    const result = await post(`/api/tv/bulk/${dialog}`, dialog === 'delete' ? {series_ids:reviewIds, token:preview.token} : {series_ids:reviewIds});
    if (dialog === 'delete') notify(`${result.removed.length} TV files moved to Recycle Bin${result.failed.length ? `; ${result.failed.length} failed` : ''}`, result.failed.length ? 'error' : 'success');
    else notify(`${result.tasks.length} one-shot TV download actions started`, 'success');
    setDialog(null); setPreview(null); onClear(reviewRows); onChanged();
  } catch (cause) { showError(cause.message); } finally { setBusy(false); } }
  return <div ref={ownerRef} className="tv-bulk-actions"><WorkspaceSelectionBar noun="TV shows" selectedCount={rows.length} allSelected={allSelected} onToggleAll={onToggleAll} label="Select all loaded TV shows" selectAllLabel="Select all loaded TV shows" onSelectAll={onSelectAll} onClear={() => onClear()}>
    {showAdd && <><Select aria-label="Add selected TV shows to list" value={listId} onChange={event => setListId(event.target.value)}><option value="">Choose TV custom list</option>{lists.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</Select><Button size="compact" type="button"  disabled={!listId || busy} onClick={() => membership()}>Add to a list</Button><Button size="compact" type="button"  disabled={busy} onClick={() => membership(true)}>Add to Watchlist</Button></>}
    <Button variant="danger" size="compact" type="button"  disabled={busy || !localIds.length} onClick={() => open('delete')}>Delete local files</Button><Button size="compact" type="button"  disabled={busy || !localIds.length} onClick={() => open('download')}>Download released episodes</Button>
    {localIds.length < rows.length && <span className="workspace-selection-note">Downloads and file deletion: {localIds.length} cataloged of {rows.length} selected.</span>}
    </WorkspaceSelectionBar>
    {error && !dialog && !onError && <p role="alert">{error}</p>}
    {dialog && createPortal(<div className="modal-backdrop"><DialogShell size="wide" ref={panelRef} className="tv-bulk-dialog" role="dialog" aria-modal="true" aria-label={dialog === 'delete' ? 'Review TV file deletion' : 'Review TV bulk download'}>
      <h2>{dialog === 'delete' ? 'Move exact TV files to Recycle Bin?' : 'Download released missing episodes?'}</h2>
      {busy && !preview && <p role="status">Checking selected shows…</p>}{error && <p role="alert">{error}</p>}
      {dialog === 'delete' && preview && <><p>{preview.video_count} video files and {preview.sidecar_count} paired sidecars. Watch history and TV list membership stay.</p>
        {preview.shows.map(show => <div key={show.series_id}><strong>{show.title}</strong>{show.blocked && <p role="alert">Blocked: {show.reasons.join('; ')}</p>}</div>)}
        <ul className="tv-bulk-paths">{preview.files.map(item => <li key={item.path}>{item.kind}: {item.path}</li>)}</ul></>}
      {dialog === 'download' && preview && <><p>This searches released regular episodes once. Episodes with no source are reported in task history; future episodes are not followed.</p>
        <p>Verified episodes move into the season folder. Completed downloads are removed from qBittorrent.</p>
        {preview.items.map(item => <div key={item.series_id}><p>Show {item.series_id}: {item.counts.released_missing} missing · {item.counts.owned} owned · {item.counts.review} needs review · {item.counts.queued} queued{!item.metadata_complete ? ' · metadata incomplete' : ''}</p>{item.import_destinations?.map(destination=><p key={destination.season}>Season {destination.season}: {destination.state==='ready'?destination.path:destination.reason}</p>)}</div>)}</>}
      <div className="tv-actions"><Button type="button" onClick={dismissReview}>Cancel</Button><Button variant="primary" type="button"  disabled={busy || !preview || (dialog === 'delete' && (preview.blocked || !preview.video_count)) || (dialog === 'download' && preview.items.some(item => !item.metadata_complete || item.counts.review))} onClick={confirm}>{dialog === 'delete' ? 'Move listed files to Recycle Bin' : 'Start one-shot downloads'}</Button></div>
    </DialogShell></div>, document.body)}
  </div>;
}
