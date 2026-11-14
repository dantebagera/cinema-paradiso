import { MonitorPlay } from 'lucide-react';

export default function IPTVAvailabilityBadge({ movie, providers = [], onStream }) {
  const matches = providers.filter(provider => provider.state === 'ready' && provider.matches?.[String(movie.tmdb_id)]);
  return (
    <div className="movie-iptv-availability" aria-label="Saved IPTV availability">
      {matches.slice(0, 2).map(provider => (
        <button key={provider.provider_id} type="button" className="unified-availability-badge"
          title={`Listed in ${provider.name}'s last synced catalog`} aria-label={`Stream from ${provider.name}`}
          onClick={event => { event.stopPropagation(); onStream(movie, provider.provider_id); }}>
          <MonitorPlay size={13} /><span dir="auto">{provider.name}</span>
        </button>
      ))}
      {matches.length > 2 && <button type="button" className="unified-availability-badge"
        aria-label={`Show all ${matches.length} IPTV providers`}
        onClick={event => { event.stopPropagation(); onStream(movie); }}>+{matches.length - 2}</button>}
    </div>
  );
}
