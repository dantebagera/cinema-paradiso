export default function AcquisitionDecisionDetails({ review }) {
  if (!review) return null;
  return <details className="acquisition-review"><summary>Review releases ({review.decisions?.length || 0})</summary>
    {review.mode === 'shadow' && <p>Policy preview · current movie selection remains authoritative.</p>}
    <table><thead><tr><th>Release</th><th>Result</th><th>Claim / confidence</th><th>Score</th><th>Reasons</th></tr></thead>
      <tbody>{(review.decisions || []).map((decision) => <tr key={decision.decision_token}>
        <td>{decision.candidate.title}<br /><small>{decision.candidate.indexer}</small></td>
        <td>{decision.accepted ? 'Accepted' : 'Rejected'} · {decision.eligibility.replaceAll('_', ' ')}</td>
        <td>{decision.claim.source} / {decision.claim.resolution}<br />{decision.source_confidence.replaceAll('_', ' ')}</td>
        <td>{decision.quality_score} quality · {decision.format_score} formats</td>
        <td>{[...(decision.reasons || []), ...(decision.warnings || [])].map((reason) => <p key={reason.code}>{reason.message}</p>)}</td>
      </tr>)}</tbody></table>
  </details>;
}
