import { Activity, ArrowUpLeft, Globe2, ListChecks, ShieldCheck, Sparkles } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useUiStore } from '../store/uiStore';
import './landing.css';

const text = (english, arabic, value) => (english ? value : arabic);

const medicalHighlights = [
  {
    icon: Activity,
    title: 'تقدير الإنتان',
    titleEn: 'Sepsis assessment',
    description: 'مراجعة العلامات الحيوية والتحاليل ضمن مسار بحثي واضح.',
    descriptionEn: 'Review vital signs and laboratory inputs in a research workflow.',
  },
  {
    icon: ListChecks,
    title: 'تحليل الأعراض',
    titleEn: 'Symptom analysis',
    description: 'ترتيب الاحتمالات من الأعراض المدخلة دون استبدال التقييم الطبي.',
    descriptionEn: 'Rank possibilities from entered symptoms without replacing clinical assessment.',
  },
  {
    icon: ShieldCheck,
    title: 'مراجعة آمنة',
    titleEn: 'Careful review',
    description: 'كل النتائج بحثية وتحتاج مراجعة مختص وبروتوكولات المكان.',
    descriptionEn: 'Outputs are research signals requiring specialist review and local protocols.',
  },
];

export default function Landing() {
  const language = useUiStore((state) => state.language);
  const setLanguage = useUiStore((state) => state.setLanguage);
  const { i18n } = useTranslation();
  const isEnglish = language === 'en';
  const splineScene = import.meta.env.VITE_SPLINE_SCENE
    || 'https://my.spline.design/nancylookingaround-cloyfNCxbzM7fwj0IpBuuwzc/';

  const toggleLanguage = () => {
    const nextLanguage = isEnglish ? 'ar' : 'en';
    setLanguage(nextLanguage);
    void i18n.changeLanguage(nextLanguage);
  };

  return (
    <main className="medical-landing">
      <header className="medical-landing-header">
        <Link className="medical-brand" to="/" aria-label="MediMind AI">
          <span className="medical-brand-mark"><Activity size={18} /></span>
          <span>MEDIMIND <b>AI</b><small>{text(isEnglish, 'منصة طبية بحثية', 'MEDICAL RESEARCH')}</small></span>
        </Link>
        <nav className="medical-landing-nav" aria-label={text(isEnglish, 'التنقل', 'Navigation')}>
          <Link to="/models">{text(isEnglish, 'النماذج', 'Models')}</Link>
          <Link to="/research">{text(isEnglish, 'حدود الاستخدام', 'Use limits')}</Link>
          <Link className="medical-nav-primary" to="/assistant">{text(isEnglish, 'افتح المساعد', 'Open assistant')} <ArrowUpLeft size={15} /></Link>
          <button type="button" onClick={toggleLanguage} aria-label={text(isEnglish, 'التبديل للعربية', 'Switch to Arabic')}><Globe2 size={15} />{isEnglish ? 'ع' : 'EN'}</button>
        </nav>
      </header>

      <section className="medical-landing-hero">
        <div className="medical-landing-copy">
          <span className="medical-eyebrow"><Sparkles size={14} /> {text(isEnglish, 'دعم القرار الطبي · استخدام بحثي', 'MEDICAL DECISION SUPPORT · RESEARCH USE')}</span>
          <h1>{text(isEnglish, 'رؤية أوضح لكل حالة.', 'Clearer insight for every case.')}</h1>
          <p>{text(isEnglish, 'مساحة موحدة لاستكشاف النماذج الطبية ومراجعة مخرجاتها مع سياق واضح وحدود معلنة.', 'A focused workspace for exploring medical models and reviewing their outputs with clear context and visible limits.')}</p>
          <div className="medical-landing-actions">
            <Link className="medical-button medical-button-primary" to="/assistant">{text(isEnglish, 'ابدأ محادثة أو تحليلاً', 'Start a chat or analysis')} <ArrowUpLeft size={16} /></Link>
            <Link className="medical-button medical-button-secondary" to="/models">{text(isEnglish, 'استعرض النماذج', 'Browse models')}</Link>
          </div>
          <div className="medical-safety-note"><ShieldCheck size={16} />{text(isEnglish, 'ليست أداة تشخيص أو علاج. راجع كل نتيجة مع مختص.', 'Not a diagnostic or treatment tool. Review every result with a qualified clinician.')}</div>
        </div>
        <div className="medical-spline-card" aria-label={text(isEnglish, 'نموذج ثلاثي الأبعاد للمنصة', '3D model of the platform')}>
          <iframe className="medical-spline-frame" title={text(isEnglish, 'نموذج ثلاثي الأبعاد', '3D model')} src={splineScene} />
          <span className="medical-spline-label">{text(isEnglish, 'نماذج · سياق · مراجعة', 'MODELS · CONTEXT · REVIEW')}</span>
        </div>
      </section>

      <section className="medical-highlights" aria-label={text(isEnglish, 'محتوى طبي', 'Medical capabilities')}>
        {medicalHighlights.map(({ icon: Icon, title, titleEn, description, descriptionEn }) => (
          <article className="medical-highlight-card" key={titleEn}>
            <span className="medical-highlight-icon"><Icon size={18} /></span>
            <h2>{text(isEnglish, title, titleEn)}</h2>
            <p>{text(isEnglish, description, descriptionEn)}</p>
          </article>
        ))}
      </section>

      <footer className="medical-landing-footer">
        <span>MEDIMIND AI · {text(isEnglish, 'منصة بحثية طبية', 'MEDICAL RESEARCH PLATFORM')}</span>
        <Link to="/disclaimer">{text(isEnglish, 'إخلاء المسؤولية والخصوصية', 'Disclaimer and privacy')}</Link>
      </footer>
    </main>
  );
}
