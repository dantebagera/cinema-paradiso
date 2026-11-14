// Native attributes, validation, value and events remain caller-owned.
export default function FormField({ as: Element = 'label', label, children, error, className = '', ...props }) {
  return <Element {...props} className={`dialog-field ${className}`}>
    {label != null && <span>{label}</span>}{children}
    {error && <span className="dialog-error">{error}</span>}
  </Element>;
}

export function Input({ className = '', ...props }) {
  return <input {...props} className={`cp-input ${className}`} />;
}

export function Select({ className = '', children, ...props }) {
  return <select {...props} className={`cp-select ${className}`}>{children}</select>;
}

export function Textarea({ className = '', ...props }) {
  return <textarea {...props} className={`cp-input ${className}`} />;
}
