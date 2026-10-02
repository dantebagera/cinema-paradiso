import { useEffect, useState } from 'react';
import { Bell } from 'lucide-react';
import { fetchJson } from '../../api/client.js';

export default function NotificationWindow({ collapsed = false }) {
  const [open, setOpen] = useState(false);
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
    <button type="button" className="notification-bell" aria-label={`Notifications, ${data.unread} unread`} aria-expanded={open} onClick={() => setOpen(value => !value)}><Bell size={20}/>{!collapsed && <span>Notifications</span>}{data.unread > 0 && <strong>{data.unread}</strong>}</button>
    {open && <section className="notification-panel" aria-label="Notifications"><header><h2>Notifications</h2><button type="button" onClick={() => setOpen(false)}>Close</button></header>
      <label>Search history <input value={query} onChange={event => { setQuery(event.target.value); setPage(1); }} placeholder="Task, show or episode" /></label>
      {error && <p role="alert">{error}</p>}
      <p>{data.total} events · {data.unread} unread</p>
      <div className="notification-events">{groups.map(group => <section key={group.key} aria-label={group.label}><h3>{group.label}</h3>{group.items.map(item => <article key={item.id} className={item.read_at ? '' : 'notification-unread'}>
        <span>{item.severity} · {new Date(item.created_at * 1000).toLocaleString()}</span>
        <strong>{item.title}</strong><p>{item.body}</p>
        <div><a href={item.link}>Open</a>{!item.read_at && <button type="button" onClick={() => markRead([item.id])}>Mark read</button>}</div>
      </article>)}</section>)}{!data.items.length && <p>No notifications found.</p>}</div>
      <footer><button type="button" disabled={page <= 1} onClick={() => setPage(value => value - 1)}>Previous</button><span>Page {page} of {data.total_pages}</span><button type="button" disabled={page >= data.total_pages} onClick={() => setPage(value => value + 1)}>Next</button></footer>
    </section>}
  </div>;
}
