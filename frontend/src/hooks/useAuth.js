import { useTranslation } from 'react-i18next';

export function useAuth() {
  const { i18n } = useTranslation();
  const token = localStorage.getItem('aura_access_token');
  const user = JSON.parse(localStorage.getItem('aura_user') || 'null');
  return {
    isAuthenticated: Boolean(token),
    authConfigured: true,
    user,
    message: i18n.language === 'en'
      ? 'Backend JWT authentication is enabled for research accounts.'
      : 'مصادقة JWT مفعلة لحسابات البحث.',
  };
}
