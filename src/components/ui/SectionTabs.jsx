// Existing callers retain roles, keyboard behavior, history and selected state.
export default function SectionTabs({ as: Element = 'div', children, className = '', ...props }) {
  return <Element {...props} className={`discover-tabs media-section-tabs cp-section-tabs ${className}`}>{children}</Element>;
}

export function SectionTab({ active = false, className = '', children, ...props }) {
  return <button {...props} className={`cp-section-tab ${active ? 'discover-tab-active' : ''} ${className}`}>{children}</button>;
}
