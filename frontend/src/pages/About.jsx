import { ExternalLink, Info, Server } from 'lucide-react';
import { Link } from 'react-router-dom';
import { MODULES } from '../api/endpoints';
import { Panel } from '../components/UI/primitives';
import { useLocale } from '../hooks/useLocale';

const modelApiUrl = import.meta.env.VITE_MODEL_API_URL || 'http://127.0.0.1:8001';

export default function About() {
  const { isEnglish, text } = useLocale();
  return <div className="page-stack"><div className="page-title-row"><div><span className="eyebrow">PLATFORM NOTES</span><h1>{text('عن المنصة', 'About the platform')}</h1><p>{text('تفاصيل تنظيم الواجهة وربط الخدمات.', 'Interface organization and service connections.')}</p></div></div>
    <Panel className="about-panel"><h2><Server size={19} /> {text('الخدمات المتصلة', 'Connected services')}</h2><p>{text('الخدمة الحديثة افتراضياً على', 'The model service defaults to')} <code>127.0.0.1:8001</code> {text('وتُضبط عبر', 'and is configured with')} <code>VITE_MODEL_API_URL</code>. {text('خدمة Sepsis/X-ray والمرضى القديمة افتراضياً على', 'The legacy Sepsis/X-ray and patient service defaults to')} <code>127.0.0.1:8000</code> {text('وتُضبط عبر', 'and is configured with')} <code>VITE_CLINICAL_API_URL</code>.</p><p>{text('الموديلات المدعومة في هذه الواجهة:', 'Models supported by this interface:')} {MODULES.filter((module) => module.available).map((module) => module.id).join(', ')}.</p></Panel>
    <Panel className="about-panel"><h2><Info size={19} /> {text('حدود التكامل', 'Integration limits')}</h2><ul><li><code>symptoms_all</code> {text('غير مسجل كـroute في', 'is not registered as a route in')} <code>app/main.py</code>.</li><li>{text('Gemini يستخدم RAG من مصادر المشروع؛ لا يُعدّل أوزان النموذج ولا يرسل بيانات تعريفية للمريض.', 'Gemini uses project-grounded RAG; it does not modify model weights or send identifying patient data.')}</li><li>{text('SHAP متاح فقط في استجابة Sepsis القديمة عند نجاح الخدمة.', 'SHAP is available only in successful responses from the legacy Sepsis service.')}</li><li>{text('السجل المحلي ليس سجلاً طبياً؛ كل طلب Gemini بسياق مريض يُسجل في Audit Log.', 'Browser history is not a medical record; every Gemini request with patient context is written to an audit log.')}</li></ul><a href={`${modelApiUrl}/docs`} target="_blank" rel="noreferrer">{isEnglish ? 'Model API documentation' : 'توثيق Model API'} <ExternalLink size={14} /></a></Panel>
    <Panel className="about-panel"><h2><Info size={19} /> {text('حالة الاستخدام', 'Use status')}</h2><p>{text('تجد حالة الاعتماد وحدود النماذج وسياسة البيانات في صفحة واحدة مخصصة.', 'Model validation, use limitations, and data guidance are collected on a dedicated page.')}</p><Link to="/research">{text('فتح حالة الاستخدام والاعتماد', 'Open use and validation status')} <ExternalLink size={14} /></Link></Panel>
  </div>;
}
