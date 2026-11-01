import { formatPercent } from '../../utils/formatters';

export default function ConfidenceBar({ prediction, index = 0 }) {
  const probability = Math.max(0, Math.min(1, Number(prediction.probability || 0)));
  return (
    <div className="confidence-row">
      <div className="confidence-copy"><span>{prediction.condition}</span><strong>{formatPercent(probability)}</strong></div>
      <div className="confidence-track" role="meter" aria-label={`${prediction.condition}: ${formatPercent(probability)}`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(probability * 100)}>
        <span className={`confidence-fill confidence-fill-${index % 4}`} style={{ width: `${probability * 100}%` }} />
      </div>
    </div>
  );
}
