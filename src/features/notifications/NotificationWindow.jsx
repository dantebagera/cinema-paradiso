import WorkspaceEmptyState from '../../components/WorkspaceEmptyState.jsx';
import Pagination from '../../components/Pagination.jsx';
import { ActionLink } from '../../components/ui/Button.jsx';
import Button from '../../components/ui/Button.jsx';
import { Input } from '../../components/ui/FormField.jsx';
import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Bell, Search } from 'lucide-react';
import { fetchJson } from '../../api/client.js';
import useDismissiblePopover from '../../hooks/useDismissiblePopover.js';

export default function NotificationWindow({ collapsed = false, open = false, onToggle, onDismiss, portalTarget, onMouseEnter, onMouseLeave, onFocus, onBlur }) {
  const triggerRef = useRef(null);
  const panelRef = useRef(null);
  useDismissiblePopover(open, onDismiss, triggerRef, panelRef);
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(1);
  const [data, setData] = useState({ items: [], unread: 0, total: 0, total_pages: 1 });
  const [error, setError] = useState('');
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    let alive = true;
    const load = () => fetchJson(`/api/notifications?query=${encodeURIComponent(open ? query : '')}&page=${open ? page : 1}`)
      .then(result => { if (alive) { setData(result); setError(''); } })
      .catch(cause => { if (alive && open) setError(cause.message); });
    load();
    const timer = window.setInterval(load, 30000);
    return () => { alive = false; window.clearInterval(timer); };
  }, [open, query, page, revision]);
  async function markRead(ids) {
    try {
      await fetchJson('/api/notifications/read', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ids }) });
      setRevision(value => value + 1);
    } catch (cause) { setError(cause.message); }
  }
  const groups = Object.values(data.items.reduce((index, item) => {
    const key = `${item.media_type}:${item.source}:${item.task_id || item.id}:${item.episode_key || ''}`;
    (index[key] ||= { key, label: `${item.media_type.toUpperCase()} · ${item.source}${item.task_id ? ` · Task ${item.task_id.slice(0, 8)}` : ''}${item.episode_key ? ` · ${item.episode_key}` : ''}`, items: [] }).items.push(item);
    return index;
  }, {}));
  return <div className="notification-window">
    <button ref={triggerRef} type="button" className="nav-item notification-bell" aria-label={`Notifications, ${data.unread} unread`} aria-expanded={open} aria-controls="notification-panel" onMouseEnter={onMouseEnter} onMouseLeave={onMouseLeave} onFocus={onFocus} onBlur={onBlur} onClick={onToggle}><span className="nav-icon-wrap"><Bell size={22}/></span><span className="nav-label">Notifications</span>{data.unread > 0 && <strong className="notification-count">{data.unread}</strong>}</button>
    {open && createPortal(<section ref={panelRef} id="notification-panel" className={`notification-panel${collapsed ? ' notification-panel-collapsed' : ''}`} aria-label="Notifications"><header><h2><Bell size={18}/> Notifications</h2><span>{data.unread} unread</span></header>
      <label className="notification-search">Search history <span><Search size={16} aria-hidden="true"/><Input value={query} onChange={event => { setQuery(event.target.value); setPage(1); }} placeholder="Task, show or episode" /></span></label>
      {error && <p className="notification-error" role="alert">{error}</p>}
      <p className="notification-summary">{data.total} events</p>
      <div className="notification-events">{groups.map(group => <section key={group.key} aria-label={group.label}><h3>{group.label}</h3>{group.items.map(item => <article key={item.id} className={item.read_at ? '' : 'notification-unread'}>
        <span>{item.severity} · {new Date(item.created_at * 1000).toLocaleString()}</span>
        <strong>{item.title}</strong><p>{item.body}</p>
        <div><ActionLink size="compact"  href={item.link} onClick={onDismiss}>Open</ActionLink>{!item.read_at && <Button size="compact" type="button" onClick={() => markRead([item.id])}>Mark read</Button>}</div>
      </article>)}</section>)}{!data.items.length && <WorkspaceEmptyState size="compact" className="notification-empty"><Bell size={24} aria-hidden="true"/><strong>{query ? 'No matching notifications' : 'No notifications yet'}</strong><p>{query ? 'Try a different task, show or episode.' : 'Updates from your tasks and downloads will appear here.'}</p></WorkspaceEmptyState>}</div>
      <footer><Pagination page={page} totalPages={Math.max(1, data.total_pages)} showSinglePage onPageChange={setPage} ariaLabel="Notifications pagination" /></footer>
    </section>, portalTarget || document.body)}
  </div>;
}
