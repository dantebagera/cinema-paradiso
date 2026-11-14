import Button from '../../components/ui/Button.jsx';
import DialogShell from '../../components/ui/DialogShell.jsx';
import { fetchJson } from '../../api/client.js';

export default function TVPosterEditor({ series, onClose, onSaved, notify }) {
  async function save(event) {
    event.preventDefault();
    try {
      await fetchJson(`/api/tv/series/${series.id}/poster`, { method: 'POST', body: new FormData(event.currentTarget) });
      onSaved(); onClose();
    } catch (error) { notify(error.message, 'error'); }
  }
  async function reset() {
    try {
      await fetchJson(`/api/tv/series/${series.id}/poster`, { method: 'DELETE' });
      onSaved(); onClose();
    } catch (error) { notify(error.message, 'error'); }
  }
  return <div className="modal-backdrop" onClick={onClose}><DialogShell as="form" size="poster" className="tv-poster-editor" role="dialog" aria-modal="true" aria-label={`Edit poster for ${series.title}`} onSubmit={save} onClick={event => event.stopPropagation()}>
    <h3>Edit {series.title} poster</h3><p>Choose a JPEG, PNG or WebP image under 5 MB. The provider poster remains available for reset.</p>
    <input type="file" name="image" accept="image/jpeg,image/png,image/webp" required />
    <div className="tv-actions"><Button type="submit">Save poster</Button>{series.poster_override && <Button type="button" onClick={reset}>Reset to provider poster</Button>}<Button type="button" onClick={onClose}>Cancel</Button></div>
  </DialogShell></div>;
}
