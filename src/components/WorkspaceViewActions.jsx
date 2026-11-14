import Button from './ui/Button.jsx';
import { Clapperboard, Folder, Loader2, RefreshCw } from 'lucide-react';

export default function WorkspaceViewActions({ fileView, label, onMediaView, onFileView, onRefresh, refreshLabel, loading = false, children }) {
  return <>
    <div className="segmented-control library-view-switch" role="group" aria-label={label}>
      <button type="button" className={!fileView ? 'segment-active' : ''} aria-pressed={!fileView} onClick={onMediaView}><Clapperboard size={18}/> Media View</button>
      <button type="button" className={fileView ? 'segment-active' : ''} aria-pressed={fileView} onClick={onFileView}><Folder size={18}/> File View</button>
    </div>
    <Button type="button" className="library-rescan-button" onClick={onRefresh} disabled={loading} aria-label={refreshLabel} title={refreshLabel}>
      {loading ? <Loader2 size={19} className="spin"/> : <RefreshCw size={19}/>}
    </Button>
    {children}
  </>;
}
