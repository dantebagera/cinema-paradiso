import { Select } from '../../components/ui/FormField.jsx';
// Keep native keyboard navigation while sharing the catalog search menu styling.
export default function SearchModeSelect({ children, className = '', ...props }) {
  return <Select className={`search-mode-select ${className}`} {...props}>{children}</Select>;
}
