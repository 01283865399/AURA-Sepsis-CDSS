import { ShieldAlert } from 'lucide-react';
import { useTranslation } from 'react-i18next';

export default function Disclaimer({ compact = false }) {
  const { t } = useTranslation();
  return (
    <aside className={`disclaimer ${compact ? 'disclaimer-compact' : ''}`} role="note">
      <ShieldAlert aria-hidden="true" size={18} />
      <div><strong>{t('disclaimerTitle')}</strong><p>{t('disclaimer')}</p></div>
    </aside>
  );
}
