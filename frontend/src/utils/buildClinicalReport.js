/**
 * Build a cautious, bilingual follow-up report from a model response.
 * This is deterministic UI guidance, not a diagnostic or generative medical model.
 * @param {import('../api/types').ModuleDefinition} module
 * @param {Record<string, any>} result
 * @param {Array<{condition: string, probability: number}>} predictions
 * @param {boolean} isEnglish
 */
export function buildClinicalReport(module, result, predictions, isEnglish) {
  const top = predictions[0];
  const score = top ? `${Math.round(Number(top.probability) * 100)}%` : '';
  const isSepsis = module.id === 'sepsis';
  const isRadiology = ['xray', 'covid19_radiography', 'tb_chest_radiography'].includes(module.id);
  const extractedValues = result.extracted_vitals || {};
  const extractedCount = Object.keys(extractedValues).length;

  let summary;
  if (isSepsis) {
    const level = result.risk_level || top?.condition || (isEnglish ? 'not available' : 'غير متاح');
    summary = isEnglish
      ? `The model's returned category is “${level}” (${score || 'score unavailable'}). The score is experimental, not a clinical probability.`
      : `تصنيف النموذج هو «${level}» (${score || 'الدرجة غير متاحة'}). الدرجة تجريبية وليست احتمالاً سريرياً معايراً.`;
  } else if (module.id === 'xray') {
    if (result.analysis_status === 'xray_analyzed' && top) {
      summary = isEnglish
        ? `The chest X-ray screen identified an operational signal for ${top.condition} (${Number(result.confidence_score ?? top.probability * 100).toFixed(1)}/100). The image alone cannot establish clinical stability, a confirmed diagnosis, or disease probability.`
        : `أظهر فحص أشعة الصدر إشارة تشغيلية مرتبطة بـ ${top.condition} (${Number(result.confidence_score ?? top.probability * 100).toFixed(1)}/100). لا تكفي الصورة وحدها لإثبات استقرار الحالة أو تأكيد تشخيص أو تحديد احتمال الإصابة.`;
    } else {
      summary = isEnglish
        ? 'No X-ray finding was produced by the service. A non-result does not rule out disease.'
        : 'لم تُنتج الخدمة نتيجة للأشعة. عدم ظهور نتيجة لا يستبعد وجود مرض.';
    }
  } else if (module.id === 'lab_ocr') {
    summary = extractedCount
      ? (isEnglish
        ? `OCR extracted ${extractedCount} candidate value(s). They are transcriptions to verify, not interpreted lab results.`
        : `استخرج OCR عدد ${extractedCount} من القيم المرشحة. هي قراءة آلية تحتاج تحققاً، وليست تفسيراً للتحاليل.`)
      : (isEnglish
        ? 'No supported values were extracted from the image. Review the source document manually.'
        : 'لم تُستخرج قيم مدعومة من الصورة. راجع التقرير الأصلي يدوياً.');
  } else if (top) {
    summary = isEnglish
      ? `The model's top-ranked class is “${top.condition}” (${score}). This is the model's class score, not a confirmed diagnosis or personal risk estimate.`
      : `الفئة الأعلى ترتيباً هي «${top.condition}» (${score}). هذه درجة تصنيف للنموذج وليست تشخيصاً مؤكداً أو تقديراً شخصياً للخطر.`;
  } else {
    summary = isEnglish
      ? 'The service returned no interpretable prediction. Do not infer a diagnosis from this response.'
      : 'لم تُرجع الخدمة تنبؤاً قابلاً للتفسير. لا تستنتج تشخيصاً من هذه الاستجابة.';
  }

  let actions;
  if (isSepsis) {
    const riskTier = String(result.risk_tier || result.risk_level || '').toLowerCase();
    if (riskTier.includes('high')) {
      actions = isEnglish
        ? [
            'Contact the treating clinician promptly to review current observations, labs, and the local escalation protocol; this model band is not a validated urgency decision.',
            'Base any urgent action on the person’s actual condition and qualified clinical assessment, not this score alone.',
          ]
        : [
            'تواصل سريعاً مع الطبيب المعالج لمراجعة العلامات الحيوية والتحاليل وبروتوكول التصعيد المحلي؛ تصنيف النموذج ليس مقياس استعجال معتمداً.',
            'اجعل قرار الاستعجال مبنياً على حالة الشخص الفعلية وتقييم مختص، لا على الدرجة وحدها.',
          ];
    } else if (riskTier.includes('medium')) {
      actions = isEnglish
        ? [
            'Arrange clinician review of this estimate with current observations, labs, baseline, and local protocol.',
            'The model band is not clinically validated; follow the care team’s plan and reassess if the condition changes.',
          ]
        : [
            'رتّب مراجعة الطبيب لهذا التقدير مع العلامات الحيوية والتحاليل وخط الأساس والبروتوكول المحلي.',
            'تصنيف النموذج غير معتمد سريرياً؛ اتبع خطة فريق الرعاية وأعد التقييم عند تغير الحالة.',
          ];
    } else {
      actions = isEnglish
        ? [
            'A low model estimate does not rule out sepsis or another illness; continue the clinician’s existing assessment plan.',
            'Review the estimate with the treating clinician if symptoms persist, worsen, or remain concerning.',
          ]
        : [
            'التقدير المنخفض لا يستبعد الإنتان أو مرضاً آخر؛ واصل خطة التقييم التي وضعها الطبيب.',
            'راجع الطبيب إذا استمرت الأعراض أو تفاقمت أو بقيت مثيرة للقلق.',
          ];
    }
  } else if (isRadiology) {
    actions = isEnglish
      ? [
          'Request review of the original image by a qualified radiologist or treating clinician.',
          'Compare the screening output with the image quality, projection, symptoms, and clinical record.',
        ]
      : [
          'راجع الصورة الأصلية وتقريرها مع اختصاصي أشعة أو الطبيب المعالج.',
          'فسّر الإشارة مع جودة الصورة ووضعيتها والأعراض والعلامات الحيوية والسجل السريري.',
          'لا تغيّر العلاج أو تتخذ قراراً عاجلاً اعتماداً على درجة النموذج وحدها.',
        ];
  } else if (module.id === 'skin_lesions_8class' || module.id === 'isic_2019') {
    actions = isEnglish
      ? [
          'Arrange qualified clinical or dermatology review of the lesion and the original image.',
          'Mention any recent change in size, shape, color, bleeding, or symptoms to the clinician.',
        ]
      : [
          'رتّب مراجعة سريرية أو جلدية مؤهلة للآفة والصورة الأصلية.',
          'أخبر الطبيب عن أي تغير حديث في الحجم أو الشكل أو اللون أو نزف أو أعراض.',
        ];
  } else if (module.id === 'diabetes') {
    actions = isEnglish
      ? ['Review the result with a clinician alongside the original glucose and HbA1c measurements.', 'If symptoms or concern continue, request clinical assessment even when the model ranks “no diabetes” highest.']
      : ['راجع النتيجة مع طبيب إلى جانب قياسات الغلوكوز وHbA1c الأصلية.', 'إذا استمرت الأعراض أو المخاوف، اطلب تقييماً سريرياً حتى لو رتّب النموذج «لا يوجد سكري» أولاً.'];
  } else if (module.id === 'heart') {
    actions = isEnglish
      ? ['Discuss this result with a clinician alongside symptoms, ECG, and original measurements.', 'Use urgent services for ongoing chest pain, severe breathlessness, fainting, or sudden deterioration, regardless of the model score.']
      : ['ناقش النتيجة مع طبيب إلى جانب الأعراض وتخطيط القلب والقياسات الأصلية.', 'اطلب الطوارئ عند ألم صدري مستمر أو ضيق نفس شديد أو إغماء أو تدهور مفاجئ، بصرف النظر عن درجة النموذج.'];
  } else if (module.id === 'kidney') {
    actions = isEnglish
      ? ['Review the output with a clinician alongside the original kidney blood tests and urinalysis.', 'If the result conflicts with symptoms or known test results, rely on clinical review rather than the model ranking.']
      : ['راجع النتيجة مع طبيب إلى جانب تحاليل وظائف الكلى وفحص البول الأصليين.', 'إذا تعارضت النتيجة مع الأعراض أو التحاليل المعروفة، فاعتمد على التقييم السريري لا ترتيب النموذج.'];
  } else if (module.id === 'indian_liver_patient') {
    actions = isEnglish
      ? ['Discuss the result with a clinician alongside the original liver panel and medical history.', 'Ask the clinician whether the existing results need confirmation or follow-up; the model cannot make that decision.']
      : ['ناقش النتيجة مع طبيب إلى جانب تحاليل الكبد الأصلية والتاريخ الصحي.', 'اسأل الطبيب إن كانت النتائج تحتاج تأكيداً أو متابعة؛ النموذج لا يحدد ذلك.'];
  } else if (module.id === 'lab_ocr') {
    actions = isEnglish
      ? [
          'Verify every extracted number, unit, and label against the original report before relying on it.',
          "Ask the ordering clinician to interpret verified values in the person's clinical context.",
        ]
      : [
          'تحقق من كل رقم ووحدة واسم مستخرج بمقارنته بالتقرير الأصلي قبل الاعتماد عليه.',
          'اطلب من الطبيب تفسير القيم التي تم التحقق منها ضمن السياق السريري.',
        ];
  } else if (module.id === 'symptoms' || module.id === 'ddxplus') {
    actions = isEnglish
      ? [
          'Use the ranked list as discussion support; confirm symptoms and findings with a qualified clinician.',
          'Seek in-person assessment if symptoms are severe, worsening, or concerning.',
        ]
      : [
          'استخدم ترتيب الاحتمالات لدعم النقاش فقط، وأكد الأعراض والنتائج مع طبيب مؤهل.',
          'اطلب تقييماً حضورياً إذا كانت الأعراض شديدة أو تتفاقم أو تثير القلق.',
        ];
  } else {
    actions = isEnglish
      ? [
          'Review the model output with a qualified clinician alongside the original measurements and medical history.',
          'Do not use this score alone to start, stop, or change care.',
        ]
      : [
          'راجع ناتج النموذج مع طبيب مؤهل إلى جانب القياسات الأصلية والتاريخ الصحي.',
          'لا تستخدم هذه الدرجة وحدها لبدء الرعاية أو إيقافها أو تغييرها.',
        ];
  }

  const emergency = isSepsis || module.id === 'heart'
    ? (isEnglish
      ? 'If there is severe breathing difficulty, persistent chest pain, new confusion, fainting, or collapse, contact local emergency services now; do not wait for an AI result.'
      : 'عند وجود صعوبة شديدة في التنفس أو ألم صدري مستمر أو ارتباك جديد أو إغماء أو انهيار، اتصل بالطوارئ المحلية الآن ولا تنتظر نتيجة النموذج.')
    : '';

  return {
    title: isEnglish ? 'What to do next' : 'ماذا تفعل الآن؟',
    summary,
    actions,
    emergency,
  };
}
