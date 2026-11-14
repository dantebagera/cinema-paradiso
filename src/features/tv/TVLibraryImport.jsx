import { useEffect, useState } from 'react';
import { fetchJson } from '../../api/client.js';

export default function TVLibraryImport({ onOpenMaintenance, ready = true }) {
  const [pending, setPending] = useState(0);
  useEffect(() => {
    if (!ready) return;
    let active = true;
    fetchJson('/api/tv/maintenance?page_size=1').then((result) => {
      if (active) setPending((result.counts?.unidentified_folders || 0) +
        (result.counts?.unresolved_episode_files || 0) + (result.counts?.conflicts || 0) +
        (result.counts?.scan_errors || 0));
    }).catch(() => {});
    return () => { active = false; };
  }, [ready]);
  return <button type="button" className="tv-library-import-launch" onClick={onOpenMaintenance}>
    Review TV identity in Maintenance{pending ? ` (${pending})` : ''}
  </button>;
}
