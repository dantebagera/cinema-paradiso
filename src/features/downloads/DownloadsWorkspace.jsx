import { useState } from 'react';
import TVDownloads from '../tv/TVDownloads.jsx';
export default function DownloadsWorkspace({ tvEnabled = false }) {
  const [tv, setTv] = useState(false);
  return (
    <section className="downloads-workspace" aria-label="Downloads powered by qBittorrent">
      {tvEnabled && <div className="tv-media-switch" role="group" aria-label="Downloads media type"><button aria-pressed={!tv} onClick={() => setTv(false)}>Movies / qBittorrent</button><button aria-pressed={tv} onClick={() => setTv(true)}>TV Shows</button></div>}
      {tv && <TVDownloads />}
      {!tv && <iframe className="downloads-frame" title="qBittorrent Downloads" src="/qbittorrent/" />}
    </section>
  );
}
