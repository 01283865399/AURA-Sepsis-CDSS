import { Activity, Bell, Globe2, Menu, Moon, Sun } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useApiHealth } from '../../hooks/useApiHealth';
import { useUiStore } from '../../store/uiStore';

export default function Navbar() {
  const { t, i18n } = useTranslation();
  const health = useApiHealth();
  const theme = useUiStore((state) => state.theme);
  const language = useUiStore((state) => state.language);
  const toggleTheme = useUiStore((state) => state.toggleTheme);
  const setLanguage = useUiStore((state) => state.setLanguage);
  const setSidebarOpen = useUiStore((state) => state.setSidebarOpen);
  const online = health.isSuccess;

  const changeLanguage = () => {
    const nextLanguage = language === 'ar' ? 'en' : 'ar';
    setLanguage(nextLanguage);
    void i18n.changeLanguage(nextLanguage);
  };

  return (
    <header className="topbar">
      <button className="icon-button mobile-menu" type="button" onClick={() => setSidebarOpen(true)} aria-label="فتح القائمة"><Menu size={19} /></button>
      <div className="topbar-heading"><span className="topbar-mark"><Activity size={18} /></span><div><strong>{t('brand')}</strong><small>Research workspace</small></div></div>
      <div className="topbar-actions">
        <span className={`connection-pill ${online ? 'is-online' : 'is-offline'}`} title={online ? 'API /health' : 'Model API unavailable'}><i />{health.isPending ? t('connecting') : online ? t('online') : t('offline')}</span>
        <button className="icon-button" type="button" onClick={changeLanguage} aria-label={t('language')} title={t('language')}><Globe2 size={17} /><span className="language-label">{language === 'ar' ? 'EN' : 'ع'}</span></button>
        <button className="icon-button" type="button" onClick={toggleTheme} aria-label={theme === 'light' ? 'تفعيل الوضع الداكن' : 'تفعيل الوضع الفاتح'} title={theme === 'light' ? 'الوضع الداكن' : 'الوضع الفاتح'}>{theme === 'light' ? <Moon size={17} /> : <Sun size={17} />}</button>
        <span className="account-mark" aria-label="ملف محلي">A</span>
      </div>
    </header>
  );
}
