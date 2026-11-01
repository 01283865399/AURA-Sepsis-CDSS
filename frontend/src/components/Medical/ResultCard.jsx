import { CheckCircle2, Clock3, Share2 } from 'lucide-react';
import toast from 'react-hot-toast';
import { formatDate } from '../../utils/formatters';
import { getDisplayPredictions } from '../../utils/formatters';
import TopKPredictions from '../Charts/TopKPredictions';
import RiskGauge from '../Charts/RiskGauge';
import { Button } from '../UI/primitives';
import { useLocale } from '../../hooks/useLocale';
import FollowUpReport from './FollowUpReport';
import { buildClinicalReport } from '../../utils/buildClinicalReport';
import '../../styles/medical-content.css';

export default function ResultCard({ result, module }) {
  if (!result) return null;
  const { text, isEnglish } = useLocale();
  const predictions = getDisplayPredictions(result);
  const medicalContent = Array.isArray(result.medical_content) ? result.medical_content : [];
  const factors = result.top_contributing_factors || [];
  const followUpReport = buildClinicalReport(module, result, predictions, isEnglish);
  const shareResult = async () => {
    const summary = [
      `${isEnglish ? module.titleEn : module.title}: ${predictions[0]?.condition || result.risk_level || (isEnglish ? 'Analysis complete' : 'اكتمل التحليل')}`,
      followUpReport.summary,
      ...followUpReport.actions.map((action, index) => `${index + 1}. ${action}`),
      followUpReport.emergency,
    ].filter(Boolean).join('\n\n');
    try {
      if (navigator.share) await navigator.share({ title: `MediMind AI · ${module.title}`, text: summary });
      else {
        await navigator.clipboard.writeText(summary);
        toast.success(text('تم نسخ ملخص النتيجة.', 'Result summary copied.'));
      }
    } catch (error) {
      if (error.name !== 'AbortError') toast.error(text('تعذرت مشاركة النتيجة من هذا المتصفح.', 'Sharing is unavailable in this browser.'));
    }
  };
  return (
    <section className="result-panel" aria-labelledby="result-title">
      <header className="result-heading">
        <span className="result-icon"><CheckCircle2 size={20} /></span>
        <div><span className="eyebrow">{isEnglish ? module.titleEn : module.title}</span><h2 id="result-title">{text('نتيجة النموذج', 'Model result')}</h2></div>
      </header>
      <div className="result-meta"><span>{result.model_name || result.modelName || module.title}</span><span><Clock3 size={13} /> {formatDate(new Date().toISOString(), isEnglish ? 'en' : 'ar')}</span></div>
      {result.sepsis_probability != null && <RiskGauge value={result.sepsis_probability} label={text('درجة النموذج', 'Model score')} />}
      <FollowUpReport report={followUpReport} />
      {module.id === 'xray' && predictions[0] && (
        <section className="result-explanation" aria-labelledby="result-explanation-title">
          <h3 id="result-explanation-title">{text('شرح نتيجة الفحص', 'Screening interpretation')}</h3>
          <p>
            {text(
              `رصد النموذج نمطاً مرتبطاً بـ ${predictions[0].condition} بدرجة تشغيلية ${Number(result.confidence_score ?? predictions[0].probability * 100).toFixed(1)}/100. هذه الدرجة تساعد على ترتيب الإشارات التي يراجعها المختص، ولا تعني أن الحالة مصابة مؤكداً أو أن المريض في حالة غير مستقرة.`,
              `The model detected a pattern associated with ${predictions[0].condition} with an operational score of ${Number(result.confidence_score ?? predictions[0].probability * 100).toFixed(1)}/100. This ranks signals for specialist review; it does not confirm disease or establish clinical instability.`,
            )}
          </p>
          <p>
            {text(
              'تُفهم النتيجة مع جودة الصورة ووضعيتها والأعراض والعلامات الحيوية وتقرير اختصاصي الأشعة. لا تُستخدم هذه الإشارة وحدها لتغيير العلاج أو اتخاذ قرار سريري.',
              'Interpret the signal with image quality, projection, symptoms, vital signs, and a radiologist report. Do not use it alone to change treatment or make a clinical decision.',
            )}
          </p>
        </section>
      )}
      {predictions.length > 0 && <TopKPredictions predictions={predictions.slice(0, 5)} />}
      <section className="medical-content-summary" aria-labelledby="medical-content-title">
        <h3 id="medical-content-title">{text('ملاحظة التفسير', 'Interpretation note')}</h3>
        {medicalContent.length === 0
          ? <p>{text('تعكس هذه البطاقة مخرجات الفحص الآلي فقط. تُستكمل القراءة من الصورة الأصلية والسياق السريري وتقرير الاختصاصي.', 'This card presents the automated screening output. Complete interpretation requires the original image, clinical context, and specialist report.')}</p>
          : medicalContent.map((item, index) => {
            if (!item.available || !item.content) {
              return <p key={`${item.condition}-${index}`}>{isEnglish ? item.notice : (item.notice_ar || item.notice)}</p>;
            }
            const content = item.content;
            const description = content.description || {};
            const references = Array.isArray(content.references) ? content.references : [];
            return (
              <article key={`${item.condition}-${index}`}>
                <strong>{isEnglish ? (content.condition_en || item.condition) : (content.condition_ar || item.condition)}</strong>
                <p>{isEnglish ? (description.short_en || description.long_en) : (description.short_ar || description.long_ar)}</p>
                {references.filter((reference) => reference.url?.startsWith('https://')).length > 0 && (
                  <ul>
                    {references.filter((reference) => reference.url?.startsWith('https://')).map((reference) => (
                      <li key={reference.url}><a href={reference.url} target="_blank" rel="noreferrer">{reference.title || reference.source}</a></li>
                    ))}
                  </ul>
                )}
              </article>
            );
          })}
      </section>
      {result.data_completeness && <div className="completeness-note">{text('اكتمال المدخلات', 'Input completeness')}: {Math.round((result.data_completeness.score || 0) * 100)}% ({result.data_completeness.provided_feature_count}/{result.data_completeness.required_feature_count})</div>}
      {factors.length > 0 && (
        <div className="factor-list"><h3>{text('مساهمات النموذج · SHAP', 'Model contributions · SHAP')}</h3>
          <p>{text('راجع حدود تفسير المساهمات في صفحة حالة الاستخدام.', 'See the use-status page for SHAP interpretation limits.')}</p>
          {factors.slice(0, 5).map((factor) => <div key={factor.feature}><span>{factor.feature}</span><b dir="ltr">{Number(factor.impact).toFixed(3)}</b></div>)}
        </div>
      )}
      <div className="result-actions"><Button type="button" variant="secondary" onClick={shareResult}><Share2 size={15} /> {text('مشاركة الملخص', 'Share summary')}</Button></div>
    </section>
  );
}
