import { useMutation } from '@tanstack/react-query';
import { clinicalApi, getApiError, modelApi } from '../api/client';
import { getDisplayPredictions } from '../utils/formatters';
import { usePredictionStore } from '../store/predictionStore';

const cleanPayload = (values) => Object.fromEntries(
  Object.entries(values).filter(([, value]) => value !== '' && value != null)
    .map(([key, value]) => [key, typeof value === 'string' && value.trim() !== '' && Number.isFinite(Number(value)) ? Number(value) : value]),
);

export async function submitModulePrediction({ module, values, file }) {
  if (!module?.available || !module.endpoint) throw new Error('هذا المسار غير متاح في API الحالية.');
  if (module.transport === 'image-form') {
    const form = new FormData();
    form.append('image', file);
    form.append('top_k', String(Math.min(5, module.maxTopK || 5)));
    return (await modelApi.post(module.endpoint, form)).data;
  }
  if (module.transport === 'raw-image') {
    return (await clinicalApi.post(module.endpoint, file, {
      headers: { 'Content-Type': file.type || 'application/octet-stream' },
    })).data;
  }

  let payload;
  if (module.id === 'symptoms') {
    payload = {
      symptoms: values.symptoms.split(/[\n,،;]+/).map((item) => item.trim()).filter(Boolean),
      top_k: 5,
    };
  } else if (module.id === 'ddxplus') {
    payload = {
      age: Number(values.age),
      sex: values.sex,
      evidences: values.evidences.split(/[\n,،;]+/).map((item) => item.trim()).filter(Boolean),
      top_k: 5,
    };
  } else {
    payload = cleanPayload(values);
    if (module.maxTopK) payload.top_k = Math.min(5, module.maxTopK);
  }
  const client = module.api === 'clinical' ? clinicalApi : modelApi;
  return (await client.post(module.endpoint, payload)).data;
}

export function usePrediction() {
  const addRecord = usePredictionStore((state) => state.addRecord);
  return useMutation({
    mutationFn: submitModulePrediction,
    retry: false,
    onSuccess: (result, request) => {
      const predictions = getDisplayPredictions(result);
      const top = predictions[0];
      addRecord({
        id: globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`,
        modelId: request.module.id,
        createdAt: new Date().toISOString(),
        modelName: result.model_name || result.modelName || request.module.title,
        predictions: predictions.slice(0, 5),
        researchOnly: true,
        detail: result.findings || result.risk_level || top?.condition || '',
      });
    },
    onError: (error) => {
      error.userMessage = getApiError(error);
    },
  });
}
