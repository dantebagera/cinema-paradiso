import DialogShell, { DialogHeader } from '../../components/ui/DialogShell.jsx';
import SearchField from '../search/SearchField.jsx';
import Pagination from '../../components/Pagination.jsx';
import WorkspaceEmptyState from '../../components/WorkspaceEmptyState.jsx';
import { Input } from '../../components/ui/FormField.jsx';
import Button from '../../components/ui/Button.jsx';
import {
  ArrowDown,
  ArrowUp,
  Check,
  ChevronLeft,
  ChevronRight,
  CirclePlus,
  Film,
  ListPlus,
  Pencil,
  Play,
  Radio,
  Search,
  Trash2,
  Tv,
  X
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { iptvImage } from '../../api/iptv.js';
import { formatCount } from '../../utils/appUtils.js';

const TYPE_OPTIONS = [
  ['all', 'All'],
  ['live', 'Channels'],
  ['movie', 'Movies'],
  ['series', 'Series']
];

function listTitle(item) {
  const name = String(item?.name || item?.title || 'Untitled');
  const year = String(item?.year || '').slice(0, 4);
  return year ? name.replace(new RegExp(`\\s*\\(\\s*${year}\\s*\\)\\s*$`), '').trim() || name : name;
}

function itemCountLabel(value) {
  const count = Number(value || 0);
  return `${formatCount(count)} ${count === 1 ? 'item' : 'items'}`;
}

function TypeIcon({ kind, size = 18 }) {
  const Icon = kind === 'live' ? Radio : kind === 'series' ? Tv : Film;
  return <Icon size={size} />;
}

function ListArtwork({ providerId, item }) {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [item.kind, item.item_id]);
  const source = item.available && item.image_url ? iptvImage(providerId, item.kind, item.item_id) : '';
  return (
    <span className="iptv-list-artwork">
      {source && !failed ? <img src={source} alt="" loading="lazy" onError={() => setFailed(true)} /> : <TypeIcon kind={item.kind} size={22} />}
    </span>
  );
}

export function IPTVListPickerModal({ item, lists, busy, newName, onNewName, onCreate, onToggle, onClose }) {
  if (!item) return null;
  return (
    <div className="iptv-list-picker-backdrop" role="presentation" onClick={onClose}>
      <DialogShell className="iptv-list-picker" role="dialog" aria-modal="true" aria-label={`Add ${listTitle(item)} to IPTV list`} onClick={(event) => event.stopPropagation()}>
        <DialogHeader as="header">
          <div><p className="screen-kicker">IPTV organization</p><h2>Add to list</h2><span dir="auto">{listTitle(item)}</span></div>
          <Button size="icon" type="button"  onClick={onClose} aria-label="Close list picker"><X size={18} /></Button>
        </DialogHeader>
        <form onSubmit={(event) => { event.preventDefault(); onCreate(); }}>
          <Input value={newName} onChange={(event) => onNewName(event.target.value)} placeholder="New list name..." maxLength={80} />
          <Button variant="primary" type="submit"  disabled={!newName.trim() || busy}><CirclePlus size={16} /> Create and add</Button>
        </form>
        <div className="iptv-list-picker-options">
          {lists.map((list) => (
            <button type="button" key={list.list_id} className={list.included ? 'is-included' : ''} disabled={busy} onClick={() => onToggle(list)}>
              <span>{list.included ? <Check size={17} /> : <ListPlus size={17} />}</span>
              <strong>{list.name}</strong>
              <small>{itemCountLabel(list.item_count)}</small>
            </button>
          ))}
          {!lists.length ? <div className="iptv-picker-empty"><ListPlus size={26} /><span>No custom lists yet.</span></div> : null}
        </div>
      </DialogShell>
    </div>
  );
}

