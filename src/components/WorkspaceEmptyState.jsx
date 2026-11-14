export default function WorkspaceEmptyState({ as: Element = 'div', title, description, children, actions, className = '', size = 'regular', icon: Icon, ...props }) {
  return (
    <Element {...props} className={`empty-state ${size === 'compact' ? 'cp-empty-compact' : 'workspace-empty-state'} ${className}`}>
      {Icon && <Icon size={30} />}
      {title != null && <strong>{title}</strong>}
      {description != null && <span>{description}</span>}
      {title != null && children ? <div className="workspace-empty-actions">{children}</div> : children}
      {actions && <div className="workspace-empty-actions">{actions}</div>}
    </Element>
  );
}
