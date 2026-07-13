import { Check } from 'lucide-react';
import { cx } from '../utils/appUtils.js';

export default function SelectionCheckbox({ checked, onChange, label, className }) {
  return (
    <label className={cx('selection-checkbox', className, checked && 'selection-checkbox-checked')} onClick={(event) => event.stopPropagation()}>
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} aria-label={label} />
      <span aria-hidden="true">{checked ? <Check size={14} /> : null}</span>
    </label>
  );
}
