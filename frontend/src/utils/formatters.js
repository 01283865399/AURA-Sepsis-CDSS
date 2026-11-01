export function formatDate(value, locale = 'ar') {
  return new Intl.DateTimeFormat(locale === 'ar' ? 'ar-EG' : 'en', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value));
}

export function formatPercent(value, digits = 1) {
  return `${(Number(value || 0) * 100).toFixed(digits)}%`;
}

export function getDisplayPredictions(result) {
  if (Array.isArray(result?.predictions)) return result.predictions;
  if (Number.isFinite(result?.sepsis_probability)) {
    return [{
      condition: result.risk_level || 'Sepsis model score',
      probability: result.sepsis_probability,
    }];
  }
  if (result?.target_scores && typeof result.target_scores === 'object') {
    return Object.entries(result.target_scores)
      .map(([condition, score]) => ({ condition, probability: Number(score) / 100 }))
      .sort((left, right) => right.probability - left.probability);
  }
  return [];
}
