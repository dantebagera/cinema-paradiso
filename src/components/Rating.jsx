import { Star } from 'lucide-react';
import { formatVoteCount } from '../utils/moviePresentation.js';

export default function Rating({ value, votes }) {
  if (!value) return null;
  const voteLabel = formatVoteCount(votes);
  return <span className="rating"><Star size={14} fill="currentColor" />{value}{voteLabel ? ` - ${voteLabel}` : ''}</span>;
}
