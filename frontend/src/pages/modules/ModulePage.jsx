import { zodResolver } from '@hookform/resolvers/zod';
import { ArrowRight, FileText, Info, RotateCcw, Send, ShieldCheck } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useForm } from 'react-hook-form';
import { Link, useParams } from 'react-router-dom';
import { getModule } from '../../api/endpoints';
import ResultCard from '../../components/Medical/ResultCard';
import { Alert, Button, Field, FileUpload, Loading, Panel } from '../../components/UI/primitives';
import { usePrediction } from '../../hooks/usePrediction';
import { validateImage } from '../../utils/validators';
import { makeModuleSchema } from '../../utils/validators';
import { useLocale } from '../../hooks/useLocale';

export default function ModulePage() {
  const { moduleId } = useParams();
  const { isEnglish, text } = useLocale();
  const module = getModule(moduleId);
  const [file, setFile] = useState(null);
  const [fileError, setFileError] = useState('');
  const [previewUrl, setPreviewUrl] = useState('');
  const prediction = usePrediction();
  const schema = useMemo(() => module ? makeModuleSchema(module) : undefined, [module]);
  const defaultValues = useMemo(() => {
    if (!module) return {};
    if (module.id === 'symptoms') return { symptoms: '' };
    if (module.id === 'ddxplus') return { age: '', sex: '', evidences: '' };
    return Object.fromEntries((module.fields || []).map((field) => [field.name, '']));
  }, [module]);
  const { register, handleSubmit, reset, formState: { errors } } = useForm({
    resolver: schema ? zodResolver(schema) : undefined,
    defaultValues,
    mode: 'onBlur',
  });

  useEffect(() => {
    reset(defaultValues);
    setFile(null);
    setFileError('');
    prediction.reset();
  }, [moduleId, defaultValues, reset]);

  useEffect(() => {
    if (!file) {
      setPreviewUrl('');
      return undefined;
    }
    const objectUrl = URL.createObjectURL(file);
    setPreviewUrl(objectUrl);
    return () => URL.revokeObjectURL(objectUrl);
  }, [file]);

  const submit = (values) => {
    if (module.transport !== 'json') {
      const validationError = validateImage(file);
      if (validationError) {
        setFileError(validationError);
        return;
      }
    }
    setFileError('');
    prediction.mutate({ module, values, file });
  };

  if (!module) return <div className="page-stack"><h1>{text('النموذج غير موجود', 'Model not found')}</h1><Link to="/models">{text('العودة إلى مكتبة النماذج', 'Return to model catalog')}</Link></div>;

  if (!module.available) {
    return <div className="page-stack"><Link className="back-link" to="/models"><ArrowRight size={16} /> {text('مكتبة النماذج', 'Model catalog')}</Link><Panel className="unavailable-panel"><span className="model-icon"><Info size={21} /></span><h1>{isEnglish ? module.titleEn : module.title}</h1><p>{isEnglish ? module.descriptionEn : module.description}</p><Alert tone="warning">{text('لا يوجد route في الـBackend الحالي؛ لم يتم إرسال أي طلب لهذا النموذج.', 'This backend route is not registered. No request was sent.')}</Alert><code>POST /api/v1/diagnose/symptoms_all</code></Panel></div>;
  }

  const primaryFields = (module.fields || []).filter((field) => !field.advanced);
  const advancedFields = (module.fields || []).filter((field) => field.advanced);
  const imageModule = module.transport === 'image-form' || module.transport === 'raw-image';
  const category = isEnglish ? ({ سريري: 'Clinical', تصوير: 'Imaging', أعراض: 'Symptoms', مختبر: 'Laboratory' }[module.category] || module.category) : module.category;

  return (
    <div className="page-stack">
      <Link className="back-link" to="/models"><ArrowRight size={16} /> {text('مكتبة النماذج', 'Model catalog')}</Link>
      <div className="module-page-heading"><div><span className="eyebrow">{category} · {module.count}</span><h1>{isEnglish ? module.titleEn : module.title}</h1><p>{isEnglish ? module.descriptionEn : module.description}</p></div><span className="module-mark"><ShieldCheck size={21} /></span></div>
      <div className="module-layout">
        <Panel className="assessment-panel">
          <div className="panel-title"><div><span className="step-index">01</span><div><h2>{text('المدخلات', 'Inputs')}</h2><p>{text('أدخل القيم التي تم التحقق منها فقط.', 'Enter verified values only.')}</p></div></div><FileText size={18} /></div>
          <form onSubmit={handleSubmit(submit)} noValidate>
            {module.id === 'symptoms' && (
              <label className="form-field" htmlFor="symptoms"><span>{text('الأعراض', 'Symptoms')} <b>*</b></span><textarea id="symptoms" rows="5" placeholder={text('مثال: fever, cough ... أدخل أسماء الأعراض التي يتوقعها النموذج', 'Enter symptom names expected by the model, e.g. fever, cough')} {...register('symptoms')} aria-invalid={Boolean(errors.symptoms)} aria-describedby={errors.symptoms ? 'symptoms-error' : undefined} />{errors.symptoms && <small className="field-error" id="symptoms-error" role="alert">{errors.symptoms.message}</small>}<small>{text('افصل بين الأعراض بفاصلة أو سطر جديد. لا توجد حالياً قائمة اقتراحات منشورة من الـAPI.', 'Separate symptoms with commas or new lines. The API does not publish a suggestion list.')}</small></label>
            )}
            {module.id === 'ddxplus' && <div className="form-grid"><Field field={{ name: 'age', label: 'العمر', labelEn: 'Age', type: 'number', required: true, min: 0, max: 120 }} register={register} error={errors.age} language={isEnglish ? 'en' : 'ar'} /><Field field={{ name: 'sex', label: 'الجنس', labelEn: 'Sex', type: 'select', required: true, options: [{ label: isEnglish ? 'Female' : 'أنثى', value: 'F' }, { label: isEnglish ? 'Male' : 'ذكر', value: 'M' }] }} register={register} error={errors.sex} language={isEnglish ? 'en' : 'ar'} /><label className="form-field form-field-wide" htmlFor="evidences"><span>{text('أدلة DDXPlus', 'DDXPlus evidence codes')} <b>*</b></span><textarea id="evidences" rows="4" placeholder="E_... or E_..._@_value" {...register('evidences')} aria-invalid={Boolean(errors.evidences)} />{errors.evidences && <small className="field-error" role="alert">{errors.evidences.message}</small>}<small>{text('استخدم رموز الأدلة المسجلة بصيغة E_…', 'Use registered evidence codes in E_… format.')}</small></label></div>}
            {primaryFields.length > 0 && <div className="form-grid">{primaryFields.map((field) => <Field key={field.name} field={field} register={register} error={errors[field.name]} language={isEnglish ? 'en' : 'ar'} />)}</div>}
            {advancedFields.length > 0 && <details className="advanced-fields"><summary>{text('خصائص المختبر الإضافية', 'Additional laboratory features')} ({advancedFields.length})</summary><div className="form-grid">{advancedFields.map((field) => <Field key={field.name} field={field} register={register} error={errors[field.name]} language={isEnglish ? 'en' : 'ar'} />)}</div></details>}
            {imageModule && <div className="upload-block"><FileUpload file={file} onChange={(nextFile) => { setFile(nextFile); setFileError(''); }} error={fileError} />{previewUrl && <img className="upload-preview" src={previewUrl} alt={text('معاينة الملف المحدد', 'Selected file preview')} />}</div>}
            <div className="form-footnote"><Info size={15} /><span>{text('الحقول الاختيارية الفارغة لا تُرسل. تحقق من الوحدات والقيم قبل المتابعة.', 'Blank optional fields are omitted. Verify units and values before continuing.')}</span></div>
            {prediction.error && <Alert>{prediction.error.userMessage || text('تعذر إكمال الطلب.', 'The request could not be completed.')}</Alert>}
            <div className="form-actions"><Button type="submit" disabled={prediction.isPending}>{prediction.isPending ? <Loading label={text('جارٍ التحليل', 'Analyzing')} /> : <><Send size={16} /> {text('تحليل', 'Analyze')}</>}</Button><Button type="button" variant="secondary" onClick={() => { reset(defaultValues); setFile(null); setFileError(''); prediction.reset(); }} disabled={prediction.isPending}><RotateCcw size={15} /> {text('إعادة ضبط', 'Reset')}</Button></div>
          </form>
        </Panel>
        <div className="result-column">
          {prediction.data ? <ResultCard result={prediction.data} module={module} /> : <Panel className="result-placeholder"><span className="placeholder-icon"><Info size={20} /></span><span className="eyebrow">02 · MODEL OUTPUT</span><h2>{text('بانتظار التحليل', 'Awaiting analysis')}</h2><p>{text('بعد الإرسال ستظهر استجابة الخادم هنا، مع أعلى النتائج أو تفاصيل الفحص المتاحة.', 'The server response, top predictions, or screening details will appear here.')}</p></Panel>}
        </div>
      </div>
    </div>
  );
}
