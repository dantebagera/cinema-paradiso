import { AlertTriangle, CheckCircle2, Copy, Folder, HardDrive, Loader2, Search, X } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { fetchJson } from '../api/client.js';
import { formatCount } from '../utils/appUtils.js';

export default function ExportCopyDialog({ movies, onClose, notify }) {
  const [destination, setDestination] = useState('');
  const [job, setJob] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [folderBrowserOpen, setFolderBrowserOpen] = useState(false);
  const localCount = movies.filter((movie) => movie.path).length;
  const completed = job && ['completed', 'completed_with_errors', 'failed', 'cancelled'].includes(job.status);
  const percent = job?.bytes_total ? Math.min(100, Math.round((Number(job.bytes_done || 0) / Number(job.bytes_total || 1)) * 100)) : 0;

  useEffect(() => {
    if (!job?.id || completed) return undefined;
    const timer = window.setInterval(async () => {
      try {
        const next = await fetchJson(`/api/library/export-jobs/${encodeURIComponent(job.id)}`);
        setJob(next);
        if (['completed', 'completed_with_errors'].includes(next.status)) notify?.(`Copied ${formatCount(next.copied_count || 0)} movie file${Number(next.copied_count || 0) === 1 ? '' : 's'}`);
      } catch (pollError) {
        setError(pollError.message);
      }
    }, 900);
    return () => window.clearInterval(timer);
  }, [job?.id, completed, notify]);

  async function startCopy(event) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      setJob(await fetchJson('/api/library/export-jobs', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ movies, destination }) }));
    } catch (copyError) {
      setError(copyError.message);
    } finally {
      setBusy(false);
    }
  }

  async function cancelCopy() {
    if (!job?.id) return;
    try {
      setJob(await fetchJson(`/api/library/export-jobs/${encodeURIComponent(job.id)}/cancel`, { method: 'POST' }));
      notify?.('Copy job cancelled', 'neutral');
    } catch (cancelError) {
      setError(cancelError.message);
    }
  }

  return <>
    <div className="modal-backdrop export-copy-backdrop" role="presentation" onClick={onClose}>
      <form className="small-dialog export-copy-dialog" role="dialog" aria-modal="true" aria-label="Copy selected movies" onClick={(event) => event.stopPropagation()} onSubmit={startCopy}>
        <div className="dialog-header"><div><p className="screen-kicker">Export list movies</p><h2>Copy selected to...</h2></div><button type="button" className="inspector-close" onClick={onClose} aria-label="Close copy dialog"><X size={18} /></button></div>
        <p className="dialog-body-path">{formatCount(movies.length)} selected, {formatCount(localCount)} local file{localCount === 1 ? '' : 's'} available to copy. Existing files are skipped.</p>
        <label className="dialog-field"><span>Destination folder</span><div className="folder-path-row"><input value={destination} onChange={(event) => setDestination(event.target.value)} placeholder="E:\\Friend USB\\Movies or \\\\server\\share\\movies" disabled={Boolean(job && !completed)} /><button type="button" className="btn btn-secondary" onClick={() => setFolderBrowserOpen(true)} disabled={Boolean(job && !completed)}><Folder size={15} /> Browse...</button></div></label>
        {job && <div className="export-progress"><div className="export-progress-track"><span style={{ width: `${percent}%` }} /></div><p><strong>{job.status}</strong><span>{formatCount(job.copied_count || 0)} copied, {formatCount(job.skipped_count || 0)} skipped, {formatCount(job.failed_count || 0)} failed</span></p>{job.current && <small>Copying {job.current}</small>}</div>}
        {error && <p className="dialog-error"><AlertTriangle size={14} /> {error}</p>}
        <div className="dialog-actions"><button type="button" className="btn btn-secondary" onClick={onClose}>Close</button>{job && !completed ? <button type="button" className="btn btn-secondary" onClick={cancelCopy}>Cancel copy</button> : <button type="submit" className="btn btn-primary" disabled={busy || !destination.trim() || !movies.length}>{busy ? <Loader2 size={15} className="spin" /> : <Copy size={15} />} Start copy</button>}</div>
      </form>
    </div>
    {folderBrowserOpen && <FolderBrowserDialog initialPath={destination} onClose={() => setFolderBrowserOpen(false)} onSelect={(path) => { setDestination(path); setFolderBrowserOpen(false); }} />}
  </>;
}

export function FolderBrowserDialog({ initialPath, onSelect, onClose }) {
  const [manualPath, setManualPath] = useState(initialPath || '');
  const [data, setData] = useState({ current_path: '', parent: '', roots: [], entries: [] });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const loadFolder = useCallback(async (path = '') => {
    const clean = String(path || '').trim();
    setLoading(true); setError('');
    try {
      const next = await fetchJson(`/api/system/folders${clean ? `?path=${encodeURIComponent(clean)}` : ''}`);
      setData(next);
      if (next.current_path) setManualPath(next.current_path);
    } catch (browseError) { setError(browseError.message); } finally { setLoading(false); }
  }, []);
  useEffect(() => { loadFolder(initialPath || ''); }, [initialPath, loadFolder]);
  const roots = data.roots || [];
  const entries = data.entries || [];
  return <div className="modal-backdrop folder-browser-backdrop" role="presentation" onClick={onClose}>
    <div className="small-dialog folder-browser-dialog" role="dialog" aria-modal="true" aria-label="Browse destination folder" onClick={(event) => event.stopPropagation()}>
      <div className="dialog-header"><div><p className="screen-kicker">Copy destination</p><h2>Browse folders</h2></div><button type="button" className="inspector-close" onClick={onClose} aria-label="Close folder browser"><X size={18} /></button></div>
      <form className="folder-browser-path-form" onSubmit={(event) => { event.preventDefault(); loadFolder(manualPath); }}><input value={manualPath} onChange={(event) => setManualPath(event.target.value)} placeholder="Type a folder path or network share" /><button type="submit" className="btn btn-secondary" disabled={loading}>{loading ? <Loader2 size={15} className="spin" /> : <Search size={15} />} Open</button></form>
      {data.current_path && <div className="folder-current-path"><span>{data.current_path}</span><button type="button" className="btn btn-primary" onClick={() => onSelect(data.current_path)}><CheckCircle2 size={15} /> Use this folder</button></div>}
      {error && <p className="dialog-error"><AlertTriangle size={14} /> {error}</p>}
      <div className="folder-browser-grid"><div><h3>Quick locations</h3><div className="folder-browser-list">{roots.map((entry) => <button type="button" key={entry.path} onClick={() => loadFolder(entry.path)}><HardDrive size={15} /> <span>{entry.name}</span></button>)}</div></div><div><h3>Folders</h3><div className="folder-browser-list">{data.parent && <button type="button" onClick={() => loadFolder(data.parent)}><Folder size={15} /> <span>..</span></button>}{entries.map((entry) => <button type="button" key={entry.path} onClick={() => loadFolder(entry.path)}><Folder size={15} /> <span>{entry.name}</span></button>)}{!loading && !entries.length && !data.parent && <span className="folder-browser-empty">Choose a quick location or type a path.</span>}{!loading && data.current_path && !entries.length && <span className="folder-browser-empty">No child folders.</span>}</div></div></div>
      <div className="dialog-actions"><button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button><button type="button" className="btn btn-primary" onClick={() => onSelect(data.current_path)} disabled={!data.current_path}><CheckCircle2 size={15} /> Select folder</button></div>
    </div>
  </div>;
}
