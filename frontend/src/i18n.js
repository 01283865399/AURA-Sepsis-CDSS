import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

const resources = {
  ar: { translation: {
    brand: 'MediMind AI · منصة طبية بحثية', assistant: 'المساعد الطبي', home: 'الرئيسية', dashboard: 'لوحة المتابعة', models: 'النماذج', history: 'سجل الفحوصات', labs: 'المختبر', profile: 'الإعدادات', about: 'عن المنصة', patients: 'المرضى',
    online: 'متصل', offline: 'غير متصل', connecting: 'جارٍ التحقق', light: 'الوضع الفاتح', dark: 'الوضع الداكن', language: 'English',
    welcome: 'مساحة عمل سريرية للبحث', researchOnly: 'بيئة بحثية · لا تستخدم كتشخيص مستقل', checks: 'فحوصات مسجلة محلياً', availableModels: 'مسارات متاحة', latest: 'أحدث الفحوصات', openModel: 'فتح النموذج', runAnalysis: 'تشغيل التحليل', clear: 'مسح السجل', search: 'بحث في النماذج والفحوصات',
    disclaimerTitle: 'تنبيه الاستخدام', disclaimer: 'مخرجات النماذج تقديرات بحثية غير معتمدة سريرياً. ليست تشخيصاً أو توصية علاجية، ولا تغني عن تقييم مختص. لا تدخل بيانات تعريفية أو معلومات مرضى حقيقية.',
    submit: 'تحليل البيانات', reset: 'إعادة ضبط', loading: 'جارٍ التحليل', result: 'نتيجة النموذج', noResults: 'لا توجد فحوصات محفوظة بعد', localHistory: 'السجل محفوظ في هذا المتصفح فقط، ولا يتضمن قيم المدخلات.', unsupported: 'Endpoint غير متاح في الخادم الحالي',
    profileLocal: 'التفضيلات محفوظة محلياً في هذا المتصفح. لا توجد خدمة حسابات أو JWT مهيأة في الـBackend.',
  } },
  en: { translation: {
    brand: 'MediMind AI · Medical research', assistant: 'Medical assistant', home: 'Home', dashboard: 'Dashboard', models: 'Models', history: 'History', labs: 'Labs', profile: 'Preferences', about: 'About', patients: 'Patients',
    online: 'Online', offline: 'Offline', connecting: 'Checking', light: 'Light mode', dark: 'Dark mode', language: 'العربية',
    welcome: 'Clinical research workspace', researchOnly: 'Research environment · not a standalone diagnosis', checks: 'Locally saved analyses', availableModels: 'Available routes', latest: 'Recent analyses', openModel: 'Open model', runAnalysis: 'Run analysis', clear: 'Clear history', search: 'Search models and analyses',
    disclaimerTitle: 'Use notice', disclaimer: 'Model outputs are research estimates and are not clinically validated. They are not a diagnosis or treatment recommendation and do not replace qualified review. Do not enter identifying or real patient data.',
    submit: 'Analyze data', reset: 'Reset', loading: 'Analyzing', result: 'Model result', noResults: 'No analyses saved yet', localHistory: 'History is stored only in this browser and excludes submitted values.', unsupported: 'Endpoint unavailable on the current server',
    profileLocal: 'Preferences are stored locally in this browser. No account or JWT service is configured in the backend.',
  } },
};

i18n.use(initReactI18next).init({
  resources,
  lng: 'ar',
  fallbackLng: 'ar',
  interpolation: { escapeValue: false },
  react: { useSuspense: false },
});

export default i18n;
