import { useQuery } from '@tanstack/react-query';
import { Activity, AlertTriangle, BookOpenCheck, CheckCircle2, Database, FileSearch, Info, ScanLine, ShieldCheck, TriangleAlert } from 'lucide-react';
import { Link } from 'react-router-dom';
import { clinicalApi } from '../api/client';
import { MODULES } from '../api/endpoints';
import { Panel } from '../components/UI/primitives';
import { useApiHealth } from '../hooks/useApiHealth';
import { useLocale } from '../hooks/useLocale';
import '../styles/research-status.css';

export default function ResearchStatus() {
  const { isEnglish, text } = useLocale();
  const modelHealth = useApiHealth();
  const clinicalHealth = useQuery({
    queryKey: ['clinical-api-status'],
    queryFn: async () => (await clinicalApi.get('/')).data,
    retry: false,
    staleTime: 30000,
    refetchOnWindowFocus: false,
  });
  const availableCount = MODULES.filter((module) => module.available).length;

  return (
    <div className="page-stack research-status-page">
      <section className="governance-hero">
        <div className="governance-mark"><ShieldCheck size={23} /></div>
        <div className="governance-copy">
          <span className="eyebrow">MODEL GOVERNANCE</span>
          <h1>{text('حالة الاستخدام والاعتماد', 'Use and validation status')}</h1>
          <p>{text('تجميع موحد لحالة النماذج والخدمات وحدود استخدام مخرجاتها.', 'A single reference for model status, connected services, and output limitations.')}</p>
        </div>
        <span className="governance-status"><i /> {text('استخدام بحثي فقط', 'Research use only')}</span>
      </section>

      <div className="service-status-grid">
        <Panel className="service-status-panel">
          <div className="service-status-heading"><span className="service-status-icon"><Activity size={18} /></span><div><span className="eyebrow">MODEL API · :8001</span><h2>{text('خدمة النماذج', 'Model service')}</h2></div></div>
          <div className="service-status-row"><span>{text('الاتصال', 'Connection')}</span><strong className={modelHealth.isSuccess ? 'status-value-online' : 'status-value-offline'}>{modelHealth.isSuccess ? text('متصل', 'Online') : modelHealth.isPending ? text('جارٍ الفحص', 'Checking') : text('غير متصل', 'Offline')}</strong></div>
          <div className="service-status-row"><span>{text('المسارات المنشورة', 'Registered routes')}</span><strong>{availableCount}</strong></div>
          <div className="service-status-row"><span>{text('حالة الاستخدام', 'Use status')}</span><strong>{text('بحثي', 'Research')}</strong></div>
        </Panel>
        <Panel className="service-status-panel">
          <div className="service-status-heading"><span className="service-status-icon service-status-legacy"><Database size={18} /></span><div><span className="eyebrow">CLINICAL API · :8000</span><h2>{text('خدمة Sepsis والأشعة', 'Sepsis and imaging service')}</h2></div></div>
          <div className="service-status-row"><span>{text('الاتصال', 'Connection')}</span><strong className={clinicalHealth.isSuccess ? 'status-value-online' : clinicalHealth.isPending ? '' : 'status-value-offline'}>{clinicalHealth.isSuccess ? text('متصل', 'Online') : clinicalHealth.isPending ? text('جارٍ الفحص', 'Checking') : text('غير متصل', 'Offline')}</strong></div>
          <div className="service-status-row"><span>{text('حالة الاعتماد', 'Validation status')}</span><strong>{clinicalHealth.data?.clinical_status === 'approved' ? text('معتمد سريرياً', 'Clinically approved') : text('بحثي فقط', 'Research only')}</strong></div>
          <div className="service-status-row"><span>{text('Sepsis enabled', 'Sepsis access')}</span><strong>{clinicalHealth.data?.deployment_approved ? text('اعتماد معلن', 'Approval declared') : clinicalHealth.isSuccess ? text('تجريبي محلي', 'Local research override') : '—'}</strong></div>
        </Panel>
      </div>

      <section className="governance-warning" aria-labelledby="governance-warning-title">
        <div className="governance-warning-icon"><AlertTriangle size={21} /></div>
        <div><span className="eyebrow">IMPORTANT</span><h2 id="governance-warning-title">{text('حدود الاستخدام السريري', 'Clinical use limitations')}</h2><p>{text('لم تُعتمد هذه النماذج للاستخدام السريري المستقل. مخرجاتها ليست تشخيصاً أو توصية علاجية أو وسيلة لاستبعاد مرض، ولا تحل محل التقييم المباشر من طبيب مؤهل أو البروتوكولات المحلية.', 'These models are not approved for independent clinical use. Their outputs are not diagnoses, treatment recommendations, or a way to rule out disease. They do not replace qualified clinical assessment or local protocols.')}</p></div>
      </section>

      <div className="governance-detail-grid">
        <Panel className="governance-detail"><span className="governance-detail-icon"><TriangleAlert size={18} /></span><h2>{text('الدرجات والاحتمالات', 'Scores and probabilities')}</h2><p>{text('درجات Sepsis غير معايرة كاحتمال فردي. حدود الخطورة وإشارات الأشعة نقاط تشغيلية بحثية وليست حدود قرار سريري.', 'Sepsis scores are not calibrated individual probabilities. Risk bands and radiology signals are exploratory operating points, not clinical decision thresholds.')}</p></Panel>
        <Panel className="governance-detail"><span className="governance-detail-icon governance-detail-blue"><FileSearch size={18} /></span><h2>{text('الصور وOCR', 'Images and OCR')}</h2><p>{text('نتائج الأشعة إشارة فحص تحتاج مراجعة اختصاصي أشعة. قيم OCR مرشحة فقط ويجب التحقق من كل قيمة ووحدة بمقارنتها بالتقرير الأصلي.', 'Radiology output is a screening signal requiring radiologist review. OCR values are candidates only; verify every value and unit against the original report.')}</p></Panel>
        <Panel className="governance-detail"><span className="governance-detail-icon governance-detail-amber"><BookOpenCheck size={18} /></span><h2>{text('التفسير والخصوصية', 'Explanations and privacy')}</h2><p>{text('مساهمات SHAP تشرح سلوك النموذج ولا تثبت السببية. لا تدخل أسماء أو معرفات أو صوراً مرتبطة بمريض حقيقي؛ السجل الحالي محلي في المتصفح وليس سجلاً طبياً.', 'SHAP contributions describe model behavior, not causation. Do not enter names, identifiers, or patient-linked images. Browser history is local and is not a medical record.')}</p></Panel>
      </div>

      <Panel className="governance-integrations">
        <div><span className="eyebrow">INTEGRATION STATUS</span><h2>{text('المسارات وحدود التكامل', 'Routes and integration limits')}</h2></div>
        <ul>
          <li><CheckCircle2 size={15} /> {text('المسارات المتاحة حالياً:', 'Currently available routes:')} {MODULES.filter((module) => module.available).map((module) => module.id).join('، ')}.</li>
          <li><Info size={15} /> <code>symptoms_all</code> {text('لا يملك endpoint مسجلاً في الخادم الحالي.', 'has no registered endpoint on the current backend.')}</li>
          <li><Info size={15} /> {text('مصادقة JWT مفعلة للأدوار البحثية؛ سياق المريض يحتاج موافقة صريحة ويُرسل منزوع الهوية فقط.', 'Backend JWT auth is enabled for research roles; patient context requires explicit consent and is de-identified before Gemini.')}</li>
        </ul>
        <Link to="/about">{text('تفاصيل الخوادم والتكامل', 'Server and integration details')} <ScanLine size={15} /></Link>
      </Panel>
    </div>
  );
}
