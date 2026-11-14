import Button from './ui/Button.jsx';
import FormField, { Input } from './ui/FormField.jsx';
import DialogShell, { DialogHeader, DialogActions } from './ui/DialogShell.jsx';
import { X } from 'lucide-react';
import { cx } from '../utils/appUtils.js';
import { getMovieIdentity } from '../utils/libraryUtils.js';

export function LibraryStat({ icon: Icon, label, value, tone, onClick }) {
  const content = <><Icon size={18} /><strong>{value}</strong><span>{label}</span></>;
  if (onClick) return <button type="button" className={cx('library-stat', 'library-stat-action', `tone-${tone}`)} onClick={onClick}>{content}</button>;
  return <article className={cx('library-stat', `tone-${tone}`)}>{content}</article>;
}

export function LibraryRenameModal({ item, onClose, onSubmit }) {
  const identity = getMovieIdentity(item);
  return <div className="modal-backdrop" role="presentation" onClick={onClose}>
    <DialogShell as="form" className="small-dialog" onSubmit={onSubmit} role="dialog" aria-modal="true" aria-label="Rename file" onClick={(event) => event.stopPropagation()}>
      <DialogHeader ><div><p className="screen-kicker">Rename file</p><h2>{item.filename}</h2></div><Button size="icon" type="button" className="inspector-close" onClick={onClose} aria-label="Close rename dialog"><X size={18} /></Button></DialogHeader>
      <FormField ><span>Movie title</span><Input name="title" defaultValue={identity.title} /></FormField>
      <FormField ><span>Year</span><Input name="year" defaultValue={identity.year} inputMode="numeric" /></FormField>
      <DialogActions ><Button type="button"  onClick={onClose}>Cancel</Button><Button variant="primary" type="submit" >Rename</Button></DialogActions>
    </DialogShell>
  </div>;
}

export function ConfirmDialog({
  title,
  body,
  confirmLabel,
  danger,
  acknowledgementLabel = '',
  acknowledged = false,
  onAcknowledgementChange,
  onCancel,
  onConfirm,
}) {
  return <div className="modal-backdrop" role="presentation" onClick={onCancel}>
    <DialogShell className="small-dialog" role="dialog" aria-modal="true" aria-label={title} onClick={(event) => event.stopPropagation()}>
      <DialogHeader ><div><p className="screen-kicker">Confirm action</p><h2>{title}</h2></div><Button size="icon" type="button" className="inspector-close" onClick={onCancel} aria-label="Close dialog"><X size={18} /></Button></DialogHeader>
      <p className="dialog-body-path">{body}</p>
      {acknowledgementLabel && (
        <label className="dialog-confirmation-check">
          <input type="checkbox" checked={acknowledged} onChange={(event) => onAcknowledgementChange?.(event.target.checked)} />
          <span>{acknowledgementLabel}</span>
        </label>
      )}
      <DialogActions ><Button type="button"  onClick={onCancel}>Cancel</Button><Button variant={danger ? 'danger' : 'primary'} type="button"  disabled={Boolean(acknowledgementLabel) && !acknowledged} onClick={onConfirm}>{confirmLabel}</Button></DialogActions>
    </DialogShell>
  </div>;
}
