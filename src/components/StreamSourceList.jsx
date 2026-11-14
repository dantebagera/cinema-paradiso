import { Play } from 'lucide-react';
import '../features/iptv/iptvSourceList.css';

export default function StreamSourceList({ items, onChoose, disabled = false }) {
  return <div className="iptv-source-list">
    {items.map(item => <button type="button" key={item.id} disabled={disabled || item.disabled}
      aria-label={item.actionLabel} onClick={() => onChoose(item.value)}>
      <span><strong dir="auto">{item.title}</strong><small dir="auto">{item.detail}</small></span>
      {item.disabled ? <small>Unavailable</small> : <Play size={18} />}
    </button>)}
  </div>;
}
