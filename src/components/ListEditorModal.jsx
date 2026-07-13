import { AlertTriangle, CirclePlus, Loader2, Search, Trash2, X } from 'lucide-react';
import { useMemo, useState } from 'react';
import { formatCount } from '../utils/appUtils.js';
import { movieIdentityKey, moviePayload } from '../utils/libraryUtils.js';

export default function ListEditorModal({ item, bulkItems = [], items, lists, onClose, onCreate, onAdd, onAddBulk }) {
  const [name, setName] = useState('');
  const [selected, setSelected] = useState(() => (bulkItems.length ? bulkItems : item ? [item] : []));
  const [search, setSearch] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const selectedKeys = useMemo(() => new Set(selected.map((movie) => movieIdentityKey(moviePayload(movie)))), [selected]);
  const selectedPayloads = useMemo(() => selected.map((movie) => moviePayload(movie)), [selected]);
  const canAddWatched = selectedPayloads.length > 0 && selectedPayloads.every((movie) => movie.path);
  const candidates = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return [];
    return items
      .filter((movie) => {
        if (selectedKeys.has(movieIdentityKey(moviePayload(movie)))) return false;
        const payload = moviePayload(movie);
        return `${payload.title} ${payload.year} ${movie.filename || ''}`.toLowerCase().includes(query);
      })
      .slice(0, 12);
  }, [items, search, selectedKeys]);

  async function submitCreate(event) {
    event.preventDefault();
    const cleanName = name.trim();
    if (!cleanName) return;
    setBusy(true);
    setError('');
    try {
      const created = await onCreate(cleanName);
      if (onAddBulk && selected.length > 1) await onAddBulk(created.id, selected);
      else for (const movie of selected) await onAdd(created.id, movie);
      setName('');
      onClose();
    } catch (submitError) {
      setError(submitError.message || 'Could not add movies to list');
    } finally {
      setBusy(false);
    }
  }

  async function addExisting(listId) {
    if (!selected.length) return;
    setBusy(true);
    setError('');
    try {
      if (onAddBulk && selected.length > 1) await onAddBulk(listId, selected);
      else await onAdd(listId, selected[0]);
      onClose();
    } catch (addError) {
      setError(addError.message || 'Could not add movies to list');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <section className="small-dialog" role="dialog" aria-modal="true" aria-label="List editor" onClick={(event) => event.stopPropagation()}>
        <div className="dialog-header">
          <div><p className="screen-kicker">User lists</p><h2>{selected.length > 1 ? 'Add selected movies to list' : item ? 'Add movie to list' : 'Create list'}</h2></div>
          <button type="button" className="inspector-close" onClick={onClose} aria-label="Close list editor"><X size={18} /></button>
        </div>
        <form onSubmit={submitCreate}>
          <label className="dialog-field"><span>New list name</span><input value={name} onChange={(event) => setName(event.target.value)} placeholder="My Best, Marvel Universe..." /></label>
          {selected.length > 0 && <p className="dialog-body-path list-editor-selection-summary">{formatCount(selectedPayloads.length)} selected movie{selectedPayloads.length === 1 ? '' : 's'} will be added.</p>}
          {!item && !bulkItems.length && <>
            <label className="library-search curation-search"><Search size={17} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search local movies to add..." /></label>
            {candidates.length > 0 && <div className="curation-candidates">{candidates.map((movie) => { const payload = moviePayload(movie); return <button type="button" key={movie.path} onClick={() => { setSelected((current) => [...current, movie]); setSearch(''); }}><CirclePlus size={15} />{payload.title}{payload.year ? ` (${payload.year})` : ''}</button>; })}</div>}
            <div className="curation-list">{selected.map((movie) => { const payload = moviePayload(movie); return <div className="curation-row" key={movie.path}><span>{payload.title}{payload.year ? ` (${payload.year})` : ''}</span><button type="button" className="mini-action mini-action-danger" onClick={() => setSelected((current) => current.filter((entry) => entry.path !== movie.path))}><Trash2 size={13} /> Remove</button></div>; })}</div>
          </>}
          {error && <p className="dialog-error list-editor-error"><AlertTriangle size={14} /> {error}</p>}
          <div className="dialog-actions"><button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button><button type="submit" className="btn btn-primary" disabled={busy || !name.trim() || (!item && selected.length === 0)}>{busy ? <Loader2 size={15} className="spin" /> : <CirclePlus size={15} />} Create</button></div>
        </form>
        {selected.length > 0 && lists.length > 0 && <div className="existing-list-picker"><span className="mini-label">Existing lists</span>{lists.filter((list) => canAddWatched || list.system_type !== 'watched').map((list) => <button type="button" key={list.id} onClick={() => addExisting(list.id)} disabled={busy}>{list.name}</button>)}</div>}
      </section>
    </div>
  );
}
