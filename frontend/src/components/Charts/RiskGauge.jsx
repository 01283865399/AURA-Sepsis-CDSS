import { formatPercent } from '../../utils/formatters';
import { useLocale } from '../../hooks/useLocale';

export default function RiskGauge({ value = 0, label }) {
  const { text } = useLocale();
  const percent = Math.max(0, Math.min(100, Number(value) * 100));
  return (
    <div className="risk-gauge" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(percent)} aria-label={`${label}: ${formatPercent(value)}`}>
      <div className="risk-gauge-ring" style={{ '--gauge-value': `${percent * 3.6}deg` }}><span>{formatPercent(value, 0)}</span></div>
      <small>{label || text('درجة النموذج غير المعايرة', 'Uncalibrated model score')}</small>
    </div>
  );
}
