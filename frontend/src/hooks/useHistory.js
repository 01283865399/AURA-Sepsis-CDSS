import { useMemo } from 'react';
import { usePredictionStore } from '../store/predictionStore';

export function useHistory(search = '') {
  const history = usePredictionStore((state) => state.history);
  const normalizedSearch = search.trim().toLocaleLowerCase();
  return useMemo(() => history.filter((record) => {
    const content = `${record.modelId} ${record.modelName} ${record.detail || ''}`.toLocaleLowerCase();
    return content.includes(normalizedSearch);
  }), [history, normalizedSearch]);
}
