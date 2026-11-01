import React, { useEffect, useMemo, useRef, useState } from 'react';
import axios from 'axios';
import { Link, useNavigate, useParams } from 'react-router-dom';
import './dashboard.css';
import {
  Activity,
  AlertTriangle,
  ArrowLeft,
  ArrowUpRight,
  Check,
  CircleHelp,
  Clock3,
  Download,
  FlaskConical,
  Gauge,
  HeartPulse,
  LoaderCircle,
  Microscope,
  Radio,
  ShieldCheck,
  Stethoscope,
  Thermometer,
  Upload,
  UserRound,
  Wifi,
  WifiOff,
  Volume2,
  X,
} from 'lucide-react';

const API_URL = import.meta.env.VITE_CLINICAL_API_URL || 'http://127.0.0.1:8000';

const AR_TRANSLATIONS = {
  'MediMind AI dashboard': 'لوحة MediMind AI لدعم القرار البحثي',
  'Use and validation status': 'حالة الاستخدام والاعتماد',
  'Clinical decision support': 'دعم القرار السريري',
  'Connecting to API': 'جارٍ الاتصال بواجهة API',
  Online: 'متصل',
  Offline: 'غير متصل',
  'QUICK TEST PATIENTS': 'أمثلة سريعة للاختبار',
  'Illustrative values · model result may differ from the profile label': 'قيم توضيحية · قد تختلف نتيجة النموذج عن وصف المثال',
  'Acute shock example': 'مثال صدمة حادة',
  'High-risk profile': 'ملف خطورة مرتفعة',
  'Moderate example': 'مثال خطورة متوسطة',
  'Moderate-risk profile': 'ملف خطورة متوسطة',
  'Stable example': 'مثال مستقر',
  'Low-risk profile': 'ملف خطورة منخفضة',
  'Assessment and report ready': 'التقييم والتقرير جاهزان',
  'View report': 'عرض التقرير',
  'Live sensor simulation': 'محاكاة المستشعرات المباشرة',
  'Demo readings · not connected to bedside devices': 'قراءات تجريبية · غير متصلة بأجهزة المريض',
  Profile: 'الحالة',
  Stable: 'مستقر',
  Deteriorating: 'متدهور',
  'Stop stream': 'إيقاف البث',
  'Start live stream': 'بدء البث المباشر',
  'Polling every 3 seconds': 'تحديث كل 3 ثوانٍ',
  'Stream paused': 'البث متوقف مؤقتًا',
  'Last sample': 'آخر قراءة',
  'Audio alert armed': 'التنبيه الصوتي مفعّل',
  'Back to Patients Directory': 'العودة إلى قائمة المرضى',
  'Patient record not found.': 'لم يتم العثور على سجل المريض.',
  Bed: 'سرير',
  'Loading patient record…': 'جارٍ تحميل سجل المريض…',
  'This patient has no observations yet. Enter verified current measurements before running the model.': 'لا توجد مؤشرات مسجلة لهذا المريض بعد. أدخل القياسات الحالية التي تم التحقق منها قبل تشغيل النموذج.',
  'Patient condition is critical.': 'الحالة في خطر.',
  'The patient condition is critical.': 'حالة المريض في خطر.',
  'Repeated siren and voice alert · close to silence': 'صفارة وتنبيه صوتي متكرران · أغلق لكتمهما',
  'Silence alarm': 'كتم التنبيه',
  'Sensor simulation or prediction request failed.': 'فشل طلب محاكاة المستشعر أو التنبؤ.',
  'ICU · EARLY WARNING': 'العناية المركزة · إنذار مبكر',
  'Sepsis risk assessment': 'تقييم مخاطر الإنتان',
  'Review patient observations, run the model, and inspect the factors behind its estimate.': 'راجع مؤشرات المريض وشغّل النموذج وافحص العوامل المؤثرة في تقديره.',
  'Decision support': 'دعم القرار',
  'Model-assisted': 'بمساعدة النموذج',
  'PATIENT ASSESSMENT': 'تقييم المريض',
  'Clinical observations': 'المؤشرات السريرية',
  'Enter current values to generate an estimate.': 'أدخل القيم الحالية للحصول على تقدير.',
  'Reference ranges are general adult guides, not patient-specific targets.': 'النطاقات المرجعية إرشادية عامة للبالغين وليست أهدافًا خاصة بالمريض.',
  'About reference ranges': 'حول النطاقات المرجعية',
  'Illustrative inputs · model output may differ': 'مدخلات توضيحية · قد تختلف نتيجة النموذج',
  'Vital signs': 'العلامات الحيوية',
  'Bedside observations': 'ملاحظات سريرية',
  'Patient profile': 'ملف المريض',
  'Demographics and ICU stay': 'البيانات الديموغرافية ومدة العناية المركزة',
  Laboratory: 'الفحوصات المخبرية',
  'Latest available results': 'أحدث النتائج المتاحة',
  'Heart rate': 'معدل ضربات القلب',
  'Oxygen saturation': 'تشبع الأكسجين',
  Temperature: 'درجة الحرارة',
  'Systolic BP': 'ضغط الدم الانقباضي',
  'Diastolic BP': 'ضغط الدم الانبساطي',
  'Mean arterial pressure': 'متوسط الضغط الشرياني',
  'Respiratory rate': 'معدل التنفس',
  Age: 'العمر',
  'ICU length of stay': 'مدة الإقامة بالعناية المركزة',
  'White blood cells': 'كريات الدم البيضاء',
  Platelets: 'الصفائح الدموية',
  years: 'سنة',
  'Adult reference': 'مرجع البالغين',
  'Time in current ICU stay': 'الوقت منذ دخول العناية المركزة',
  'Female': 'أنثى',
  Male: 'ذكر',
  Guide: 'إرشادي',
  'Run AI diagnostics': 'تشغيل تحليل النموذج',
  'Analyzing patient data…': 'جارٍ تحليل بيانات المريض…',
  'For clinical decision support only. Use alongside clinician judgment.': 'لدعم القرار السريري فقط. استخدمه إلى جانب التقدير الطبي المختص.',
  '02 · MODEL OUTPUT': '02 · ناتج النموذج',
  'Assessment complete': 'اكتمل التقييم',
  'Awaiting assessment': 'بانتظار التقييم',
  'Sepsis risk': 'مخاطر الإنتان',
  'Uncalibrated model score': 'درجة نموذج غير معايرة',
  'No assessment': 'لا يوجد تقييم',
  'MODEL': 'النموذج',
  SCORE: 'الدرجة',
  'Input completeness': 'اكتمال المدخلات',
  'Model score': 'درجة النموذج',
  '{percent}% ({provided}/{required} model features supplied); {imputed} values imputed.': '{percent}% ({provided}/{required} مؤشرًا من النموذج أُدخلت)؛ تم تقدير {imputed} قيمة.',
  'Exploratory model spread: {lower}–{upper}%. Not a calibrated confidence interval or clinical probability range.': 'نطاق تفاوت النموذج الاستكشافي: {lower}–{upper}%. ليس فاصل ثقة معايرًا ولا نطاق احتمال سريريًا.',
  'Risk bands are project settings and are not clinically validated.': 'حدود مستويات الخطورة إعدادات للمشروع ولم يتم التحقق منها سريريًا.',
  'CLINICAL ACTION': 'الإجراء السريري',
  'Model output is not a diagnosis or treatment instruction.': 'ناتج النموذج ليس تشخيصًا أو تعليمات علاجية.',
  'High': 'مرتفع',
  'Medium': 'متوسط',
  'Low': 'منخفض',
  'High Risk': 'خطورة مرتفعة',
  'Moderate Risk': 'خطورة متوسطة',
  'Low Risk': 'خطورة منخفضة',
  '03 · EXPLAINABLE AI · SHAP': '03 · الذكاء الاصطناعي القابل للتفسير · SHAP',
  'What influenced this result?': 'ما العوامل التي أثرت في هذه النتيجة؟',
  'Five strongest feature contributions from the model.': 'أقوى خمسة مؤشرات ساهمت في ناتج النموذج.',
  'Increases model risk': 'يرفع خطورة النموذج',
  'Decreases model risk': 'يخفض خطورة النموذج',
  'Relative magnitude': 'الحجم النسبي للتأثير',
  'Insights appear after assessment': 'تظهر التفاصيل بعد التقييم',
  'Run the model to see which patient features contributed most to its estimate.': 'شغّل النموذج لمعرفة مؤشرات المريض الأكثر مساهمة في تقديره.',
  'SHAP describes model contribution, not clinical causation.': 'توضح SHAP مساهمة المؤشر في ناتج النموذج ولا تثبت علاقة سببية سريرية.',
  REPORT: 'التقرير',
  'Share a printable patient summary': 'مشاركة ملخص المريض القابل للطباعة',
  'Export patient report': 'تصدير تقرير المريض',
  '04 · IMAGE INTAKE': '04 · إدخال الصورة',
  'Medical image preview': 'معاينة الصورة الطبية',
  'Upload a supported image for file validation and preview.': 'ارفع صورة مدعومة للتحقق منها ومعاينتها.',
  'Image type': 'نوع الصورة',
  'Auto / unknown': 'تلقائي / غير معروف',
  'Chest X-ray': 'أشعة سينية للصدر',
  'Lab report (OCR)': 'تقرير مختبر (OCR)',
  'Drop an image here or browse': 'أفلت الصورة هنا أو اخترها',
  'up to 10 MB': 'حتى 10 ميغابايت',
  'Remove selected image': 'إزالة الصورة المحددة',
  'Checking image…': 'جارٍ فحص الصورة…',
  'Validate image file': 'التحقق من ملف الصورة',
  'Image preview': 'معاينة الصورة',
  'Image checked': 'تم فحص الصورة',
  Findings: 'النتائج',
  'Not interpreted': 'لم يتم تفسيرها',
  'Infection site': 'موضع العدوى',
  'Not identified': 'لم يتم تحديده',
  'Normalized screening score': 'درجة الفحص المعيارية',
  'Target model scores · 0–100 normalized scale': 'درجات الفئات · مقياس معياري من 0 إلى 100',
  'OCR candidate values · verify against source': 'قيم OCR المرشحة · تحقق منها بمقارنتها بالمصدر',
  'OCR-only model preview': 'معاينة النموذج باستخدام OCR فقط',
  'Not merged into current patient assessment.': 'لم تُدمج في تقييم المريض الحالي.',
  'Apply OCR candidates to form': 'إضافة قيم OCR المرشحة إلى النموذج',
  'Image output is not a diagnosis and does not automatically alter the patient’s sepsis prediction.': 'نتيجة الصورة ليست تشخيصًا ولا تغيّر تلقائيًا توقع الإنتان للمريض.',
  'OCR requires the optional EasyOCR/Tesseract dependencies. This project has no validated chest X-ray classifier.': 'يتطلب OCR مكتبات EasyOCR أو Tesseract الاختيارية. لا يحتوي المشروع على مصنف أشعة صدر تم التحقق منه.',
  'OCR candidates ready for review': 'قيم OCR المرشحة جاهزة للمراجعة',
  'OCR engine unavailable': 'محرك OCR غير متاح',
  'No supported lab values found': 'لم يتم العثور على قيم مختبر مدعومة',
  'X-ray screening complete · review required': 'اكتمل فحص الأشعة · يلزم التحقق',
  'X-ray model unavailable': 'نموذج الأشعة غير متاح',
  'Image type not recognized': 'نوع الصورة غير معروف',
  'Image preview validated': 'تم التحقق من معاينة الصورة',
  '05 · STRUCTURED REPORT · PDF': '05 · تقرير منظم · PDF',
  'Comprehensive decision-support summary': 'ملخص شامل لدعم القرار',
  'Recomputed from current values and SHAP on the API.': 'أُعيد حسابه من القيم الحالية ومؤشرات SHAP عبر API.',
  'Model result': 'نتيجة النموذج',
  'Image review': 'مراجعة الصورة',
  'X-ray screening result': 'نتيجة فحص الأشعة',
  'OCR candidates extracted': 'تم استخراج قيم مرشحة بواسطة OCR',
  'Preview only · no findings': 'معاينة فقط · لا نتائج',
  'Not provided': 'غير مرفق',
  Diagnosis: 'التشخيص',
  'Not generated': 'لم يتم إنشاؤه',
  'RISK-BASED GUIDANCE': 'إرشادات حسب مستوى الخطورة',
  'Immediate Medical Action Bundle': 'الإجراءات الطبية الفورية',
  'Lab & Imaging Follow-up': 'متابعة المختبر والتصوير',
  'Generating PDF…': 'جارٍ إنشاء PDF…',
  'Export CDS report (PDF)': 'تصدير تقرير دعم القرار (PDF)',
  'Clinical decision support · Verify all outputs against the patient record': 'دعم القرار السريري · تحقق من النتائج بمقارنتها بسجل المريض',
  'Urgent simulated alert · demo only': 'تنبيه عاجل محاكى · للعرض فقط',
  'Model estimate is above 60%. Follow local clinical escalation procedures; this is not a validated bedside alarm.': 'تقدير النموذج أعلى من 60%. اتبع إجراءات التصعيد المحلية؛ هذا ليس إنذارًا سريريًا تم التحقق منه.',
  'Dismiss alert': 'إغلاق التنبيه',
  'Printable patient assessment report': 'تقرير تقييم المريض القابل للطباعة',
  Generated: 'تاريخ الإنشاء',
  'Patient summary & admission context': 'ملخص المريض وسياق الدخول',
  'Admission context': 'سياق الدخول',
  'Real-time vital signs & lab biomarkers': 'العلامات الحيوية والمؤشرات المخبرية',
  Measurement: 'القياس',
  Value: 'القيمة',
  'General reference': 'المرجع العام',
  Context: 'السياق',
  'Not specified': 'غير محدد',
  'Context only': 'للسياق فقط',
  'Sepsis risk score & AI probability': 'درجة مخاطر الإنتان واحتمال النموذج',
  'Model estimate': 'تقدير النموذج',
  'Explainable AI insights · SHAP': 'رؤى الذكاء الاصطناعي القابل للتفسير · SHAP',
  'Medical image / X-ray review': 'مراجعة الصورة الطبية / الأشعة',
  'Technical preview:': 'معاينة تقنية:',
  'This is file metadata, not an image finding.': 'هذه بيانات الملف وليست نتيجة لتفسير الصورة.',
  'Screening model:': 'نموذج الفحص:',
  'Infection site:': 'موضع العدوى:',
  'Normalized screening score:': 'درجة الفحص المعيارية:',
  'Target class scores · normalized operating-point scale': 'درجات الفئات المستهدفة · مقياس معياري',
  'No image was supplied for review.': 'لم تُرفق صورة للمراجعة.',
  'Clinical impression': 'الانطباع السريري',
  'Clinical recommendations ·': 'التوصيات السريرية ·',
  'Enter the latest patient observations and run an assessment to view decision support.': 'أدخل أحدث مؤشرات المريض وشغّل التقييم لعرض دعم القرار.',
  'Prompt bedside reassessment is warranted. Review the patient’s full clinical picture and follow your institution’s sepsis escalation protocol.': 'يلزم إعادة تقييم المريض سريعًا. راجع الحالة السريرية كاملة واتبع بروتوكول مؤسستك للتصعيد عند الإنتان.',
  'Review current observations and trends with the care team. Consider reassessment based on clinical context and local protocol.': 'راجع المؤشرات الحالية واتجاهاتها مع فريق الرعاية، وفكّر في إعادة التقييم وفق السياق السريري والبروتوكول المحلي.',
  'No elevated model signal at this time. Continue routine monitoring and reassess if the patient’s condition changes.': 'لا توجد حاليًا إشارة مرتفعة من النموذج. واصل المراقبة المعتادة وأعد التقييم عند تغير حالة المريض.',
  'The PDF could not be generated. Check the API and try again.': 'تعذر إنشاء PDF. تحقق من اتصال API وحاول مجددًا.',
  'The server returned an invalid PDF response.': 'أعاد الخادم استجابة PDF غير صالحة.',
  'The report could not be generated. Check the API connection and try again.': 'تعذر إنشاء التقرير. تحقق من اتصال API وحاول مجددًا.',
  'Could not reach the prediction service. Check that the API is running, then try again.': 'تعذر الوصول إلى خدمة التنبؤ. تحقق من تشغيل API ثم حاول مجددًا.',
  'OCR found candidate laboratory/vital values. Verify every value and unit against the original report before clinical use.': 'استخرج OCR قيمًا مرشحة. تحقق من كل قيمة ووحدة بمقارنتها بالتقرير الأصلي قبل أي استخدام سريري.',
  'Confirm each extracted value and unit against the source report before using it.': 'تحقق من كل قيمة ووحدة مستخرجة بمقارنتها بالتقرير الأصلي قبل استخدامها.',
  'The image was validated, but lab-report OCR could not run in this environment. No values were extracted.': 'تم التحقق من الصورة، لكن تعذر تشغيل OCR في هذه البيئة ولم تُستخرج قيم.',
  'Check image orientation, legibility, and whether the selected type matches the file.': 'تحقق من اتجاه الصورة ووضوحها ومن تطابق النوع المحدد مع الملف.',
  'Validate image': 'التحقق من الصورة',
  'Preset patient examples': 'أمثلة مرضى جاهزة',
  ' loaded': ' تم تحميله',
  'A risk estimate is not a diagnosis or a treatment recommendation.': 'تقدير الخطورة ليس تشخيصًا أو توصية علاجية.',
  'Vitals, model output, and SHAP summary': 'المؤشرات الحيوية وناتج النموذج وملخص SHAP',
  'Age and stay context only; not a diagnosis.': 'العمر وسياق الإقامة فقط؛ وليس تشخيصًا.',
  'REPORT SUMMARY': 'ملخص التقرير',
  'No report generated': 'لم يتم إنشاء تقرير',
  'Not assessed': 'لم يتم التقييم',
  'RECOMMENDATIONS': 'التوصيات',
  'VIEW DETAILS': 'عرض التفاصيل',
  'Close': 'إغلاق',
  'No value': 'لا توجد قيمة',
  '4.0–11.0 ×10⁹/L': '4.0–11.0 ×10⁹/لتر',
  '150–400 ×10⁹/L': '150–400 ×10⁹/لتر',
  '60–100 bpm': '60–100 نبضة/دقيقة',
  '94–100%': '94–100%',
  '36.5–37.5 °C': '36.5–37.5 °م',
  '90–120 mmHg': '90–120 ملم زئبق',
  '60–80 mmHg': '60–80 ملم زئبق',
  '70–100 mmHg': '70–100 ملم زئبق',
  '12–20 /min': '12–20 /دقيقة',
  'Acute shock example loaded': 'تم تحميل مثال الصدمة الحادة',
  'Moderate example loaded': 'تم تحميل المثال متوسط الخطورة',
  'Stable example loaded': 'تم تحميل المثال المستقر',
  'increases': 'يزيد',
  'decreases': 'يخفض',
  'No contribution data available.': 'لا تتوفر بيانات للمساهمات.',
  "Configured model-score bands: Low <{medium}, Moderate {medium}–<{high}, High ≥{high}. These thresholds are not clinically validated.": 'حدود درجات النموذج: منخفضة أقل من {medium}، متوسطة من {medium} إلى أقل من {high}، مرتفعة {high} فأعلى. لم يتم التحقق من هذه الحدود سريريًا.',
  'Request prompt in-person review by the treating clinician and verify the current observations against the patient record.': 'اطلب مراجعة مباشرة وسريعة من الطبيب المعالج وتحقق من المؤشرات الحالية بمقارنتها بسجل المريض.',
  "If clinical concern is present, follow the institution's sepsis screening and escalation pathway.": 'إذا وُجد قلق سريري، فاتبع مسار مؤسستك لفحص الإنتان والتصعيد.',
  'Clinical monitoring and any further actions remain the responsibility of the treating team.': 'تظل المراقبة السريرية وأي إجراءات إضافية مسؤولية فريق الرعاية المعالج.',
  'Review available CBC, metabolic results, lactate, and cultures in their clinical context; repeat or order tests only when directed by the treating clinician or local protocol.': 'راجع نتائج تعداد الدم الكامل والفحوصات الاستقلابية واللاكتات والمزارع في سياقها السريري؛ ولا تكرر الفحوصات أو تطلبها إلا بتوجيه الطبيب المعالج أو البروتوكول المحلي.',
  "Arrange timely clinician review and compare the current observations with the patient's baseline and recent trend.": 'رتّب مراجعة الطبيب في الوقت المناسب وقارن المؤشرات الحالية بخط الأساس والاتجاهات الحديثة للمريض.',
  'Escalate according to local protocol if the patient is deteriorating or the treating team is concerned.': 'صعّد الرعاية وفق البروتوكول المحلي إذا تدهورت حالة المريض أو كان فريق الرعاية قلقًا.',
  'Review recent laboratory results and trends; repeat testing only when clinically indicated by the treating team or local protocol.': 'راجع نتائج المختبر الحديثة واتجاهاتها؛ ولا تكرر الفحوصات إلا عند وجود داعٍ سريري يحدده فريق الرعاية أو البروتوكول المحلي.',
  "No immediate action is inferred from this model score alone; continue the clinician's existing monitoring plan.": 'لا تُستنتج حاجة إلى إجراء فوري من درجة النموذج وحدها؛ واصل خطة المراقبة التي وضعها الطبيب.',
  "Reassess promptly if the patient's condition changes or clinical concern persists despite a low model estimate.": 'أعد التقييم سريعًا إذا تغيرت حالة المريض أو استمر القلق السريري رغم انخفاض تقدير النموذج.',
  "No automatic repeat testing is recommended by this report; follow the existing clinical plan and local protocol.": 'لا يوصي هذا التقرير تلقائيًا بتكرار الفحوصات؛ اتبع الخطة السريرية الحالية والبروتوكول المحلي.',
  'The chest X-ray model flagged a screening finding; obtain qualified radiology review and correlate clinically. This result does not confirm an infection source or prescribe treatment.': 'رصد نموذج الأشعة السينية للصدر مؤشرًا يستدعي الفحص؛ اطلب مراجعة اختصاصي أشعة مؤهل واربط النتيجة بالسياق السريري. لا تؤكد هذه النتيجة مصدر عدوى ولا تصف علاجًا.',
  'The uploaded image was validated for preview only. No imaging findings or infection site are available; obtain qualified radiology or clinician review if imaging is clinically indicated.': 'تم التحقق من الصورة المرفوعة للمعاينة فقط. لا تتوفر نتائج تصوير أو موضع عدوى؛ اطلب مراجعة اختصاصي أشعة أو طبيب مؤهل إذا كان التصوير مطلوبًا سريريًا.',
  'OCR produced candidate lab values only. Verify them against the source report; no radiological interpretation was performed.': 'استخرج OCR قيمًا مخبرية مرشحة فقط. تحقق منها بمقارنتها بالتقرير الأصلي؛ لم يتم إجراء تفسير إشعاعي.',
  'No laboratory values were extracted. Review the image manually and verify any transcribed values against the source document.': 'لم يتم استخراج قيم مخبرية. راجع الصورة يدويًا وتحقق من أي قيم منسوخة بمقارنتها بالمستند الأصلي.',
  'No image was attached; imaging should be considered only by the treating clinician when clinically indicated.': 'لم تُرفق صورة؛ وينبغي أن يقرر الطبيب المعالج إجراء التصوير عند وجود داعٍ سريري فقط.',
  'For clinician review only. This software does not diagnose, order tests, or prescribe treatment. Verify the record and use clinical judgment and local protocols.': 'لمراجعة الطبيب فقط. لا يشخّص هذا البرنامج ولا يطلب الفحوصات أو يصف العلاج. تحقق من السجل واستخدم الحكم السريري والبروتوكولات المحلية.',
  'For research and decision-support review only. Not an official record, diagnosis, or treatment order. Not validated for autonomous monitoring or treatment decisions.': 'للبحث ومراجعة دعم القرار فقط. ليس سجلًا رسميًا أو تشخيصًا أو أمرًا علاجيًا. لم يتم التحقق منه للمراقبة أو قرارات العلاج المستقلة.',
  'Model estimate only. It is not a diagnosis and must be interpreted by a qualified clinician.': 'تقدير النموذج فقط. ليس تشخيصًا ويجب أن يفسره طبيب مؤهل.',
  'Feature contributions describe model behavior, not clinical causation.': 'توضح مساهمات المؤشرات سلوك النموذج ولا تثبت علاقة سببية سريرية.',
  'No final clinical diagnosis is generated by this decision-support report.': 'لا يصدر هذا التقرير الداعم للقرار تشخيصًا سريريًا نهائيًا.',
  'Ranges are broad adult references for context only; they are not patient-specific targets or clinical interpretation.': 'النطاقات مراجع عامة للبالغين للسياق فقط؛ وليست أهدافًا خاصة بالمريض أو تفسيرًا سريريًا.',
  'ICU monitoring context supplied by the operator; not independently verified.': 'سياق مراقبة العناية المركزة أدخله المشغّل ولم يتم التحقق منه بشكل مستقل.',
  'within broad reference': 'ضمن النطاق المرجعي العام',
  'outside broad reference': 'خارج النطاق المرجعي العام',
  'A screening-model result was supplied; verify it with a radiologist.': 'تم تقديم نتيجة نموذج فحص؛ تحقق منها مع اختصاصي أشعة.',
  'No validated chest X-ray classifier is installed; no radiological findings or infection source were identified.': 'لا يوجد مصنف أشعة صدر تم التحقق منه؛ ولم يتم تحديد نتائج إشعاعية أو مصدر للعدوى.',
  'OCR could not run in this environment. No laboratory values were extracted.': 'تعذر تشغيل OCR في هذه البيئة. لم يتم استخراج قيم مخبرية.',
  'The image was validated, but no supported labeled lab values were extracted and no X-ray classification was performed.': 'تم التحقق من الصورة، لكن لم يتم استخراج قيم مخبرية معنونة مدعومة ولم يتم تصنيف الأشعة.',
  'No medical image was supplied for review.': 'لم يتم تقديم صورة طبية للمراجعة.',
  'No imaging interpretation or recommendation is available because no image was supplied.': 'لا يتوفر تفسير أو توصية للتصوير لعدم تقديم صورة.',
  'No image validation was provided. No imaging diagnosis was generated.': 'لم يتم تقديم تحقق للصورة. لم يصدر تشخيص للتصوير.',
  'Install the optional Python dependency from backend/requirements-ocr.txt and the Tesseract OCR executable, then restart the API.': 'ثبّت مكتبة Python الاختيارية من backend/requirements-ocr.txt وبرنامج Tesseract OCR ثم أعد تشغيل API.',
  'Obtain qualified radiology review and correlate the image with clinical context.': 'اطلب مراجعة اختصاصي أشعة مؤهل واربط الصورة بالسياق السريري.',
  'No diagnosis or medication recommendation was generated from the image.': 'لم يصدر تشخيص أو توصية دوائية اعتمادًا على الصورة.',
  'Review the image manually and verify any transcribed values against the source document.': 'راجع الصورة يدويًا وتحقق من أي قيم منسوخة بمقارنتها بالمستند الأصلي.',
  'OCR extracted candidate laboratory values only. Verify them against the original report; they do not constitute a diagnosis.': 'استخرج OCR قيمًا مخبرية مرشحة فقط. تحقق منها بمقارنتها بالتقرير الأصلي؛ فهي لا تشكل تشخيصًا.',
  'Any model estimate from OCR values is a separate preview and must be reviewed by the treating clinician.': 'أي تقدير للنموذج من قيم OCR هو معاينة منفصلة ويجب أن يراجعه الطبيب المعالج.',
  'IMAGE INTAKE': 'إدخال الصورة',
  'STRUCTURED REPORT · PDF': 'تقرير منظم · PDF',
  'MediMind AI - Comprehensive Clinical Decision Support Summary': 'MediMind AI - ملخص شامل لدعم القرار البحثي',
  'Uncalibrated model score; do not interpret as a calibrated individual disease probability.': 'درجة نموذج غير معايرة؛ لا تفسرها على أنها احتمال فردي معاير للإصابة بالمرض.',
  'This is exploratory disagreement among cross-validation fold models, not a calibrated statistical confidence interval or a clinically validated probability interval.': 'هذا تباين استكشافي بين نماذج طيات التحقق المتقاطع، وليس فاصل ثقة إحصائيًا معايرًا أو نطاق احتمال تم التحقق منه سريريًا.',
  'For clinician review only. This model output is not a diagnosis, is not a treatment recommendation, and must not replace clinical judgment or local protocols. The model and thresholds have not been clinically validated.': 'لمراجعة الطبيب فقط. ناتج هذا النموذج ليس تشخيصًا ولا توصية علاجية، ويجب ألا يحل محل الحكم السريري أو البروتوكولات المحلية. لم يتم التحقق السريري من النموذج أو حدوده.',
  'The image could not be checked. Confirm the API is running and try again.': 'تعذر فحص الصورة. تحقق من تشغيل API ثم حاول مجددًا.',
  'Choose a JPEG, PNG, WEBP, BMP, or TIFF image. DICOM and PDF files are not supported.': 'اختر صورة JPEG أو PNG أو WEBP أو BMP أو TIFF. ملفات DICOM وPDF غير مدعومة.',
  'Image exceeds the 10 MB upload limit.': 'يتجاوز حجم الصورة حد الرفع البالغ 10 ميغابايت.',
  'This is separate from the patient assessment.': 'هذه نتيجة منفصلة عن تقييم المريض.',
  'Image review recommendations': 'توصيات مراجعة الصورة',
  'Estimated probability': 'الاحتمال المقدّر',
  'Patient observations': 'مؤشرات المريض',
  'Clinical action support': 'دعم الإجراء السريري',
  'Top model contributions (SHAP)': 'أبرز مساهمات النموذج (SHAP)',
  'model output': 'ناتج النموذج',
  'model risk': 'خطورة النموذج',
  'CLINICAL DECISION SUPPORT REPORT': 'تقرير دعم القرار السريري',
  'Research use · not clinically validated · not an official record or diagnosis. Scores are uncalibrated and must not be used alone for care decisions. Verify data and discuss any result with a qualified clinician. SHAP describes model contribution, not causation; completeness and model spread are not confidence measures.': 'للاستخدام البحثي · لم يتم التحقق السريري · ليس سجلًا رسميًا أو تشخيصًا. الدرجات غير معايرة ولا تستخدم منفردة لقرارات الرعاية. تحقّق من البيانات وناقش النتائج مع طبيب مؤهل. توضح SHAP مساهمة النموذج ولا تثبت السببية؛ واكتمال البيانات وتفاوت النموذج ليسا مقياسي ثقة.',
  'Clinically approved status · decision support, not an official record or diagnosis. Scores are uncalibrated and must not be used alone for care decisions. Verify data and discuss any result with a qualified clinician. SHAP describes model contribution, not causation; completeness and model spread are not confidence measures.': 'حالة الاعتماد السريري: معتمد · دعم قرار وليس سجلًا رسميًا أو تشخيصًا. الدرجات غير معايرة ولا تستخدم منفردة لقرارات الرعاية. تحقّق من البيانات وناقش النتائج مع طبيب مؤهل. توضح SHAP مساهمة النموذج ولا تثبت السببية؛ واكتمال البيانات وتفاوت النموذج ليسا مقياسي ثقة.',
  'Clinical status unavailable · do not treat an estimate as a diagnosis.': 'حالة الاعتماد غير متاحة · لا تعتبر التقدير تشخيصًا.',
  'Choose how to export this report': 'اختر طريقة تصدير هذا التقرير',
  'Patient report': 'تقرير المريض',
  'Clinical decision support report': 'تقرير دعم القرار السريري',
  'Print report': 'طباعة التقرير',
  'Download PDF': 'تنزيل PDF',
  'Cancel': 'إلغاء',
  'Report language': 'لغة التقرير',
  'Arabic': 'العربية',
  'English': 'الإنجليزية',
  'Preparing report…': 'جارٍ تجهيز التقرير…',
  'No image was provided for review.': 'لم يتم تقديم صورة للمراجعة.',
};

