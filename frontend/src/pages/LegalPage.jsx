import { BookOpenCheck, ShieldAlert } from 'lucide-react';
import { Link, useLocation } from 'react-router-dom';
import { Panel } from '../components/UI/primitives';
import { useUiStore } from '../store/uiStore';
import './legal.css';

const LEGAL_DOCUMENTS = {
  disclaimer: {
    title: ['إخلاء المسؤولية الطبية', 'Medical disclaimer'],
    intro: [
      'MediMind AI منصة بحثية تجريبية. مخرجات النماذج لا تمثل تشخيصاً أو توصية علاجية ولا تصلح لاتخاذ قرار سريري مستقل.',
      'MediMind AI is an experimental research platform. Model outputs are not diagnoses or treatment recommendations and are not suitable for independent clinical decisions.',
    ],
    sections: [
      {
        title: ['حدود النماذج', 'Model limitations'],
        body: [
          'لم تُعتمد النماذج للاستخدام السريري المستقل. قد تكون النتائج غير دقيقة أو ناقصة أو متحيزة، كما أن درجات النماذج ليست بالضرورة احتمالات فردية معايرة.',
          'The models are not approved for independent clinical use. Results may be inaccurate, incomplete, or biased, and model scores are not necessarily calibrated individual probabilities.',
        ],
      },
      {
        title: ['المراجعة البشرية', 'Qualified review'],
        body: [
          'راجع كل مخرج مع مختص مؤهل والسياق السريري والبروتوكولات المحلية. لا تستخدم المنصة لاستبعاد مرض أو تأخير طلب الرعاية.',
          'Review every output with a qualified professional, clinical context, and local protocols. Do not use the platform to rule out disease or delay care.',
        ],
      },
      {
        title: ['الحالات الطارئة', 'Emergencies'],
        body: [
          'في حالة الطوارئ، تواصل مع خدمات الطوارئ المحلية أو مقدم الرعاية مباشرة؛ لا تنتظر استجابة المنصة.',
          'For emergencies, contact local emergency services or a healthcare professional directly; do not wait for a platform response.',
        ],
      },
    ],
  },
  privacy: {
    title: ['الخصوصية والبيانات', 'Privacy and data'],
    intro: [
      'هذه صفحة توضيحية لسلوك النسخة التجريبية الحالية، وليست ضماناً قانونياً للخصوصية. لا تُدخل أسماء أو معرفات أو صوراً مرتبطة بمرضى حقيقيين.',
      'This page describes the current prototype behavior; it is not a legal privacy guarantee. Do not enter names, identifiers, or images linked to real patients.',
    ],
    sections: [
      {
        title: ['التخزين المحلي', 'Browser storage'],
        body: [
          'تُحفظ تفضيلات اللغة والمظهر وسجل ملخصات التحليل في تخزين المتصفح المحلي. السجل محلي لهذا المتصفح، وليس سجلاً طبياً موثوقاً أو متزامناً بين الأجهزة؛ ويمكن مسحه من صفحة السجل.',
          'Language and theme preferences and a summary history are stored in browser local storage. This history is local to this browser, is not a verified medical record or synchronized between devices, and can be cleared from History.',
        ],
      },
      {
        title: ['إرسال التحليلات', 'Analysis requests'],
        body: [
          'تُرسل مدخلات التحليل إلى خدمة الـAPI المضبوطة لتشغيل النموذج. تختلف المعالجة والاحتفاظ بحسب إعداد الخدمة المحلية؛ لا تفترض أن أي مدخلات أُرسلت إلى خدمة متصلة لا تُسجل.',
          'Analysis inputs are sent to the configured API service to run a model. Processing and retention depend on that local service configuration; do not assume submitted inputs are never logged by a connected service.',
        ],
      },
      {
        title: ['الحسابات والمرضى', 'Accounts and patient records'],
        body: [
          'لا توجد حالياً خدمة حسابات أو JWT مهيأة. تخزين بيانات المرضى غير معتمد للاستخدام السريري؛ لا تستخدم بيانات تعريفية حقيقية.',
          'No account or JWT service is currently configured. Patient-data storage is not approved for clinical use; do not use identifiable real data.',
        ],
      },
    ],
  },
  terms: {
    title: ['شروط الاستخدام', 'Terms of use'],
    intro: [
      'هذه خلاصة إرشادية لاستخدام نموذج بحثي تجريبي، وليست عقداً قانونياً أو استشارة قانونية.',
      'This is an informational summary for an experimental research prototype, not a legal contract or legal advice.',
    ],
    sections: [
      {
        title: ['الاستخدام المسموح', 'Intended use'],
        body: [
          'استخدم المنصة للاستكشاف والاختبار البحثي فقط. لا تستخدم المخرجات للتشخيص أو العلاج أو الفرز السريري المستقل.',
          'Use the platform for exploration and research testing only. Do not use outputs for diagnosis, treatment, or independent clinical triage.',
        ],
      },
      {
        title: ['مسؤولية المدخلات', 'Input responsibility'],
        body: [
          'لا تُرسل معلومات لا تملك صلاحية استخدامها، ولا تُدخل بيانات تعريفية أو سرية أو مرتبطة بمريض حقيقي. استخدم بيانات اختبار غير معرّفة.',
          'Do not submit information you are not authorized to use, or identifying, confidential, or patient-linked data. Use non-identifiable test data.',
        ],
      },
      {
        title: ['الاعتمادية والتوفر', 'Reliability and availability'],
        body: [
          'قد تتوقف الخدمات أو تتغير النماذج والنتائج دون إشعار. افحص حالة الخدمة وحدود الاستخدام قبل أي اختبار، وارجع إلى صفحة حالة الاعتماد.',
          'Services may be unavailable and models or outputs may change without notice. Check service status and use limitations before testing, and review the validation-status page.',
        ],
      },
    ],
  },
};

