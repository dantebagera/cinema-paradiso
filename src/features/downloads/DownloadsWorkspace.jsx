import Button from '../../components/ui/Button.jsx';
import { useState } from 'react';
import TVDownloads from '../tv/TVDownloads.jsx';
export default function DownloadsWorkspace({ tvEnabled = false }) {
  const [tv, setTv] = useState(false);
  return (
    <section className="downloads-workspace" aria-label="Downloads powered by qBittorrent">
      {tvEnabled && <div className="tv-media-switch" role="group" aria-label="Downloads media type"><Button aria-pressed={!tv} onClick={() => setTv(false)}>Movies / qBittorrent</Button><Button aria-pressed={tv} onClick={() => setTv(true)}>TV Shows</Button></div>}
      {tv && <TVDownloads />}
      {!tv && <iframe className="downloads-frame" title="qBittorrent Downloads" src="/qbittorrent/" />}
    </section>
  );
}