const FEATURE_TRANSLATIONS = {
  HR: 'معدل ضربات القلب',
  O2Sat: 'تشبع الأكسجين',
  Temp: 'درجة الحرارة',
  SBP: 'ضغط الدم الانقباضي',
  MAP: 'متوسط الضغط الشرياني',
  DBP: 'ضغط الدم الانبساطي',
  Resp: 'معدل التنفس',
  Age: 'العمر',
  Gender: 'الجنس',
  ICULOS: 'مدة الإقامة بالعناية المركزة',
  WBC: 'كريات الدم البيضاء',
  Platelets: 'الصفائح الدموية',
  EtCO2: 'ثاني أكسيد الكربون بنهاية الزفير',
  BaseExcess: 'فائض القاعدة',
  HCO3: 'البيكربونات',
  FiO2: 'الأكسجين المستنشق',
  pH: 'الأس الهيدروجيني',
  PaCO2: 'ضغط ثاني أكسيد الكربون الشرياني',
  SaO2: 'تشبع الأكسجين الشرياني',
  AST: 'إنزيم AST',
  BUN: 'نيتروجين يوريا الدم',
  Alkalinephos: 'الفوسفاتاز القلوي',
  Calcium: 'الكالسيوم',
  Chloride: 'الكلوريد',
  Creatinine: 'الكرياتينين',
  Bilirubin_direct: 'البيليروبين المباشر',
  Glucose: 'الجلوكوز',
  Lactate: 'اللاكتات',
  Magnesium: 'المغنيسيوم',
  Phosphate: 'الفوسفات',
  Potassium: 'البوتاسيوم',
  Bilirubin_total: 'البيليروبين الكلي',
  TroponinI: 'التروبونين I',
  Hct: 'الهيماتوكريت',
  Hgb: 'الهيموجلوبين',
  PTT: 'زمن الثرومبوبلاستين الجزئي',
  Fibrinogen: 'الفيبرينوجين',
  Unit1: 'نوع وحدة العناية 1',
  Unit2: 'نوع وحدة العناية 2',
  HospAdmTime: 'الوقت منذ دخول المستشفى',
};

