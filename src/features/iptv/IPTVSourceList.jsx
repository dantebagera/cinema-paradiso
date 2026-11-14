import StreamSourceList from '../../components/StreamSourceList.jsx';

export default function IPTVSourceList({ sources, onChoose, disabled = false }) {
  return <StreamSourceList disabled={disabled} onChoose={onChoose} items={sources.map(source => ({
    id: source.source_key, value: source, disabled: !source.available,
    title: source.playlist_name || source.name,
    detail: [source.quality_claim ? `${source.quality_claim} provider claim` : '',
      source.dubbed_claim ? 'Dubbed claim' : '', source.subtitled_claim ? 'Subtitle claim' : ''].filter(Boolean).join(' · ') || 'Provider source',
  }))} />;
}
