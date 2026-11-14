import { Loader2, MonitorPlay } from 'lucide-react';

const variants = {
  primary: 'btn-primary', secondary: 'btn-secondary', play: 'btn-primary btn-green',
  stream: 'btn-secondary btn-green-outline', danger: 'btn-danger', upgrade: 'btn-upgrade',
  ai: 'btn-primary btn-violet', source: 'mini-action-source'
};

// Presentation only. Callers retain submission, pending guards and disabled policy.
export default function Button({ as: Element = 'button', variant = 'secondary', size = 'regular', icon: Icon, iconSize = 15,
  loading = false, label, children, className = '', ...props }) {
  const compact = size === 'compact';
  const tone = compact && variant === 'secondary' ? ''
    : compact && variant === 'danger' ? 'mini-action-danger' : variants[variant];
  return <Element {...props} className={[
    'cp-button', compact ? 'mini-action' : size === 'icon' ? 'icon-button' : 'btn', size !== 'icon' && tone,
    size === 'icon' && 'cp-button-icon', className
  ].filter(Boolean).join(' ')}>
    {loading ? <Loader2 size={iconSize} className="spin" /> : Icon ? <Icon size={iconSize} /> : null}
    {children ?? label}
  </Element>;
}

// Navigation keeps native anchor semantics while sharing action presentation.
export function ActionLink(props) { return <Button {...props} as="a" />; }

export function StreamButton({ children, label = 'Stream', ...props }) {
  return <Button {...props} variant="stream" icon={MonitorPlay}>{children ?? label}</Button>;
}