const DEFAULT_FORM = {
  HR: 88,
  O2Sat: 94,
  Temp: 38.1,
  SBP: 102,
  MAP: 69,
  DBP: 58,
  Resp: 22,
  Age: 68,
  Gender: 1,
  ICULOS: 18,
  WBC: 14.5,
  Platelets: 135,
};

const EMPTY_PATIENT_FORM = Object.fromEntries(
  Object.keys(DEFAULT_FORM).map((key) => [key, '']),
);

const QUICK_PATIENTS = [
  {
    id: 'acute-shock',
    title: 'Acute shock example',
    target: 'High-risk profile',
    values: { HR: 135, Temp: 39.8, SBP: 78, WBC: 22.5, O2Sat: 88, Resp: 32 },
  },
  {
    id: 'moderate',
    title: 'Moderate example',
    target: 'Moderate-risk profile',
    values: { HR: 105, Temp: 38.2, SBP: 110, WBC: 13.5, O2Sat: 94, Resp: 22 },
  },
  {
    id: 'stable',
    title: 'Stable example',
    target: 'Low-risk profile',
    values: { HR: 68, Temp: 36.6, SBP: 120, WBC: 6.5, O2Sat: 99, Resp: 15 },
  },
];

const GROUPS = [
  {
    title: 'Vital signs',
    subtitle: 'Bedside observations',
    icon: HeartPulse,
    fields: [
      { key: 'HR', label: 'Heart rate', unit: 'bpm', range: '60–100 bpm', icon: Activity, step: 1 },
      { key: 'O2Sat', label: 'Oxygen saturation', unit: '%', range: '94–100%', icon: Gauge, step: 1 },
      { key: 'Temp', label: 'Temperature', unit: '°C', range: '36.5–37.5 °C', icon: Thermometer, step: 0.1 },
      { key: 'SBP', label: 'Systolic BP', unit: 'mmHg', range: '90–120 mmHg', icon: Activity, step: 1 },
      { key: 'DBP', label: 'Diastolic BP', unit: 'mmHg', range: '60–80 mmHg', icon: Activity, step: 1 },
      { key: 'MAP', label: 'Mean arterial pressure', unit: 'mmHg', range: '70–100 mmHg', icon: Gauge, step: 1 },
      { key: 'Resp', label: 'Respiratory rate', unit: 'breaths/min', range: '12–20 /min', icon: Stethoscope, step: 1 },
    ],
  },
  {
    title: 'Patient profile',
    subtitle: 'Demographics and ICU stay',
    icon: UserRound,
    fields: [
      { key: 'Age', label: 'Age', unit: 'years', range: 'Adult reference', icon: UserRound, step: 1 },
      { key: 'ICULOS', label: 'ICU length of stay', unit: 'hours', range: 'Time in current ICU stay', icon: Clock3, step: 1 },
    ],
  },
  {
    title: 'Laboratory',
    subtitle: 'Latest available results',
    icon: FlaskConical,
    fields: [
      { key: 'WBC', label: 'White blood cells', unit: '×10⁹/L', range: '4.0–11.0 ×10⁹/L', icon: Microscope, step: 0.1 },
      { key: 'Platelets', label: 'Platelets', unit: '×10⁹/L', range: '150–400 ×10⁹/L', icon: FlaskConical, step: 1 },
    ],
  },
];

