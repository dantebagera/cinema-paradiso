import DialogShell, { DialogActions } from './ui/DialogShell.jsx';
import FormField, { Input } from './ui/FormField.jsx';
import Button from './ui/Button.jsx';
import { useCallback, useEffect, useId, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Bell, Bookmark, Check, ChevronDown, MoreHorizontal, Pencil, Plus, Search, Trash2 } from 'lucide-react';
import AnchoredPopover from './AnchoredPopover.jsx';
import SearchField from '../features/search/SearchField.jsx';
import useDismissiblePopover from '../hooks/useDismissiblePopover.js';
import { formatCount } from '../utils/appUtils.js';

const systemIcons = { watched: Check, watchlist: Bookmark, following: Bell };

// Feature owners supply list identities and mutations; this toolbar shares presentation only.
export default function ListsToolbar({ lists, selectedList, noun = 'movies', onSelect, onCreate, onRename, onDelete, onAdd, addLabel = 'Add movie' }) {
  const [pickerOpen, setPickerOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [editor, setEditor] = useState(null);
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const pickerRef = useRef(null);
  const menuRef = useRef(null);
  const dialogRef = useRef(null);
  const restoreFocusRef = useRef(null);
  const id = useId();
  const closePicker = useCallback(() => setPickerOpen(false), []);
  const closeMenu = useCallback(() => setMenuOpen(false), []);
  const closeEditor = useCallback(() => setEditor(null), []);
  useDismissiblePopover(Boolean(editor), closeEditor, pickerRef, dialogRef, undefined,
    { dismissOutside: false, dismissEscape: false, workspaceOnly: true });
  const isSystem = Boolean(selectedList?.system_type || selectedList?.system);
  const Icon = systemIcons[selectedList?.system_type || selectedList?.id] || Bookmark;

  useEffect(() => {
    if (!editor) return undefined;
    const dialog = dialogRef.current;
    dialog.showModal();
    return () => {
      dialog.close();
      if (restoreFocusRef.current?.getClientRects().length) restoreFocusRef.current.focus({ preventScroll: true });
    };
  }, [editor]);

  function openEditor(kind) {
    restoreFocusRef.current = kind === 'new' ? document.activeElement : menuRef.current;
    setMenuOpen(false);
    setPickerOpen(false);
    setName(kind === 'new' ? '' : selectedList.name);
    setError('');
    setEditor(kind);
  }
  async function save(event) {
    event.preventDefault();
    if (!name.trim() || busy) return;
    setBusy(true); setError('');
    try {
      await (editor === 'new' ? onCreate(name.trim()) : onRename(name.trim()));
      setEditor(null);
    } catch (cause) { setError(cause.message || 'Could not save the list.'); }
    finally { setBusy(false); }
  }
  async function remove() {
    setMenuOpen(false); setError('');
    try { await onDelete(); }
    catch (cause) { setError(cause.message || 'Could not delete the list.'); }
  }
  const matches = lists.filter(list => list.name.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()));

  return <>
    <div className="lists-toolbar">
      <div className="lists-toolbar-context">
        <Button ref={pickerRef} type="button" className="lists-picker-trigger" aria-label={`Choose ${noun} list: ${selectedList?.name || 'No list selected'}`} aria-expanded={pickerOpen} aria-controls={`${id}-picker`} onClick={() => { setMenuOpen(false); setQuery(''); setPickerOpen(value => !value); }}>
          <Icon size={18} /><span>{selectedList?.name || 'Choose a list'}</span><ChevronDown size={16}/>
        </Button>
        {selectedList && <span className="lists-toolbar-count">{formatCount(selectedList.count ?? selectedList.movies?.length ?? 0)} {noun}</span>}
      </div>
      <div className="lists-toolbar-actions">
        {onAdd && <Button variant="primary" type="button"  onClick={onAdd} disabled={!selectedList}><Plus size={16}/>{addLabel}</Button>}
        <Button type="button"  onClick={() => openEditor('new')}><Plus size={16}/>New list</Button>
        <Button ref={menuRef} type="button" className="lists-actions-trigger" aria-label="List actions" aria-expanded={menuOpen} aria-controls={`${id}-actions`} disabled={!selectedList || isSystem} onClick={() => { setPickerOpen(false); setMenuOpen(value => !value); }}><MoreHorizontal size={18}/></Button>
      </div>
    </div>
    <AnchoredPopover open={pickerOpen} anchorRef={pickerRef} triggerRef={pickerRef} onClose={closePicker} maxWidth={340} id={`${id}-picker`} className="lists-popover" role="region" aria-label={`${noun === 'movies' ? 'Movie' : 'TV'} lists`}>
      <SearchField onClear={query ? () => setQuery('') : undefined}><Search size={16}/><Input aria-label="Find a list" value={query} onChange={event => setQuery(event.target.value)} placeholder="Find a list…"/></SearchField>
      <div className="lists-picker-options">
        {[true, false].map(system => {
          const group = matches.filter(list => Boolean(list.system_type || list.system) === system);
          return group.length > 0 && <div key={String(system)}><p className="mini-label">{system ? 'Smart lists' : 'Your lists'}</p>{group.map(list => {
            const ListIcon = systemIcons[list.system_type || list.id] || Bookmark;
            return <button key={list.id} type="button" className={`lists-picker-option${selectedList?.id === list.id ? ' lists-picker-option-active' : ''}`} aria-pressed={selectedList?.id === list.id} onClick={() => { onSelect(list.id); closePicker(); pickerRef.current?.focus(); }}>
              <span><ListIcon size={16}/><span>{list.name}</span></span><small>{formatCount(list.count ?? list.movies?.length ?? 0)} {noun}</small>
            </button>;
          })}</div>;
        })}
        {!matches.length && <p className="lists-picker-empty">{lists.length ? 'No lists match your search.' : 'Create a list to get started.'}</p>}
      </div>
    </AnchoredPopover>
    <AnchoredPopover open={menuOpen} anchorRef={menuRef} triggerRef={menuRef} onClose={closeMenu} maxWidth={200} id={`${id}-actions`} className="lists-popover lists-actions-menu" role="region" aria-label="List management">
      <button type="button" className="lists-picker-option" onClick={() => openEditor('rename')}><Pencil size={15}/>Rename list</button>
      <button type="button" className="lists-picker-option mini-action-danger" onClick={remove}><Trash2 size={15}/>Delete list</button>
    </AnchoredPopover>
    {error && !editor && <p className="library-status library-status-error" role="alert">{error}</p>}
    {editor && createPortal(<DialogShell as="dialog" ref={dialogRef} className="small-dialog lists-name-dialog" aria-label={editor === 'new' ? 'New list' : 'Rename list'} onCancel={event => { if (busy) event.preventDefault(); else setEditor(null); }}>
      <form onSubmit={save}>
        <h2>{editor === 'new' ? 'New list' : 'Rename list'}</h2>
        <FormField ><span>List name</span><Input autoFocus aria-label={editor === 'new' ? `New ${noun === 'movies' ? 'movie' : 'TV'} list name` : `Selected ${noun === 'movies' ? '' : 'TV '}list name`} value={name} onChange={event => setName(event.target.value)} disabled={busy} required/></FormField>
        {error && <p role="alert" className="library-status-error">{error}</p>}
        <DialogActions><Button type="button"  disabled={busy} onClick={() => setEditor(null)}>Cancel</Button><Button variant="primary" type="submit"  disabled={busy || !name.trim()}>{busy ? 'Saving…' : editor === 'new' ? 'Create list' : 'Rename list'}</Button></DialogActions>
      </form>
    </DialogShell>, document.body)}
  </>;
}
