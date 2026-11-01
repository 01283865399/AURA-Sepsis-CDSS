import { ListOrdered } from 'lucide-react';
import ConfidenceBar from './ConfidenceBar';
import { useLocale } from '../../hooks/useLocale';

export default function TopKPredictions({ predictions = [] }) {
  const { text } = useLocale();
  if (!predictions.length) return null;
  return (
    <section className="topk-list" aria-labelledby="topk-heading">
      <h3 id="topk-heading"><ListOrdered size={17} /> {text('أعلى النتائج', 'Top predictions')}</h3>
      {predictions.map((prediction, index) => (
        <ConfidenceBar key={`${prediction.condition}-${index}`} prediction={prediction} index={index} />
      ))}
    </section>
  );
}