const FEATURE_NAMES = {
  HR: 'Heart rate',
  O2Sat: 'Oxygen saturation',
  Temp: 'Temperature',
  SBP: 'Systolic blood pressure',
  MAP: 'Mean arterial pressure',
  DBP: 'Diastolic blood pressure',
  Resp: 'Respiratory rate',
  Age: 'Age',
  Gender: 'Gender',
  ICULOS: 'ICU length of stay',
  WBC: 'White blood cells',
  Platelets: 'Platelets',
};

const IMAGE_STATUS_LABELS = {
  ocr_extracted: 'OCR candidates ready for review',
  ocr_unavailable: 'OCR engine unavailable',
  ocr_no_values: 'No supported lab values found',
  xray_analyzed: 'X-ray screening complete · review required',
  xray_model_unavailable: 'X-ray model unavailable',
  unrecognized_image: 'Image type not recognized',
  preview_only: 'Image preview validated',
};

function classifyRisk(probability, apiRisk) {
  if (apiRisk === 'High Risk') return 'High Risk';
  if (apiRisk === 'Moderate Risk') return 'Moderate Risk';
  if (apiRisk === 'Low Risk') return 'Low Risk';
  if (probability >= 0.7) return 'High Risk';
  if (probability >= 0.35) return 'Moderate Risk';
  return 'Low Risk';
}

function recommendationFor(risk, hasPrediction) {
  if (!hasPrediction) return 'Enter the latest patient observations and run an assessment to view decision support.';
  if (risk === 'High Risk') {
    return 'Prompt bedside reassessment is warranted. Review the patient’s full clinical picture and follow your institution’s sepsis escalation protocol.';
  }
  if (risk === 'Moderate Risk') {
    return 'Review current observations and trends with the care team. Consider reassessment based on clinical context and local protocol.';
  }
  return 'No elevated model signal at this time. Continue routine monitoring and reassess if the patient’s condition changes.';
}

function translateText(value, targetLanguage) {
  if (targetLanguage !== 'ar' || typeof value !== 'string') return value;
  const spreadMatch = value.match(/^Model spread: ([\d.]+)–([\d.]+)%\.$/);
  if (spreadMatch) return `نطاق تفاوت النموذج: ${spreadMatch[1]}–${spreadMatch[2]}%.`;
  return AR_TRANSLATIONS[value] || value;
}

