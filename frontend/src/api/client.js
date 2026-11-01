import axios from 'axios';

const createApiClient = (baseURL, timeout = 30000) => {
  const client = axios.create({ baseURL, timeout });
  client.interceptors.request.use((config) => {
    const token = window.localStorage.getItem('aura_access_token');
    if (token) config.headers.Authorization = `Bearer ${token}`;
    return config;
  });
  return client;
};

export const modelApi = createApiClient(
  import.meta.env.VITE_MODEL_API_URL || 'http://127.0.0.1:8001',
);
export const clinicalApi = createApiClient(
  import.meta.env.VITE_CLINICAL_API_URL || 'http://127.0.0.1:8000',
  60000,
);

export async function authenticate(path, credentials) {
  const response = await clinicalApi.post(path, credentials);
  localStorage.setItem('aura_access_token', response.data.access_token);
  localStorage.setItem('aura_user', JSON.stringify({
    username: response.data.username,
    role: response.data.role,
  }));
  return response.data;
}

export async function sendGeminiChat(messages, options = {}) {
  return (await clinicalApi.post('/api/ai/chat', {
    messages,
    tool_results: options.toolResults || [],
    patient_id: options.patientId || null,
    patient_context_consent: Boolean(options.patientContextConsent),
  }, { timeout: 60000 })).data;
}

export function getApiError(error) {
  const detail = error?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg || item.message).filter(Boolean).join('، ');
  }
  if (error?.code === 'ECONNABORTED') return 'انتهت مهلة الاتصال. تحقق من تشغيل الخدمة ثم أعد المحاولة.';
  if (!error?.response) return 'تعذر الاتصال بالخدمة. تحقق من عنوان API وتشغيل الخادم.';
  return 'تعذر إكمال الطلب. راجع المدخلات وحالة الخدمة.';
}