export default function LegalPage() {
  const { pathname } = useLocation();
  const language = useUiStore((state) => state.language);
  const isEnglish = language === 'en';
  const key = pathname.split('/').filter(Boolean).at(-1);
  const document = LEGAL_DOCUMENTS[key] || LEGAL_DOCUMENTS.disclaimer;
  const localized = (values) => values[isEnglish ? 1 : 0];

  return (
    <div className="page-stack legal-page">
      <div className="page-title-row">
        <div>
          <span className="eyebrow">PLATFORM NOTICE</span>
          <h1>{localized(document.title)}</h1>
          <p>{localized(document.intro)}</p>
        </div>
      </div>
      <Panel className="legal-notice-banner">
        <ShieldAlert size={20} />
        <p>{isEnglish ? 'Research prototype only. Do not use for clinical decisions or submit real patient data.' : 'نموذج بحثي فقط. لا تستخدمه لاتخاذ قرارات سريرية ولا تُدخل بيانات مرضى حقيقية.'}</p>
      </Panel>
      <div className="legal-section-list">
        {document.sections.map((section) => (
          <Panel className="legal-section-panel" key={section.title[0]}>
            <h2><BookOpenCheck size={18} /> {localized(section.title)}</h2>
            <p>{localized(section.body)}</p>
          </Panel>
        ))}
      </div>
      <p className="legal-disclaimer-note">{isEnglish ? 'These prototype notices are informational and should be reviewed before any public or regulated deployment.' : 'هذه الإشعارات التوضيحية للنموذج الأولي، ويجب مراجعتها قبل أي نشر عام أو استخدام منظم.'}</p>
      <div className="legal-page-links">
        <Link to="/research">{isEnglish ? 'Use and validation status' : 'حالة الاستخدام والاعتماد'}</Link>
        <Link to="/privacy">{isEnglish ? 'Privacy' : 'الخصوصية'}</Link>
        <Link to="/terms">{isEnglish ? 'Terms of use' : 'شروط الاستخدام'}</Link>
      </div>
    </div>
  );
}
