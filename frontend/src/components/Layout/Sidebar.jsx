import { Activity, BadgeInfo, ClipboardList, ExternalLink, FlaskConical, Gauge, Home, Info, ScanLine, Settings2, Users, X } from 'lucide-react';
import { useEffect } from 'react';
import { NavLink } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useUiStore } from '../../store/uiStore';

const clinicalApiUrl = import.meta.env.VITE_CLINICAL_API_URL || 'http://127.0.0.1:8000';

const items = [
  { to: '/', label: 'نظرة عامة', icon: Home, end: true },
  { to: '/dashboard', label: 'لوحة المتابعة', icon: Gauge },
  { to: '/models', label: 'مكتبة النماذج', icon: ScanLine },
  { to: '/history', label: 'سجل التحليلات', icon: ClipboardList },
];

export default function Sidebar() {
  const { t, i18n } = useTranslation();
  const english = i18n.language === 'en';
  const translatedItems = [
    { to: '/', label: t('home'), icon: Home, end: true },
    { to: '/assistant', label: t('assistant'), icon: Activity },
    { to: '/dashboard', label: t('dashboard'), icon: Gauge },
    { to: '/models', label: t('models'), icon: ScanLine },
    { to: '/modules/lab_ocr', label: t('labs'), icon: FlaskConical },
    { to: '/history', label: t('history'), icon: ClipboardList },
  ];
  const open = useUiStore((state) => state.sidebarOpen);
  const setOpen = useUiStore((state) => state.setSidebarOpen);

  useEffect(() => {
    if (!open) return undefined;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [open]);

  return (
    <>
      {open && <button className="sidebar-scrim" type="button" onClick={() => setOpen(false)} aria-label="إغلاق القائمة" />}
      <aside className={`sidebar ${open ? 'sidebar-open' : ''}`}>
        <div className="sidebar-brand"><span className="brand-symbol"><Activity size={21} /></span><div><b>MediMind AI</b><small>MEDICAL RESEARCH</small></div><button className="sidebar-close icon-button" type="button" onClick={() => setOpen(false)} aria-label="إغلاق"><X size={18} /></button></div>
        <div className="sidebar-caption">{english ? 'WORKSPACE' : 'مساحة العمل'}</div>
        <nav aria-label="التنقل الرئيسي">
          {translatedItems.map(({ to, label, icon: Icon, end }) => <NavLink key={to} to={to} end={end} onClick={() => setOpen(false)} className={({ isActive }) => `side-link ${isActive ? 'side-link-active' : ''}`}><Icon size={18} /><span>{label}</span></NavLink>)}
        </nav>
        <div className="sidebar-caption side-caption-spaced">{english ? 'SUPPORT' : 'المساندة'}</div>
        <nav aria-label="روابط إضافية">
          <NavLink to="/profile" onClick={() => setOpen(false)} className={({ isActive }) => `side-link ${isActive ? 'side-link-active' : ''}`}><Settings2 size={18} /><span>{t('profile')}</span></NavLink>
          <NavLink to="/research" onClick={() => setOpen(false)} className={({ isActive }) => `side-link ${isActive ? 'side-link-active' : ''}`}><BadgeInfo size={18} /><span>{english ? 'Use and validation status' : 'حالة الاستخدام والاعتماد'}</span></NavLink>
          <NavLink to="/about" onClick={() => setOpen(false)} className={({ isActive }) => `side-link ${isActive ? 'side-link-active' : ''}`}><Info size={18} /><span>{t('about')}</span></NavLink>
          <NavLink to="/patients" onClick={() => setOpen(false)} className={({ isActive }) => `side-link ${isActive ? 'side-link-active' : ''}`}><Users size={18} /><span>{t('patients')}</span></NavLink>
          <a className="side-link" href={`${clinicalApiUrl}/docs`} target="_blank" rel="noreferrer"><ExternalLink size={18} /><span>{english ? 'Clinical API docs' : 'توثيق Clinical API'}</span></a>
        </nav>
        <div className="sidebar-bottom"><span className="sidebar-status-dot" /><div><strong>{english ? 'MediMind workspace' : 'مساحة MediMind'}</strong><small>{english ? 'Research model operations' : 'تشغيل النماذج البحثية'}</small></div></div>
      </aside>
    </>
  );
}
