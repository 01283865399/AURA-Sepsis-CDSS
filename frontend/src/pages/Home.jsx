import { motion } from 'framer-motion';
import { ArrowUpLeft, Search, ShieldCheck, Sparkles } from 'lucide-react';
import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { MODULES } from '../api/endpoints';
import { Badge, Panel } from '../components/UI/primitives';
import { usePredictionStore } from '../store/predictionStore';
import { useTranslation } from 'react-i18next';
import { Activity, Bean, Droplets, FlaskConical, HeartPulse, Layers3, ListChecks, Microscope, Network, ScanFace, ScanLine } from 'lucide-react';

const MODEL_ICONS = { Activity, Bean, Droplets, FlaskConical, HeartPulse, Layers3, ListChecks, Microscope, Network, ScanFace, ScanLine };

export default function Home() {
  const [search, setSearch] = useState('');
  const { t, i18n } = useTranslation();
  const history = usePredictionStore((state) => state.history);
  const filtered = useMemo(() => MODULES.filter((module) => `${module.title} ${module.titleEn} ${module.description}`.toLowerCase().includes(search.toLowerCase())), [search]);
  const isEnglish = i18n.language === 'en';

  return (
    <div className="page-stack">
      <section className="home-intro">
        <div className="home-intro-copy"><div className="eyebrow"><Sparkles size={14} /> {t('welcome')}</div><h1>{isEnglish ? 'Model workspace' : 'منصة النماذج الطبية'}</h1><p>{isEnglish ? 'Review available research models, submit a structured assessment, and keep a private browser-side history.' : 'استعرض النماذج البحثية، أرسل تقييماً منظماً، واحتفظ بسجل محلي خاص بهذا المتصفح.'}</p><div className="home-intro-actions"><Link className="button button-primary" to="/models">{t('models')} <ArrowUpLeft size={16} /></Link><Link className="button button-secondary" to="/dashboard">{t('dashboard')}</Link></div></div>
        <div className="home-intro-aside"><span className="intro-symbol"><ShieldCheck size={25} /></span><strong>{isEnglish ? 'Model and service information' : 'معلومات النماذج والخدمات'}</strong><Link to="/research">{isEnglish ? 'View use and validation status' : 'عرض حالة الاستخدام والاعتماد'}</Link></div>
      </section>

      <section className="catalog-section" aria-labelledby="catalog-title">
        <div className="section-heading"><div><span className="eyebrow">MODEL CATALOG</span><h2 id="catalog-title">{isEnglish ? 'Available analysis routes' : 'مسارات التحليل'}</h2></div><label className="search-box"><Search size={16} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder={t('search')} /></label></div>
        <div className="catalog-grid">
          {filtered.map((module, index) => {
            const Icon = MODEL_ICONS[module.icon] || Activity;
            const title = isEnglish ? module.titleEn : module.title;
            const description = isEnglish ? module.descriptionEn : module.description;
            const card = <Panel className={`model-card ${module.available ? '' : 'model-card-disabled'}`} key={module.id}>
              <div className="model-card-top"><span className={`model-icon model-icon-${index % 5}`}><Icon size={19} /></span><Badge tone={module.available ? 'success' : 'muted'}>{module.available ? (isEnglish ? 'Connected route' : 'مسار متاح') : t('unsupported')}</Badge></div>
              <h3>{title}</h3><p>{description}</p><div className="model-card-bottom"><span>{module.count}</span>{module.available ? <Link to={`/modules/${module.id}`} aria-label={`${t('openModel')}: ${title}`} title={t('openModel')}><ArrowUpLeft size={18} /></Link> : <span className="route-missing">غير منشور</span>}</div>
            </Panel>;
            return module.available ? <motion.div key={module.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: Math.min(index * 0.025, 0.25) }}>{card}</motion.div> : <div key={module.id}>{card}</div>;
          })}
        </div>
        {!filtered.length && <div className="empty-state">{isEnglish ? 'No models match your search.' : 'لا توجد نماذج تطابق البحث.'}</div>}
      </section>

      <section className="home-bottom-grid">
        <Panel className="stat-panel"><span className="eyebrow">LOCAL WORKSPACE</span><strong>{MODULES.filter((module) => module.available).length}</strong><span>مسارات API متاحة · {MODULES.length} بطاقة في الكتالوج</span></Panel>
        <Panel className="stat-panel"><span className="eyebrow">BROWSER HISTORY</span><strong>{history.length}</strong><span>{t('checks')}</span></Panel>
        <Panel className="availability-panel"><span className="eyebrow">{isEnglish ? 'REQUIRED FOR AI CHAT' : 'مطلوب لاستخدام الشات'}</span><strong>{isEnglish ? 'Research account' : 'حساب بحثي'}</strong><span>{isEnglish ? 'Create an account or sign in before sending messages to the AI assistant.' : 'أنشئ حسابًا أو سجّل الدخول قبل إرسال رسائل إلى المساعد الذكي.'}</span><Link to="/register">{isEnglish ? 'Create research account' : 'إنشاء حساب بحثي'}</Link></Panel>
      </section>
    </div>
  );
}
