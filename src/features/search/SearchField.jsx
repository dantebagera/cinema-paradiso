// Shared movie/TV field shell. Query interpretation stays with the search model.
export default function SearchField({ children, className = '', ...props }) {
  return <label className={`library-search ${className}`} {...props}>{children}</label>;
}
