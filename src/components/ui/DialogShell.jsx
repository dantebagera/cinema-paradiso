// Shell only: no portal, dismissal listener, focus policy or submit handler.
export default function DialogShell({ as: Element = 'section', size = 'regular', title, kicker,
  headerActions, children, footer, className = '', ...props }) {
  return <Element {...props} className={`cp-dialog cp-dialog-${size} ${className}`}>
    {title != null && <DialogHeader><div>{kicker && <p className="screen-kicker">{kicker}</p>}<h2>{title}</h2></div>{headerActions}</DialogHeader>}
    {children}{footer && <DialogActions>{footer}</DialogActions>}
  </Element>;
}

export function DialogHeader({ as: Element = 'div', children, className = '', ...props }) {
  return <Element {...props} className={`dialog-header ${className}`}>{children}</Element>;
}

export function DialogActions({ as: Element = 'div', children, className = '', ...props }) {
  return <Element {...props} className={`dialog-actions ${className}`}>{children}</Element>;
}
