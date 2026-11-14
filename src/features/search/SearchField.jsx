import { useRef } from 'react';
import { X } from 'lucide-react';

// Shared movie/TV field shell. Query interpretation stays with the search model.
export default function SearchField({ children, className = '', onClear, clearLabel = 'Clear search', ...props }) {
  const fieldRef = useRef(null);
  return <label ref={fieldRef} className={`library-search ${onClear ? 'library-search-with-clear' : ''} ${className}`} {...props}>
    {children}
    {onClear && <button type="button" className="search-clear-button" aria-label={clearLabel} title="Clear search" onClick={() => {
      onClear();
      fieldRef.current?.querySelector('input')?.focus();
    }}><X size={17} /></button>}
  </label>;
}