function App() {
  const { patientId } = useParams();
  const navigate = useNavigate();
  const [language, setLanguage] = useState(() => {
    try {
      return window.localStorage.getItem('aura-language') === 'ar' ? 'ar' : 'en';
    } catch {
      return 'en';
    }
  });
  const t = (text) => translateText(text, language);
  const [form, setForm] = useState(DEFAULT_FORM);
  const [loading, setLoading] = useState(false);
  const [apiStatus, setApiStatus] = useState('Checking');
  const [clinicalStatus, setClinicalStatus] = useState('research_only');
  const [prediction, setPrediction] = useState(null);
  const [patientRecord, setPatientRecord] = useState(null);
  const [patientLoading, setPatientLoading] = useState(false);
  const [error, setError] = useState('');
  const [activePreset, setActivePreset] = useState('');
  const [liveEnabled, setLiveEnabled] = useState(false);
  const [sensorCondition, setSensorCondition] = useState('stable');
  const [sensorTimestamp, setSensorTimestamp] = useState('');
  const [sensorError, setSensorError] = useState('');
  const [urgentAlarm, setUrgentAlarm] = useState(false);
  const [imageFile, setImageFile] = useState(null);
  const [imageAnalysisType, setImageAnalysisType] = useState('auto');
  const [imagePreview, setImagePreview] = useState('');
  const [imageReport, setImageReport] = useState(null);
  const [imageError, setImageError] = useState('');
  const [imageLoading, setImageLoading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [fullReport, setFullReport] = useState(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [reportError, setReportError] = useState('');
  const [exportDialog, setExportDialog] = useState(null);
  const [exportLanguage, setExportLanguage] = useState(language);
  const [printRequest, setPrintRequest] = useState(null);
  const audioContextRef = useRef(null);
  const alarmActiveRef = useRef(false);
  const alarmDismissedRef = useRef(false);
  const stablePollCountRef = useRef(0);
  const alarmIntervalRef = useRef(null);
  const alarmSpeechTimeoutRef = useRef(null);
  const imageInputRef = useRef(null);
  const languageRef = useRef(language);
  languageRef.current = language;

  useEffect(() => {
    let active = true;
    setPatientLoading(true);
    setPatientRecord(null);
    setPrediction(null);
    setFullReport(null);
    setError('');
    setReportError('');
    setForm(EMPTY_PATIENT_FORM);

    axios.get(`${API_URL}/api/patients/${encodeURIComponent(patientId)}`, { timeout: 10000 })
      .then((response) => {
        if (!active) return;
        const patient = response.data;
        setPatientRecord(patient);
        setForm({ ...EMPTY_PATIENT_FORM, ...patient.vital_signs });
        setApiStatus('Online');
      })
      .catch((requestError) => {
        if (!active) return;
        const detail = requestError.response?.data?.detail;
        setError(typeof detail === 'string'
          ? t(detail)
          : t('Could not load this patient record. Check the API and return to the patient directory.'));
        setApiStatus('Offline');
      })
      .finally(() => {
        if (active) setPatientLoading(false);
      });

    return () => { active = false; };
  }, [patientId]);
  const clearAlarmAudio = () => {
    window.clearInterval(alarmIntervalRef.current);
    window.clearTimeout(alarmSpeechTimeoutRef.current);
    alarmIntervalRef.current = null;
    alarmSpeechTimeoutRef.current = null;
    if ('speechSynthesis' in window) window.speechSynthesis.cancel();
  };
  const playAmbulanceSiren = () => {
    const audioContext = audioContextRef.current;
    if (!audioContext || audioContext.state === 'closed') return;
    if (audioContext.state === 'suspended') void audioContext.resume();

    try {
      const now = audioContext.currentTime;
      const duration = 4.2;
      const oscillator = audioContext.createOscillator();
      const gain = audioContext.createGain();
      oscillator.type = 'sine';
      oscillator.frequency.setValueAtTime(650, now);
      for (let step = 0; step < 5; step += 1) {
        const start = now + step * 0.8;
        oscillator.frequency.linearRampToValueAtTime(1050, start + 0.4);
        oscillator.frequency.linearRampToValueAtTime(650, start + 0.8);
      }
      gain.gain.setValueAtTime(0.0001, now);
      gain.gain.linearRampToValueAtTime(0.12, now + 0.12);
      gain.gain.setValueAtTime(0.12, now + duration - 0.2);
      gain.gain.linearRampToValueAtTime(0.0001, now + duration);
      oscillator.connect(gain);
      gain.connect(audioContext.destination);
      oscillator.start(now);
      oscillator.stop(now + duration);
    } catch {
      // Keep the visual and spoken alert available if Web Audio is unavailable.
    }
  };
  const announceUrgentRisk = () => {
    if (!('speechSynthesis' in window) || !window.SpeechSynthesisUtterance) return;
    const isArabic = languageRef.current === 'ar';
    const announcement = new window.SpeechSynthesisUtterance(
      isArabic ? 'الحالة في خطر.' : 'The patient condition is critical.',
    );
    announcement.lang = isArabic ? 'ar-SA' : 'en-US';
    announcement.rate = 0.92;
    announcement.volume = 1;
    const preferredVoice = window.speechSynthesis.getVoices().find((voice) => (
      voice.lang.toLowerCase().startsWith(isArabic ? 'ar' : 'en')
    ));
    if (preferredVoice) announcement.voice = preferredVoice;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(announcement);
  };
  const runUrgentAlarmCycle = () => {
    if (!alarmActiveRef.current || alarmDismissedRef.current) return;
    playAmbulanceSiren();
    window.clearTimeout(alarmSpeechTimeoutRef.current);
    alarmSpeechTimeoutRef.current = window.setTimeout(() => {
      if (alarmActiveRef.current && !alarmDismissedRef.current) announceUrgentRisk();
    }, 4400);
  };
  const stopUrgentAlarm = (resetDismissal = true) => {
    alarmActiveRef.current = false;
    stablePollCountRef.current = 0;
    if (resetDismissal) alarmDismissedRef.current = false;
    clearAlarmAudio();
    setUrgentAlarm(false);
  };
  const observeRiskProbability = (riskProbability) => {
    if (riskProbability <= 0.6) {
      stablePollCountRef.current += 1;
      if (stablePollCountRef.current >= 3) stopUrgentAlarm();
      return;
    }

    stablePollCountRef.current = 0;
    if (alarmActiveRef.current || alarmDismissedRef.current) return;
    alarmActiveRef.current = true;
    setUrgentAlarm(true);
    runUrgentAlarmCycle();
    alarmIntervalRef.current = window.setInterval(runUrgentAlarmCycle, 12000);
  };

  useEffect(() => {
    const direction = language === 'ar' ? 'rtl' : 'ltr';
    document.documentElement.lang = language;
    document.documentElement.dir = direction;
    try {
      window.localStorage.setItem('aura-language', language);
    } catch {
      // Language selection still works for this page when storage is unavailable.
    }
  }, [language]);

  useEffect(() => {
    let mounted = true;
    axios.get(`${API_URL}/`, { timeout: 4000 })
      .then((response) => {
        if (!mounted) return;
        setApiStatus('Online');
        setClinicalStatus(response.data.clinical_status === 'approved' ? 'clinically_approved' : 'research_only');
      })
      .catch(() => mounted && setApiStatus('Offline'));
    return () => { mounted = false; };
  }, []);

  useEffect(() => {
    if (!liveEnabled) return undefined;

    let stopped = false;
    let polling = false;
    const pollSensors = async () => {
      if (polling) return;
      polling = true;
      try {
        const sensorResponse = await axios.get(`${API_URL}/simulate-sensor`, {
          params: { condition: sensorCondition },
          timeout: 5000,
        });
        if (stopped) return;

        const readings = sensorResponse.data.readings;
        setForm((previous) => ({ ...previous, ...readings }));
        setActivePreset('');
        setSensorTimestamp(sensorResponse.data.sampled_at);
        setSensorError('');

        const predictionResponse = await axios.post(`${API_URL}/predict`, readings, {
          headers: { 'Content-Type': 'application/json' },
          timeout: 10000,
        });
        if (!stopped) {
          setPrediction(predictionResponse.data);
          setApiStatus('Online');
          observeRiskProbability(Number(predictionResponse.data.sepsis_probability));
        }
      } catch (sensorRequestError) {
        if (!stopped) {
          setSensorError(sensorRequestError.response?.data?.detail || 'Sensor simulation or prediction request failed.');
          setApiStatus('Offline');
        }
      } finally {
        polling = false;
      }
    };

    void pollSensors();
    const interval = window.setInterval(pollSensors, 3000);
    return () => {
      stopped = true;
      window.clearInterval(interval);
    };
  }, [liveEnabled, sensorCondition]);

  useEffect(() => {
    if (!liveEnabled) stopUrgentAlarm();
    return undefined;
  }, [liveEnabled]);

  useEffect(() => {
    if (!imagePreview) return undefined;
    return () => URL.revokeObjectURL(imagePreview);
  }, [imagePreview]);

  useEffect(() => () => {
    clearAlarmAudio();
    if (audioContextRef.current) void audioContextRef.current.close();
  }, []);

  useEffect(() => {
    if (!printRequest) return undefined;
    const afterPrint = () => setPrintRequest(null);
    const timer = window.setTimeout(() => window.print(), 150);
    window.addEventListener('afterprint', afterPrint);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener('afterprint', afterPrint);
    };
  }, [printRequest]);

  const probability = Math.min(1, Math.max(0, Number(prediction?.sepsis_probability ?? 0)));
  const riskLevel = classifyRisk(probability, prediction?.risk_level);
  const deploymentStatus = prediction?.deployment_status
    || fullReport?.sepsis_assessment?.deployment_status
    || clinicalStatus;
  const provenanceNotice = deploymentStatus === 'clinically_approved'
    ? 'Clinically approved status · decision support, not an official record or diagnosis. Scores are uncalibrated and must not be used alone for care decisions. Verify data and discuss any result with a qualified clinician. SHAP describes model contribution, not causation; completeness and model spread are not confidence measures.'
    : deploymentStatus === 'research_only'
      ? 'Research use · not clinically validated · not an official record or diagnosis. Scores are uncalibrated and must not be used alone for care decisions. Verify data and discuss any result with a qualified clinician. SHAP describes model contribution, not causation; completeness and model spread are not confidence measures.'
      : 'Clinical status unavailable · do not treat an estimate as a diagnosis.';
  const riskThresholds = prediction?.risk_thresholds || { medium: 0.35, high: 0.7 };
  const factors = useMemo(() => {
    const entries = prediction?.top_contributing_factors;
    if (!Array.isArray(entries)) return [];
    const maxImpact = Math.max(...entries.map(({ impact }) => Math.abs(Number(impact) || 0)), 0.0001);
    return entries.slice(0, 5).map((item) => ({
      ...item,
      name: language === 'ar'
        ? FEATURE_TRANSLATIONS[item.feature] || FEATURE_NAMES[item.feature] || item.feature
        : FEATURE_NAMES[item.feature] || item.feature,
      width: `${Math.max(3, Math.abs(Number(item.impact) || 0) / maxImpact * 100)}%`,
    }));
  }, [language, prediction]);

  const runPreset = async (preset) => {
    const nextForm = { ...form, ...preset.values };
    const payload = Object.fromEntries(Object.entries(nextForm).map(([key, value]) => [key, Number(value)]));
    const imageValidation = imageReport ? {
      analysis_status: imageReport.analysis_status,
      analysis_type: imageReport.analysis_type,
      image_format: imageReport.image_format,
      image_dimensions: imageReport.image_dimensions,
      file_size_bytes: imageReport.file_size_bytes,
      extracted_vitals: imageReport.extracted_vitals,
      findings: imageReport.findings,
      infection_site: imageReport.infection_site,
      confidence_score: imageReport.confidence_score,
      confidence_note: imageReport.confidence_note,
      target_scores: imageReport.target_scores,
      clinical_summary: imageReport.clinical_summary,
      recommendations: imageReport.recommendations,
      model_name: imageReport.model_name,
    } : null;

    setForm(nextForm);
    setActivePreset(preset.id);
    setPrediction(null);
    setFullReport(null);
    setError('');
    setReportError('');
    setLoading(true);
    setReportLoading(true);

    const [predictionResult, reportResult] = await Promise.allSettled([
      axios.post(`${API_URL}/predict`, payload, {
        headers: { 'Content-Type': 'application/json' },
        timeout: 30000,
      }),
      axios.post(`${API_URL}/generate-full-report`, { vitals: payload, image_validation: imageValidation }, {
        headers: { 'Content-Type': 'application/json' },
        timeout: 30000,
      }),
    ]);

    if (predictionResult.status === 'fulfilled') {
      setPrediction(predictionResult.value.data);
      setApiStatus('Online');
    } else {
      setError(predictionResult.reason.response?.data?.detail || 'Could not reach the prediction service. Check that the API is running, then try again.');
      setApiStatus('Offline');
    }

    if (reportResult.status === 'fulfilled') {
      setFullReport(reportResult.value.data);
    } else {
      setReportError(reportResult.reason.response?.data?.detail || 'The report could not be generated. Check the API connection and try again.');
    }

    setLoading(false);
    setReportLoading(false);
  };

  const handleFieldChange = (event) => {
    const { name, value } = event.target;
    setForm((previous) => ({ ...previous, [name]: value === '' ? '' : Number(value) }));
    setActivePreset('');
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError('');
    try {
      const payload = Object.fromEntries(Object.entries(form).map(([key, value]) => [key, Number(value)]));
      const response = await axios.post(`${API_URL}/predict`, payload, {
        headers: { 'Content-Type': 'application/json' },
        timeout: 30000,
      });
      setPrediction(response.data);
      setApiStatus('Online');
    } catch (apiError) {
      setError(t(apiError.response?.data?.detail || 'Could not reach the prediction service. Check that the API is running, then try again.'));
      setApiStatus('Offline');
      setPrediction(null);
    } finally {
      setLoading(false);
    }
  };

  const toggleLiveStream = () => {
    if (liveEnabled) {
      setLiveEnabled(false);
      clearAlarmAudio();
      setUrgentAlarm(false);
      alarmActiveRef.current = false;
      alarmDismissedRef.current = false;
      stablePollCountRef.current = 0;
      return;
    }

    try {
      const AudioContextConstructor = window.AudioContext || window.webkitAudioContext;
      if (AudioContextConstructor) {
        audioContextRef.current = new AudioContextConstructor();
        void audioContextRef.current.resume();
      }
    } catch {
      audioContextRef.current = null;
    }
    alarmDismissedRef.current = false;
    setSensorError('');
    setLiveEnabled(true);
  };

  const dismissUrgentAlarm = () => {
    alarmDismissedRef.current = true;
    alarmActiveRef.current = false;
    clearAlarmAudio();
    setUrgentAlarm(false);
  };

  const selectImage = (file) => {
    if (!file) return;
    const supportedTypes = ['image/jpeg', 'image/png', 'image/webp', 'image/bmp', 'image/tiff'];
    if (!supportedTypes.includes(file.type)) {
      setImageError('Choose a JPEG, PNG, WEBP, BMP, or TIFF image. DICOM and PDF files are not supported.');
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setImageError('Image exceeds the 10 MB upload limit.');
      return;
    }
    setImageFile(file);
    setImagePreview(URL.createObjectURL(file));
    setImageReport(null);
    setImageError('');
  };

  const validateImage = async () => {
    if (!imageFile) return;
    setImageLoading(true);
    setImageError('');
    try {
      const response = await axios.post(`${API_URL}/analyze-medical-image`, imageFile, {
        headers: { 'Content-Type': imageFile.type },
        params: { analysis_type: imageAnalysisType },
        timeout: 15000,
      });
      setImageReport(response.data);
    } catch (imageRequestError) {
      setImageError(t(imageRequestError.response?.data?.detail || 'The image could not be checked. Confirm the API is running and try again.'));
      setImageReport(null);
    } finally {
      setImageLoading(false);
    }
  };

  const applyExtractedVitals = () => {
    const extractedVitals = imageReport?.extracted_vitals || {};
    if (!Object.keys(extractedVitals).length) return;
    setForm((previous) => ({ ...previous, ...extractedVitals }));
    setActivePreset('');
    setPrediction(null);
    setFullReport(null);
    setError('');
    setReportError('');
  };

  const getReportPayload = () => ({
    vitals: Object.fromEntries(Object.entries(form).map(([key, value]) => [key, Number(value)])),
    image_validation: imageReport ? {
      analysis_status: imageReport.analysis_status,
      analysis_type: imageReport.analysis_type,
      image_format: imageReport.image_format,
      image_dimensions: imageReport.image_dimensions,
      file_size_bytes: imageReport.file_size_bytes,
      extracted_vitals: imageReport.extracted_vitals,
      findings: imageReport.findings,
      infection_site: imageReport.infection_site,
      confidence_score: imageReport.confidence_score,
      confidence_note: imageReport.confidence_note,
      target_scores: imageReport.target_scores,
      model_name: imageReport.model_name,
      clinical_summary: imageReport.clinical_summary,
      recommendations: imageReport.recommendations,
    } : null,
  });

  const loadFullReport = async () => {
    const response = await axios.post(`${API_URL}/generate-full-report`, getReportPayload(), {
      headers: { 'Content-Type': 'application/json' },
      timeout: 30000,
    });
    const report = response.data;
    setFullReport(report);
    setPrediction({
      sepsis_prediction: report.sepsis_assessment.prediction,
      sepsis_probability: report.sepsis_assessment.model_probability,
      risk_level: report.sepsis_assessment.risk_level,
      risk_tier: report.sepsis_assessment.risk_tier,
      risk_thresholds: report.sepsis_assessment.risk_thresholds,
      deployment_status: report.sepsis_assessment.deployment_status,
      data_completeness: report.sepsis_assessment.data_completeness,
      model_uncertainty_interval: report.sepsis_assessment.model_uncertainty_interval,
      top_contributing_factors: report.explainable_ai.top_contributing_factors,
    });
    return report;
  };

  const downloadPdfBlob = (blob, filename) => {
    if (!blob.type.toLowerCase().startsWith('application/pdf')) {
      throw new Error('The server returned an invalid PDF response.');
    }
    const downloadUrl = URL.createObjectURL(blob);
    const downloadLink = document.createElement('a');
    downloadLink.href = downloadUrl;
    downloadLink.download = filename;
    downloadLink.style.display = 'none';
    document.body.appendChild(downloadLink);
    downloadLink.click();
    downloadLink.remove();
    window.setTimeout(() => URL.revokeObjectURL(downloadUrl), 60000);
  };

  const exportReport = async (kind, format, selectedLanguage) => {
    setReportLoading(true);
    setReportError('');
    try {
      setExportDialog(null);
      if (format === 'print') {
        await loadFullReport();
        setPrintRequest({ kind, language: selectedLanguage });
        return;
      }

      if (kind === 'patient') {
        const response = await fetch(`${API_URL}/export-patient-report-pdf`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ ...getReportPayload(), lang: selectedLanguage }),
        });
        if (!response.ok) {
          const errorBody = await response.json().catch(() => ({}));
          throw new Error(errorBody.detail || 'The PDF could not be generated. Check the API and try again.');
        }
        downloadPdfBlob(await response.blob(), 'Sepsis_Patient_Report.pdf');
        return;
      }

      const report = await loadFullReport();
      const pdfResponse = await fetch(`${API_URL}/export-pdf`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          lang: selectedLanguage,
          risk_tier: report.sepsis_assessment.risk_tier,
          sepsis_probability: report.sepsis_assessment.model_probability,
          data_completeness: report.sepsis_assessment.data_completeness,
          top_shap_contributions: report.explainable_ai.top_contributing_factors,
          risk_thresholds: report.sepsis_assessment.risk_thresholds,
          uncertainty_interval: report.sepsis_assessment.model_uncertainty_interval,
          model_version: report.sepsis_assessment.model_version,
        }),
      });
      if (!pdfResponse.ok) {
        const errorBody = await pdfResponse.json().catch(() => ({}));
        throw new Error(errorBody.detail || 'The PDF could not be generated. Check the API and try again.');
      }
      downloadPdfBlob(await pdfResponse.blob(), 'Sepsis_Clinical_Report.pdf');
    } catch (reportRequestError) {
      setReportError(t(reportRequestError.response?.data?.detail || reportRequestError.message || 'The report could not be generated. Check the API connection and try again.'));
    } finally {
      setReportLoading(false);
    }
  };

  const openExportDialog = (kind) => {
    setExportLanguage(language);
    setExportDialog(kind);
  };

  const statusTone = {
    'High Risk': 'rose',
    'Moderate Risk': 'amber',
    'Low Risk': 'emerald',
  }[riskLevel];
  const recommendation = recommendationFor(riskLevel, Boolean(prediction));
  const alarmVisible = liveEnabled && Number(prediction?.sepsis_probability ?? 0) > 0.6;
  const printLanguage = printRequest?.language || language;
  const pt = (value) => translateText(value, printLanguage);

  return (
    <>
      <div className={`dashboard-shell${language === 'ar' ? ' dashboard-arabic' : ''}`} dir={language === 'ar' ? 'rtl' : 'ltr'} lang={language}>
        <header className="topbar">
          <a className="brand" href="#dashboard" aria-label={t('MediMind AI dashboard')}>
            <span className="brand-mark"><HeartPulse size={23} strokeWidth={2.2} /></span>
            <span className="brand-copy"><strong>MediMind <span>AI</span></strong><small>{t('Clinical decision support')}</small></span>
          </a>
          <div className="topbar-actions">
            {patientRecord && <div className="dashboard-patient-context"><UserRound size={15} /><span>{patientRecord.name} · {t('Bed')} {patientRecord.bed_number}</span><button type="button" onClick={() => navigate('/patients')}><ArrowLeft size={15} /> {t('Back to Patients Directory')}</button></div>}
            <div className="language-toggle" role="group" aria-label={language === 'ar' ? 'اللغة' : 'Language'}>
              <button type="button" className={language === 'en' ? 'active' : ''} aria-pressed={language === 'en'} onClick={() => setLanguage('en')}>EN</button>
              <button type="button" className={language === 'ar' ? 'active' : ''} aria-pressed={language === 'ar'} onClick={() => setLanguage('ar')}>عربي</button>
            </div>
            <div className={`connection-pill connection-${apiStatus.toLowerCase()}`} role="status">
              <span className="connection-dot" />
              {apiStatus === 'Checking' ? t('Connecting to API') : `API ${t(apiStatus)}`}
              {apiStatus === 'Online' ? <Wifi size={15} /> : <WifiOff size={15} />}
            </div>
          </div>
        </header>

        <main id="dashboard" className="workspace">
          {patientLoading && <div className="patient-loading-banner"><LoaderCircle className="spin" size={16} /> {t('Loading patient record…')}</div>}
          {patientRecord && !prediction && !activePreset && <div className="patient-loading-banner"><ShieldCheck size={16} /> {t('This patient has no observations yet. Enter verified current measurements before running the model.')}</div>}
          <section className="quick-patient-bar" aria-label={t('Preset patient examples')}>
            <div className="quick-patient-heading"><span className="eyebrow">{t('QUICK TEST PATIENTS')}</span><span>{t('Illustrative values · model result may differ from the profile label')}</span></div>
            <div className="quick-patient-buttons">
              {QUICK_PATIENTS.map((preset) => {
                const PresetIcon = preset.id === 'acute-shock' ? AlertTriangle : preset.id === 'moderate' ? Activity : ShieldCheck;
                return (
                  <button className={`quick-patient-button ${preset.id}${activePreset === preset.id ? ' selected' : ''}`} type="button" key={preset.id} onClick={() => runPreset(preset)} disabled={loading || reportLoading} aria-pressed={activePreset === preset.id}>
                    <PresetIcon size={17} />
                    <span><strong>{t(preset.title)}</strong><small>{t(preset.target)}</small></span>
                    {loading && activePreset === preset.id && <LoaderCircle className="spin quick-patient-spinner" size={15} />}
                  </button>
                );
              })}
            </div>
          </section>
          {fullReport && activePreset && <div className="quick-result-banner" aria-live="polite"><span><Check size={15} /> {t('Assessment and report ready')}</span><strong>{t(riskLevel)} · {(fullReport.sepsis_assessment.model_probability * 100).toFixed(1)}%</strong><a href="#comprehensive-report-card">{t('View report')} <ArrowUpRight size={14} /></a></div>}

          <section className={`sensor-console ${liveEnabled ? 'sensor-active' : ''}`} aria-label="Live sensor simulation controls">
            <div className="sensor-console-title">
              <span className="sensor-icon"><Radio size={18} /></span>
              <div><strong>{t('Live sensor simulation')}</strong><span>{t('Demo readings · not connected to bedside devices')}</span></div>
            </div>
            <div className="sensor-console-actions">
              <label className="sensor-profile"><span>{t('Profile')}</span><select value={sensorCondition} onChange={(event) => setSensorCondition(event.target.value)} disabled={liveEnabled}><option value="stable">{t('Stable')}</option><option value="deteriorating">{t('Deteriorating')}</option></select></label>
              <button className={`sensor-switch ${liveEnabled ? 'switch-on' : ''}`} type="button" role="switch" aria-checked={liveEnabled} onClick={toggleLiveStream}>
                <span className="switch-track"><span /></span>{liveEnabled ? t('Stop stream') : t('Start live stream')}
              </button>
            </div>
            <div className="sensor-status-row">
              <span className={liveEnabled ? 'stream-indicator stream-on' : 'stream-indicator'} />
              <span>{liveEnabled ? t('Polling every 3 seconds') : t('Stream paused')}</span>
              {sensorTimestamp && <span>{t('Last sample')} {new Date(sensorTimestamp).toLocaleTimeString(language === 'ar' ? 'ar' : 'en')}</span>}
              {liveEnabled && <span className="sound-enabled"><Volume2 size={13} /> {t('Audio alert armed')}</span>}
            </div>
            {sensorError && <div className="sensor-error" role="alert">{t(sensorError)}</div>}
          </section>

          <section className="page-intro">
            <div>
              <div className="eyebrow"><span className="eyebrow-line" /> {t('ICU · EARLY WARNING')}</div>
              <h1>{t('Sepsis risk assessment')}</h1>
              <p>{t('Review patient observations, run the model, and inspect the factors behind its estimate.')}</p>
            </div>
            <div className="intro-meta"><span className="live-pulse" /> {t('Decision support')} <span className="meta-divider" /> {t('Model-assisted')}</div>
          </section>

          <div className="dashboard-grid">
            <section className="panel intake-panel" aria-labelledby="intake-title">
              <div className="panel-heading">
                <div className="section-index">01</div>
                <div className="panel-heading-copy">
                  <div className="eyebrow">{t('PATIENT ASSESSMENT')}</div>
                  <h2 id="intake-title">{t('Clinical observations')}</h2>
                  <p>{t('Enter current values to generate an estimate.')}</p>
                </div>
                <button className="icon-button help-button" type="button" title={t('Reference ranges are general adult guides, not patient-specific targets.')} aria-label={t('About reference ranges')}><CircleHelp size={18} /></button>
              </div>

              {activePreset && <div className="preset-notice"><Check size={15} /> {t(`${QUICK_PATIENTS.find((preset) => preset.id === activePreset)?.title} loaded`)} <span>{t('Illustrative inputs · model output may differ')}</span></div>}

              <form onSubmit={handleSubmit} className="intake-form">
                {GROUPS.map(({ title, subtitle, icon: GroupIcon, fields }) => (
                  <fieldset className="field-group" key={title}>
                    <legend className="sr-only">{t(title)}</legend>
                    <div className="field-group-heading">
                      <span className="group-icon"><GroupIcon size={17} /></span>
                      <div><h3>{t(title)}</h3><p>{t(subtitle)}</p></div>
                    </div>
                    <div className="fields-grid">
                      {fields.map(({ key, label, unit, range, icon: FieldIcon, step }) => (
                        <label className="field" key={key} htmlFor={`field-${key}`}>
                          <span className="field-label"><FieldIcon size={14} />{t(label)}</span>
                          <span className="input-wrap">
                            <input id={`field-${key}`} name={key} type="number" inputMode="decimal" step={step} value={form[key]} onChange={handleFieldChange} required aria-describedby={`range-${key}`} />
                            <span>{unit}</span>
                          </span>
                          <span className="normal-range" id={`range-${key}`}>{t('Guide')}: {t(range)}</span>
                        </label>
                      ))}
                    </div>
                    {title === 'Patient profile' && (
                      <div className="gender-control">
                        <span className="field-label">{t('Gender')}</span>
                        <div className="segmented-control" role="group" aria-label={t('Gender')}>
                          {[{ label: 'Female', value: 0, Icon: HeartPulse }, { label: 'Male', value: 1, Icon: UserRound }].map(({ label, value, Icon }) => (
                            <button type="button" key={label} aria-pressed={Number(form.Gender) === value} className={Number(form.Gender) === value ? 'segment active' : 'segment'} onClick={() => { setForm((previous) => ({ ...previous, Gender: value })); setActivePreset(''); }}>
                              <Icon size={15} /> {t(label)}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </fieldset>
                ))}

                {error && <div className="error-banner" role="alert"><AlertTriangle size={18} /><span>{t(error)}</span></div>}

                <button className="button button-primary run-button" type="submit" disabled={loading || apiStatus === 'Offline'}>
                  {loading ? <><LoaderCircle className="spin" size={18} /> {t('Analyzing patient data…')}</> : <><Activity size={18} /> {t('Run AI diagnostics')} <ArrowUpRight size={16} /></>}
                </button>
              </form>
            </section>

            <section className="results-column" aria-label="AI diagnostics results">
              <article className={`panel risk-panel risk-${statusTone} ${alarmVisible ? 'risk-alarm' : ''}`} aria-labelledby="risk-title">
                <div className="result-topline"><span className="eyebrow">{t('02 · MODEL OUTPUT')}</span><span className="result-chip"><span />{prediction ? t('Assessment complete') : t('Awaiting assessment')}</span></div>
                <div className="risk-layout">
                  <div className="risk-copy">
                    <h2 id="risk-title">{t('Sepsis risk')}</h2>
                    <div className="probability"><strong>{(probability * 100).toFixed(1)}</strong><span>%</span></div>
                    <p>{t('Model score')}</p>
                    <span className={`risk-badge badge-${statusTone}`}><span className="badge-dot" />{prediction ? t(riskLevel) : t('No assessment')}</span>
                  </div>
                  <div className="gauge" style={{ '--gauge-value': `${probability * 100}%` }} aria-label={`${(probability * 100).toFixed(1)} percent estimated probability`}>
                    <div className="gauge-inner"><HeartPulse size={23} /><span>{t('MODEL')}<br />{t('SCORE')}</span></div>
                  </div>
                </div>
                {prediction?.data_completeness && <p className="threshold-note">{t('Input completeness')}: {Math.round(prediction.data_completeness.score * 100)}% ({prediction.data_completeness.provided_feature_count}/{prediction.data_completeness.required_feature_count} {language === 'ar' ? 'مؤشرًا من النموذج' : 'model features supplied'}); {prediction.data_completeness.imputed_features.length} {language === 'ar' ? 'قيمة مقدّرة.' : 'values imputed.'}</p>}
                {prediction?.model_uncertainty_interval && <p className="threshold-note">{t('Model spread: {lower}–{upper}%.')
                  .replace('{lower}', (prediction.model_uncertainty_interval.lower * 100).toFixed(1))
                  .replace('{upper}', (prediction.model_uncertainty_interval.upper * 100).toFixed(1))}</p>}
                <div className="recommendation">
                  <div className="recommendation-icon">{riskLevel === 'High Risk' ? <AlertTriangle size={17} /> : <Stethoscope size={17} />}</div>
                  <div><span>{t('CLINICAL ACTION')}</span><p>{t(recommendation)}</p></div>
                </div>
                <div className="risk-footer">{prediction && <span>{t('High')} ≥{Math.round(riskThresholds.high * 100)}% · {t('Medium')} ≥{Math.round(riskThresholds.medium * 100)}%</span>}</div>
              </article>

              <article className="panel shap-panel" aria-labelledby="shap-title">
                <div className="panel-heading compact-heading">
                  <div className="section-index section-index-blue">03</div>
                  <div className="panel-heading-copy"><div className="eyebrow">{t('03 · EXPLAINABLE AI · SHAP')}</div><h2 id="shap-title">{t('What influenced this result?')}</h2><p>{t('Five strongest feature contributions from the model.')}</p></div>
                  <span className="shap-mark">SHAP</span>
                </div>
                {factors.length ? (
                  <div className="factor-list">
                    {factors.map((factor, index) => {
                      const impact = Number(factor.impact) || 0;
                      const raisesRisk = impact >= 0;
                      return (
                        <div className="factor-row" key={`${factor.feature}-${index}`}>
                          <div className="factor-info"><span className="factor-rank">0{index + 1}</span><span className="factor-name">{factor.name}</span><span className={raisesRisk ? 'impact-value impact-up' : 'impact-value impact-down'}>{impact > 0 ? '+' : ''}{impact.toFixed(3)}</span></div>
                          <div className="impact-track"><span className={raisesRisk ? 'impact-fill fill-up' : 'impact-fill fill-down'} style={{ width: factor.width }} /></div>
                          <div className="impact-caption"><span className={raisesRisk ? 'impact-up' : 'impact-down'}>{t(raisesRisk ? 'Increases model risk' : 'Decreases model risk')}</span><span>{t('Relative magnitude')}</span></div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="empty-state"><span className="empty-icon"><Microscope size={21} /></span><strong>{t('Insights appear after assessment')}</strong><p>{t('Run the model to see which patient features contributed most to its estimate.')}</p></div>
                )}
              </article>

              <div className="results-actions">
                <div><span className="eyebrow">{t('REPORT')}</span><strong>{t('Share a printable patient summary')}</strong></div>
                <button type="button" className="button button-secondary export-button" onClick={() => openExportDialog('patient')} disabled={!prediction || reportLoading}><Download size={16} /> {t('Export patient report')}</button>
              </div>
            </section>
          </div>

          <section className="panel image-panel" aria-labelledby="image-title">
            <div className="panel-heading">
              <div className="section-index section-index-blue">04</div>
              <div className="panel-heading-copy"><div className="eyebrow">{t('04 · IMAGE INTAKE')}</div><h2 id="image-title">{t('Medical image preview')}</h2><p>{t('Upload a supported image for file validation and preview.')}</p><Link className="image-status-link" to="/research">{t('Use and validation status')}</Link></div>
            </div>
            <div className="image-grid">
              <div>
                <label className="image-analysis-mode"><span>{t('Image type')}</span><select value={imageAnalysisType} onChange={(event) => setImageAnalysisType(event.target.value)}><option value="auto">{t('Auto / unknown')}</option><option value="xray">{t('Chest X-ray')}</option><option value="lab">{t('Lab report (OCR)')}</option></select></label>
                <input ref={imageInputRef} className="file-input-hidden" type="file" accept="image/jpeg,image/png,image/webp,image/bmp,image/tiff" onChange={(event) => selectImage(event.target.files?.[0])} />
                <button className={`drop-zone ${dragOver ? 'drop-zone-active' : ''}`} type="button" onClick={() => imageInputRef.current?.click()} onDragOver={(event) => { event.preventDefault(); setDragOver(true); }} onDragLeave={() => setDragOver(false)} onDrop={(event) => { event.preventDefault(); setDragOver(false); selectImage(event.dataTransfer.files?.[0]); }}>
                  <span className="upload-icon"><Upload size={21} /></span><strong>{t('Drop an image here or browse')}</strong><span>JPEG, PNG, WEBP, BMP, TIFF · {t('up to 10 MB')}</span>
                </button>
                {imageFile && <div className="selected-file"><span>{imageFile.name}</span><button type="button" aria-label={t('Remove selected image')} onClick={() => { setImageFile(null); setImagePreview(''); setImageReport(null); setImageError(''); }}><X size={15} /></button></div>}
                {imageError && <div className="error-banner" role="alert"><AlertTriangle size={17} /><span>{t(imageError)}</span></div>}
                <button type="button" className="button button-secondary image-check-button" onClick={validateImage} disabled={!imageFile || imageLoading}>{imageLoading ? <><LoaderCircle className="spin" size={16} /> {t('Checking image…')}</> : <><ShieldCheck size={16} /> {t('Validate image file')}</>}</button>
              </div>
              <div className="image-preview-column">
                {imagePreview ? <img className="image-preview" src={imagePreview} alt={t('Image preview')} /> : <div className="image-placeholder"><Microscope size={24} /><span>{t('Image preview')}</span></div>}
                {imageReport ? <div className="image-report" role="status"><strong>{t(IMAGE_STATUS_LABELS[imageReport.analysis_status] || 'Image checked')}</strong><span>{imageReport.image_format} · {imageReport.image_dimensions.width} × {imageReport.image_dimensions.height} px{imageReport.ocr_engine ? ` · ${imageReport.ocr_engine}` : ''}</span>{imageReport.model_name && <span>{imageReport.model_name}</span>}<p><b>{t('Findings')}:</b> {t(imageReport.findings || 'Not interpreted')}</p><p><b>{t('Infection site')}:</b> {t(imageReport.infection_site || 'Not identified')}</p>{imageReport.confidence_score != null && <><p><b>{t('Normalized screening score')}:</b> {Number(imageReport.confidence_score).toFixed(1)}/100</p>{imageReport.confidence_note && <p>{t(imageReport.confidence_note)}</p>}</>}{Object.keys(imageReport.target_scores || {}).length > 0 && <div className="ocr-candidate-values"><strong>{t('Target model scores · 0–100 normalized scale')}</strong>{Object.entries(imageReport.target_scores).map(([name, score]) => <span key={name}>{t(name)}: {Number(score).toFixed(1)}</span>)}</div>}<p>{t(imageReport.clinical_summary)}</p>{Object.keys(imageReport.extracted_vitals || {}).length > 0 && <><div className="ocr-candidate-values"><strong>{t('OCR candidate values · verify against source')}</strong>{Object.entries(imageReport.extracted_vitals).map(([feature, value]) => <span key={feature}>{language === 'ar' ? FEATURE_TRANSLATIONS[feature] || FEATURE_NAMES[feature] || feature : FEATURE_NAMES[feature] || feature}: {value}</span>)}</div>{imageReport.sepsis_prediction_preview && <p><b>{t('OCR-only model preview')}:</b> {t(imageReport.sepsis_prediction_preview.risk_level)} · {(imageReport.sepsis_prediction_preview.sepsis_probability * 100).toFixed(1)}%. {t('Not merged into current patient assessment.')}</p>}<button className="button button-secondary apply-ocr-button" type="button" onClick={applyExtractedVitals}>{t('Apply OCR candidates to form')}</button></>}<ul className="image-recommendations">{(imageReport.recommendations || []).map((item, index) => <li key={`image-review-${index}`}>{t(item)}</li>)}</ul><p className="image-disclaimer">{t("Image output is not a diagnosis and does not automatically alter the patient's sepsis prediction.")}</p></div> : <p className="image-helper">{t('OCR requires the optional EasyOCR/Tesseract dependencies. This project has no validated chest X-ray classifier.')}</p>}
              </div>
            </div>
          </section>

          <section id="comprehensive-report-card" className="panel comprehensive-report-card" aria-labelledby="comprehensive-report-title">
            <div className="report-card-heading">
              <div className="panel-heading">
                <div className="section-index">05</div>
                <div className="panel-heading-copy"><div className="eyebrow">{t('05 · STRUCTURED REPORT · PDF')}</div><h2 id="comprehensive-report-title">{t('Comprehensive decision-support summary')}</h2><p>{t('Recomputed from current values and SHAP on the API.')}</p></div>
              </div>
            </div>
            {fullReport && <div className="report-preview"><span><strong>{t('Model result')}</strong>{t(fullReport.sepsis_assessment.risk_level)} · {(fullReport.sepsis_assessment.model_probability * 100).toFixed(1)}%</span><span><strong>{t('Image review')}</strong>{t(fullReport.medical_image_review.status === 'xray_analyzed' ? 'X-ray screening result' : fullReport.medical_image_review.status === 'ocr_extracted' ? 'OCR candidates extracted' : fullReport.medical_image_review.status === 'preview_only' ? 'Preview only · no findings' : fullReport.medical_image_review.status === 'not_provided' ? 'Not provided' : IMAGE_STATUS_LABELS[fullReport.medical_image_review.status] || fullReport.medical_image_review.status)}</span><span><strong>{t('Diagnosis')}</strong>{t('Not generated')}</span></div>}
            {fullReport && <div className="clinical-guidance">
              <div className="guidance-heading"><div><span>{t('RISK-BASED GUIDANCE')}</span><strong>{t(fullReport.clinical_recommendations.risk_band)}</strong></div></div>
              <div className="guidance-grid">
                <section><h3>{t('Immediate Medical Action Bundle')}</h3><ul>{fullReport.clinical_recommendations.immediate_medical_action_bundle.map((item, index) => <li key={`action-${index}`}>{t(item)}</li>)}</ul></section>
                <section><h3>{t('Lab & Imaging Follow-up')}</h3><ul>{fullReport.clinical_recommendations.lab_and_imaging_follow_up.map((item, index) => <li key={`followup-${index}`}>{t(item)}</li>)}</ul></section>
              </div>
            </div>}
            {reportError && <div className="error-banner" role="alert"><AlertTriangle size={17} /><span>{t(reportError)}</span></div>}
            <div className="report-card-actions"><button className="button button-primary report-export-button" type="button" onClick={() => openExportDialog('cds')} disabled={!prediction || reportLoading || apiStatus === 'Offline'}>{reportLoading ? <><LoaderCircle className="spin" size={17} /> {t('Preparing report…')}</> : <><Download size={17} /> {t('Export CDS report (PDF)')}</>}</button></div>
          </section>

          <footer className="page-footer">
            <span className="footer-brand">MEDIMIND <b>AI</b></span>
            <Link className="provenance-link" to="/research"><ShieldCheck size={15} />{t('Use and validation status')}</Link>
          </footer>
        </main>
      </div>

      {exportDialog && (
        <div className="export-dialog-backdrop" role="presentation" onMouseDown={(event) => {
          if (event.target === event.currentTarget && !reportLoading) setExportDialog(null);
        }}>
          <section className="export-dialog" role="dialog" aria-modal="true" aria-labelledby="export-dialog-title" dir={language === 'ar' ? 'rtl' : 'ltr'}>
            <button className="export-dialog-close" type="button" aria-label={t('Cancel')} onClick={() => setExportDialog(null)} disabled={reportLoading}><X size={18} /></button>
            <span className="eyebrow">{t(exportDialog === 'patient' ? 'Patient report' : 'Clinical decision support report')}</span>
            <h2 id="export-dialog-title">{t('Choose how to export this report')}</h2>
            <label className="export-language-select">
              <span>{t('Report language')}</span>
              <select value={exportLanguage} onChange={(event) => setExportLanguage(event.target.value)}>
                <option value="en">{t('English')}</option>
                <option value="ar">{t('Arabic')}</option>
              </select>
            </label>
            <div className="export-dialog-actions">
              <button className="button button-secondary" type="button" disabled={reportLoading} onClick={() => void exportReport(exportDialog, 'print', exportLanguage)}><Activity size={16} /> {t('Print report')}</button>
              <button className="button button-primary" type="button" disabled={reportLoading} onClick={() => void exportReport(exportDialog, 'pdf', exportLanguage)}><Download size={16} /> {t('Download PDF')}</button>
            </div>
            {reportLoading && <p className="export-dialog-loading"><LoaderCircle className="spin" size={15} /> {t('Preparing report…')}</p>}
          </section>
        </div>
      )}

      {urgentAlarm && <div className="urgent-toast" role="alert" aria-live="assertive"><span className="urgent-toast-icon"><Volume2 size={19} /></span><div><strong>{t('Urgent simulated alert · demo only')}</strong><span>{t('Model estimate is above 60%. Follow local clinical escalation procedures; this is not a validated bedside alarm.')}</span><span>{t('Repeated siren and voice alert · close to silence')}</span></div><button type="button" aria-label={t('Silence alarm')} onClick={dismissUrgentAlarm}><X size={17} /></button></div>}

      <section className="print-report" aria-label={pt('Printable patient assessment report')} dir={printLanguage === 'ar' ? 'rtl' : 'ltr'} lang={printLanguage}>
        {printRequest?.kind === 'cds' && fullReport ? (
          <>
            <header className="print-header"><div className="print-brand"><HeartPulse size={24} /> MediMind AI</div><span>{pt('Clinical decision support report')}</span></header>
            <h1>{pt('Sepsis risk assessment')}</h1>
            <p className="print-date">{pt('Generated')} {new Date(fullReport.generated_at).toLocaleString(printLanguage === 'ar' ? 'ar' : 'en')}</p>
            <div className="print-result"><span>{pt('Model score')}</span><strong>{(fullReport.sepsis_assessment.model_probability * 100).toFixed(1)}%</strong><b>{pt(fullReport.sepsis_assessment.risk_level)}</b></div>
            <h2>{pt('Input completeness')}</h2>
            <p>{Math.round(fullReport.sepsis_assessment.data_completeness.score * 100)}% ({fullReport.sepsis_assessment.data_completeness.provided_feature_count}/{fullReport.sepsis_assessment.data_completeness.required_feature_count})</p>
            <h2>{pt('Explainable AI insights · SHAP')}</h2>
            <ol>{fullReport.explainable_ai.top_contributing_factors.map((factor, index) => <li key={`cds-print-${index}`}>{pt(FEATURE_NAMES[factor.feature] || factor.feature)}: {factor.impact > 0 ? '+' : ''}{factor.impact} ({pt(factor.impact >= 0 ? 'increases' : 'decreases')} {pt('model output')})</li>)}</ol>
            <h2>{pt('Medical image / X-ray review')}</h2>
            <p>{pt(fullReport.medical_image_review.clinical_summary || 'No medical image was supplied for review.')}</p>
            <h2>{pt('Clinical review guidance')}</h2>
            <ul>{fullReport.clinical_recommendations.immediate_medical_action_bundle.map((item, index) => <li key={`cds-action-${index}`}>{pt(item)}</li>)}</ul>
            <footer className="print-provenance" role="note"><ShieldCheck size={14} />{pt(provenanceNotice)}</footer>
          </>
        ) : printRequest?.kind === 'patient' && fullReport ? (
          <>
            <header className="print-header"><div className="print-brand"><HeartPulse size={24} /> MediMind AI</div><span>{pt('Patient report')}</span></header>
            <h1>{pt('Patient report')}</h1>
            <p className="print-date">{pt('Generated')} {new Date(fullReport.generated_at).toLocaleString(printLanguage === 'ar' ? 'ar' : 'en')}</p>
            <h2>{pt('Patient summary & admission context')}</h2>
            <div className="print-values"><div><span>{pt('Age')}</span><strong>{fullReport.patient_summary.age_years} {pt('years')}</strong></div><div><span>{pt('Gender')}</span><strong>{pt(fullReport.patient_summary.gender)}</strong></div><div><span>{pt('Admission context')}</span><strong>{pt(fullReport.patient_summary.admission_context)}</strong></div></div>
            <h2>{pt('Real-time vital signs & lab biomarkers')}</h2>
            <p className="print-section-note">{pt(fullReport.vital_signs_and_lab_biomarkers.reference_note)}</p>
            <table className="print-table"><thead><tr><th>{pt('Measurement')}</th><th>{pt('Value')}</th><th>{pt('General reference')}</th><th>{pt('Context')}</th></tr></thead><tbody>{fullReport.vital_signs_and_lab_biomarkers.observations.map((item) => <tr key={item.feature}><td>{printLanguage === 'ar' ? FEATURE_TRANSLATIONS[item.feature] || FEATURE_NAMES[item.feature] || item.feature : FEATURE_NAMES[item.feature] || item.feature}</td><td>{pt(item.value)} {item.unit || ''}</td><td>{item.general_adult_reference_range ? `${item.general_adult_reference_range.lower}–${item.general_adult_reference_range.upper} ${item.unit}` : pt('Not specified')}</td><td>{pt(item.relative_to_reference || 'Context only')}</td></tr>)}</tbody></table>
            <h2>{pt('Sepsis risk score & AI probability')}</h2>
            <div className="print-result"><span>{pt('Model estimate')}</span><strong>{(fullReport.sepsis_assessment.model_probability * 100).toFixed(1)}%</strong><b>{pt(fullReport.sepsis_assessment.risk_level)}</b></div>
            <h2>{pt('Explainable AI insights · SHAP')}</h2>
            <ol>{fullReport.explainable_ai.top_contributing_factors.map((factor, index) => <li key={`${factor.feature}-${index}`}>{printLanguage === 'ar' ? FEATURE_TRANSLATIONS[factor.feature] || FEATURE_NAMES[factor.feature] || factor.feature : FEATURE_NAMES[factor.feature] || factor.feature}: {factor.impact > 0 ? '+' : ''}{factor.impact} ({pt(factor.impact >= 0 ? 'increases' : 'decreases')} {pt('model output')})</li>)}</ol>
            <h2>{pt('Medical image / X-ray review')}</h2>
            {fullReport.medical_image_review.image_format && <p><strong>{pt('Technical preview:')}</strong> {fullReport.medical_image_review.image_format}, {fullReport.medical_image_review.image_dimensions.width} × {fullReport.medical_image_review.image_dimensions.height} px. {pt('This is file metadata, not an image finding.')}</p>}
            {fullReport.medical_image_review.model_name && <p><strong>{pt('Screening model:')}</strong> {fullReport.medical_image_review.model_name}</p>}
            <p><strong>{pt('Findings:')}</strong> {pt(fullReport.medical_image_review.findings || 'Not interpreted')}</p>
            <p><strong>{pt('Infection site:')}</strong> {pt(fullReport.medical_image_review.infection_site || 'Not identified')}</p>
            {fullReport.medical_image_review.confidence_score != null && <p><strong>{pt('Normalized screening score:')}</strong> {Number(fullReport.medical_image_review.confidence_score).toFixed(1)}/100. {pt(fullReport.medical_image_review.confidence_note)}</p>}
            {Object.keys(fullReport.medical_image_review.target_scores || {}).length > 0 && <><h3>{pt('Target class scores · normalized operating-point scale')}</h3><ul>{Object.entries(fullReport.medical_image_review.target_scores).map(([name, score]) => <li key={`xray-score-${name}`}>{pt(name)}: {Number(score).toFixed(1)}/100</li>)}</ul></>}
            <p>{pt(fullReport.medical_image_review.clinical_summary)}</p>
            {Object.keys(fullReport.medical_image_review.extracted_vitals || {}).length > 0 && <><h3>{pt('OCR candidate values · verify against source')}</h3><ul>{Object.entries(fullReport.medical_image_review.extracted_vitals).map(([feature, value]) => <li key={`print-ocr-${feature}`}>{printLanguage === 'ar' ? FEATURE_TRANSLATIONS[feature] || FEATURE_NAMES[feature] || feature : FEATURE_NAMES[feature] || feature}: {value}</li>)}</ul>{fullReport.medical_image_review.sepsis_prediction_preview && <p><strong>{pt('OCR-only model preview')}:</strong> {pt(fullReport.medical_image_review.sepsis_prediction_preview.risk_level)} · {(fullReport.medical_image_review.sepsis_prediction_preview.sepsis_probability * 100).toFixed(1)}%. {pt('This is separate from the patient assessment.')}</p>}</>}
            <h3>{pt('Image review recommendations')}</h3>
            <ul>{fullReport.medical_image_review.recommendations.map((item, index) => <li key={`print-image-${index}`}>{pt(item)}</li>)}</ul>
            <h2>{pt('Clinical impression')}</h2>
            <p>{pt(fullReport.clinical_impression.statement)}</p>
            <h2>{pt('Clinical recommendations ·')} {pt(fullReport.clinical_recommendations.risk_band)}</h2>
            <h3>{pt('Immediate Medical Action Bundle')}</h3>
            <ul>{fullReport.clinical_recommendations.immediate_medical_action_bundle.map((item, index) => <li key={`print-action-${index}`}>{pt(item)}</li>)}</ul>
            <h3>{pt('Lab & Imaging Follow-up')}</h3>
            <ul>{fullReport.clinical_recommendations.lab_and_imaging_follow_up.map((item, index) => <li key={`print-followup-${index}`}>{pt(item)}</li>)}</ul>
          </>
        ) : (
          <>
            <header className="print-header"><div className="print-brand"><HeartPulse size={24} /> MediMind AI</div><span>{pt('CLINICAL DECISION SUPPORT REPORT')}</span></header>
            <h1>{pt('Sepsis risk assessment')}</h1>
            <p className="print-date">{pt('Generated')} {new Date().toLocaleString(printLanguage === 'ar' ? 'ar' : 'en')}</p>
            <div className="print-result"><span>{pt('Estimated probability')}</span><strong>{(probability * 100).toFixed(1)}%</strong><b>{prediction ? pt(riskLevel) : pt('No assessment')}</b></div>
            <h2>{pt('Patient observations')}</h2>
            <div className="print-values">{GROUPS.flatMap((group) => group.fields).map(({ key, label, unit }) => <div key={key}><span>{pt(label)}</span><strong>{form[key]} {unit}</strong></div>)}<div><span>{pt('Gender')}</span><strong>{pt(Number(form.Gender) === 1 ? 'Male' : 'Female')}</strong></div></div>
            <h2>{pt('Clinical action support')}</h2><p>{pt(recommendation)}</p>
            <h2>{pt('Top model contributions (SHAP)')}</h2>
            {factors.length ? <ol>{factors.map((factor, index) => <li key={`${factor.feature}-print-${index}`}>{factor.name}: {Number(factor.impact) > 0 ? '+' : ''}{Number(factor.impact).toFixed(3)} ({pt(Number(factor.impact) >= 0 ? 'increases' : 'decreases')} {pt('model risk')})</li>)}</ol> : <p>{pt('No contribution data available.')}</p>}
          </>
        )}
        <footer className="print-provenance" role="note"><ShieldCheck size={14} />{pt(provenanceNotice)}</footer>
      </section>
    </>
  );
}

export default App;