export default function IPTVListsWorkspace({
  providerId,
  lists,
  selectedListId,
  catalog,
  loading,
  query,
  kindFilter,
  newListName,
  renameName,
  onSelectList,
  onQuery,
  onKindFilter,
  onNewListName,
  onRenameName,
  onCreate,
  onRename,
  onDelete,
  onRemove,
  onMove,
  onPlay,
  onOpen,
  onPage
}) {
  const selectedList = lists.find((list) => list.list_id === selectedListId) || null;
  const page = catalog.page || 1;
  const pageSize = catalog.page_size || 60;
  const pages = Math.max(1, Math.ceil((catalog.total || 0) / pageSize));
  return (
    <div className="iptv-lists-layout">
      <aside className="iptv-user-list-rail">
        <form onSubmit={(event) => { event.preventDefault(); onCreate(); }}>
          <Input value={newListName} onChange={(event) => onNewListName(event.target.value)} placeholder="New list name..." maxLength={80} />
          <Button size="compact" type="submit"  disabled={!newListName.trim()}><CirclePlus size={14} /> New list</Button>
        </form>
        <div className="iptv-user-list-options">
          {lists.map((list) => (
            <button type="button" key={list.list_id} className={selectedListId === list.list_id ? 'is-active' : ''} onClick={() => onSelectList(list.list_id)}>
              <span>{list.name}</span><small>{formatCount(list.item_count)}</small>
            </button>
          ))}
          {!lists.length ? <div className="iptv-list-rail-empty"><ListPlus size={24} /><span>No custom lists yet.</span></div> : null}
        </div>
      </aside>

      <section className="iptv-list-main">
        {selectedList ? (
          <>
            <header className="iptv-list-management">
              <Input value={renameName} onChange={(event) => onRenameName(event.target.value)} maxLength={80} aria-label="Selected IPTV list name" />
              <Button size="compact" type="button"  onClick={onRename} disabled={!renameName.trim() || renameName.trim() === selectedList.name}><Pencil size={14} /> Rename</Button>
              <Button variant="danger" size="compact" type="button"  onClick={onDelete}><Trash2 size={14} /> Delete</Button>
            </header>
            <div className="iptv-list-toolbar">
              <div className="iptv-segmented" aria-label="IPTV list media type">
                {TYPE_OPTIONS.map(([id, label]) => <button type="button" key={id} className={kindFilter === id ? 'is-active' : ''} onClick={() => onKindFilter(id)}>{label}</button>)}
              </div>
              <SearchField className="iptv-search"><Search size={16} /><Input value={query} onChange={(event) => onQuery(event.target.value)} placeholder="Search selected list..." dir="auto" /></SearchField>
              <span>{itemCountLabel(catalog.total)}</span>
            </div>
            <div className="iptv-list-entries">
              {catalog.items.map((item, index) => {
                const globalIndex = (page - 1) * pageSize + index;
                return (
                  <article key={`${item.kind}-${item.item_id}`} className={!item.available ? 'is-unavailable' : ''}>
                    <button type="button" className="iptv-list-entry-main" onClick={() => onOpen(item)} disabled={!item.available}>
                      <ListArtwork providerId={providerId} item={item} />
                      <span className="iptv-list-entry-type"><TypeIcon kind={item.kind} size={14} />{item.kind === 'live' ? 'Channel' : item.kind === 'series' ? 'Series' : 'Movie'}</span>
                      <div><strong dir="auto">{listTitle(item)}</strong><small>{item.year || item.genre || (item.available ? 'Provider title' : 'Unavailable from provider')}</small></div>
                      {!item.available ? <span className="iptv-unavailable-badge">Unavailable</span> : <ChevronRight size={18} />}
                    </button>
                    <div className="iptv-list-entry-actions">
                      {item.available && item.kind !== 'series' ? <Button type="button" onClick={() => onPlay(item)} aria-label={`Play ${item.name}`} title="Play"><Play size={16} fill="currentColor" /></Button> : null}
                      <Button type="button" onClick={() => onMove(item, -1)} disabled={globalIndex === 0} aria-label={`Move ${item.name} up`} title="Move up"><ArrowUp size={16} /></Button>
                      <Button type="button" onClick={() => onMove(item, 1)} disabled={globalIndex >= catalog.total - 1} aria-label={`Move ${item.name} down`} title="Move down"><ArrowDown size={16} /></Button>
                      <button type="button" className="is-danger" onClick={() => onRemove(item)} aria-label={`Remove ${item.name} from list`} title="Remove from list"><Trash2 size={16} /></button>
                    </div>
                  </article>
                );
              })}
              {!catalog.items.length && !loading ? <WorkspaceEmptyState size="regular" className="iptv-list-empty"><ListPlus size={30} /><strong>This list is empty</strong><span>Add channels, movies, or series from their cards.</span></WorkspaceEmptyState> : null}
              {loading ? <div className="iptv-list-loading">Loading list...</div> : null}
            </div>
            <Pagination page={page} totalPages={pages} onPageChange={onPage} ariaLabel="IPTV list pagination" previousAriaLabel="Previous list page" nextAriaLabel="Next list page" />
          </>
        ) : <WorkspaceEmptyState size="regular" className="iptv-list-empty"><ListPlus size={32} /><strong>Create an IPTV list</strong><span>Your custom organization stays separate from provider categories.</span></WorkspaceEmptyState>}
      </section>
    </div>
  );
}
