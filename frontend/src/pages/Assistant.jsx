import { motion } from 'framer-motion';
import { zodResolver } from '@hookform/resolvers/zod';
import { Activity, ArrowUp, Bean, BookOpen, Check, ChevronDown, Droplets, FileImage, FlaskConical, HeartPulse, Layers3, ListChecks, Microscope, Network, Paperclip, PanelRightClose, PanelRightOpen, ScanFace, ScanLine, ShieldCheck, Sparkles, X } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useForm } from 'react-hook-form';
import { Link } from 'react-router-dom';
import { getModule } from '../api/endpoints';
import { getApiError, sendGeminiChat } from '../api/client';
import ResultCard from '../components/Medical/ResultCard';
import ResourceLibrary from '../components/Medical/ResourceLibrary';
import { Alert, Field, Loading } from '../components/UI/primitives';
import { useLocale } from '../hooks/useLocale';
import { usePrediction } from '../hooks/usePrediction';
import { usePredictionStore } from '../store/predictionStore';
import { makeModuleSchema, validateImage } from '../utils/validators';
import '../styles/assistant-workspace.css';

const ICONS = {
  sepsis: Activity, xray: ScanLine, symptoms: ListChecks, diabetes: Droplets,
  heart: HeartPulse, kidney: Bean, indian_liver_patient: FlaskConical,
  skin_lesions_8class: ScanFace, isic_2019: Microscope,
  covid19_radiography: ScanLine, tb_chest_radiography: ScanLine,
  ddxplus: Network, lab_ocr: FileImage,
};

function parseKeyedValues(message, module) {
  const fields = module.fields || [];
  const lookup = new Map(fields.map((field) => [field.name.toLowerCase(), field.name]));
  const values = {};
  const pairPattern = /(?:^|[,\n;\s])([A-Za-z][A-Za-z0-9_]*)\s*[:=]\s*([^,;\n]+)/g;
  for (const match of message.matchAll(pairPattern)) {
    const fieldName = lookup.get(match[1].toLowerCase());
    if (fieldName) values[fieldName] = match[2].trim();
  }
  return values;
}

function renderInlineMarkdown(value) {
  const parts = value.split(/(\*\*[^*]+\*\*|__[^_]+__|\*[^*\n]+\*)/g);
  return parts.map((part, index) => {
    const isStrong = (/^\*\*[^*]+\*\*$/.test(part) || /^__[^_]+__$/.test(part));
    if (isStrong) return <strong key={`${part}-${index}`}>{part.slice(2, -2)}</strong>;
    if (/^\*[^*\n]+\*$/.test(part)) return <em key={`${part}-${index}`}>{part.slice(1, -1)}</em>;
    return part;
  });
}

function MarkdownMessage({ value }) {
  const lines = String(value || '').split(/\r?\n/);
  const blocks = [];
  let list = [];
  let listType = 'ul';

  const flushList = () => {
    if (list.length) {
      const ListTag = listType;
      blocks.push(
        <ListTag key={`list-${blocks.length}`}>
          {list.map((item, index) => <li key={`${item}-${index}`}>{renderInlineMarkdown(item)}</li>)}
        </ListTag>,
      );
      list = [];
      listType = 'ul';
    }
  };

  lines.forEach((line) => {
    const trimmed = line.trim();
    const bullet = trimmed.match(/^[-*]\s+(.+)/);
    if (bullet) {
      if (listType !== 'ul') flushList();
      listType = 'ul';
      list.push(bullet[1]);
      return;
    }
    const numbered = trimmed.match(/^\d+[.)]\s+(.+)/);
    if (numbered) {
      if (listType !== 'ol') flushList();
      listType = 'ol';
      list.push(numbered[1]);
      return;
    }
    flushList();
    if (!trimmed) return;
    if (/^---+$/.test(trimmed)) {
      blocks.push(<hr key={`rule-${blocks.length}`} />);
      return;
    }
    const heading = trimmed.match(/^#{1,3}\s+(.+)/);
    blocks.push(heading
      ? <h3 key={`heading-${blocks.length}`}>{renderInlineMarkdown(heading[1])}</h3>
      : <p key={`paragraph-${blocks.length}`}>{renderInlineMarkdown(trimmed)}</p>);
  });
  flushList();

  return <div className="chat-markdown">{blocks}</div>;
}

function structuredFields(module) {
  if (module.id === 'ddxplus') {
    return [
      { name: 'age', label: 'العمر', labelEn: 'Age', type: 'number', required: true, min: 0, max: 120 },
      { name: 'sex', label: 'الجنس', labelEn: 'Sex', type: 'select', required: true, options: [{ label: 'أنثى', value: 'F' }, { label: 'ذكر', value: 'M' }] },
      { name: 'evidences', label: 'أدلة بصيغة E_…', labelEn: 'Evidence codes (E_…)', type: 'text', required: true },
    ];
  }
  return module.fields || [];
}

function ChatImage({ file, isEnglish }) {
  const [url, setUrl] = useState('');
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    if (!file || !file.type?.startsWith('image/')) return undefined;
    const objectUrl = URL.createObjectURL(file);
    setUrl(objectUrl);
    return () => URL.revokeObjectURL(objectUrl);
  }, [file]);

  if (!file) return null;
  if (!url) {
    return <div className="chat-attachment-file"><FileImage size={17} /><span>{file.name}</span></div>;
  }
  return (
    <>
      <button className="chat-image-button" type="button" onClick={() => setExpanded(true)} aria-label={isEnglish ? `Preview ${file.name}` : `معاينة ${file.name}`}>
        <img src={url} alt={file.name} />
        <span><FileImage size={13} />{file.name}</span>
      </button>
      {expanded && (
        <div className="chat-image-lightbox" role="dialog" aria-modal="true" aria-label={isEnglish ? 'Image preview' : 'معاينة الصورة'} onClick={() => setExpanded(false)}>
          <button type="button" className="chat-image-close" onClick={() => setExpanded(false)} aria-label={isEnglish ? 'Close preview' : 'إغلاق المعاينة'}><X size={20} /></button>
          <img src={url} alt={file.name} onClick={(event) => event.stopPropagation()} />
          <span>{file.name}</span>
        </div>
      )}
    </>
  );
}

function isResultFollowUpQuestion(value) {
  return /(?:نتيجة|تحليل|فحص).*(?:كويس|جيد|تمام|مطمئن|طبيعي)|هل.*(?:كويس|جيد|طبيعي|مطمئن)|(?:good|okay|normal|reassuring).*(?:result|scan|analysis)/i.test(value);
}

function buildResultFollowUp(result, isEnglish) {
  const scores = Object.entries(result?.target_scores || {})
    .map(([condition, score]) => ({ condition, score: Number(score) }))
    .filter((item) => Number.isFinite(item.score))
    .sort((a, b) => b.score - a.score);
  const top = scores[0];
  if (!top) {
    return isEnglish
      ? 'The screening returned no interpretable finding. It cannot be classified as normal from this result alone; review the original image with a radiologist.'
      : 'لم تُرجع نتيجة الفحص إشارة قابلة للتفسير. لا يمكن اعتبار الفحص طبيعياً من هذه النتيجة وحدها؛ راجع الصورة الأصلية مع اختصاصي الأشعة.';
  }
  const secondary = scores.slice(1, 3).map((item) => `${item.condition} (${item.score.toFixed(1)}/100)`).join('، ');
  return isEnglish
    ? `The scan is not reported as simply “good” or “bad.” The highest operational signal is ${top.condition} (${top.score.toFixed(1)}/100), followed by ${secondary || 'no additional selected signals'}. This is a screening signal, not a diagnosis or a measure of clinical stability. The appropriate next step is review of the original image, symptoms, vital signs, and radiologist interpretation.`
    : `لا تُصنَّف الأشعة ببساطة إلى «كويسة» أو «وحشة». أعلى إشارة تشغيلية هي ${top.condition} (${top.score.toFixed(1)}/100)، تليها ${secondary || 'لا توجد إشارات مختارة إضافية'}. هذه إشارة فحص وليست تشخيصاً أو مقياساً لاستقرار الحالة. الخطوة المناسبة هي مراجعة الصورة الأصلية مع الأعراض والعلامات الحيوية وتقرير اختصاصي الأشعة.`;
}

export default function Assistant() {
  const { isEnglish, text } = useLocale();
  const [toolId] = useState('gemini_chat');
  const [prompt, setPrompt] = useState('');
  const [file, setFile] = useState(null);
  const [fileError, setFileError] = useState('');
  const [messages, setMessages] = useState([]);
  const [notice, setNotice] = useState('');
  const [previewUrl, setPreviewUrl] = useState('');
  const [resourcesOpen, setResourcesOpen] = useState(false);
  const [patientId, setPatientId] = useState('');
  const [patientContextConsent, setPatientContextConsent] = useState(false);
  const [isResponding, setIsResponding] = useState(false);
  const scrollRef = useRef(null);
  const fileInputRef = useRef(null);
  const prediction = usePrediction();
  const clearHistory = usePredictionStore((state) => state.clearHistory);
  const module = useMemo(() => toolId === 'gemini_chat'
    ? { id: 'gemini_chat', available: true, transport: 'chat', api: 'model', endpoint: '/api/v1/chat' }
    : getModule(toolId), [toolId]);
  const formFields = useMemo(() => structuredFields(module || {}), [module]);
  const schema = useMemo(() => module?.transport === 'json' && module.id !== 'symptoms'
    ? makeModuleSchema(module)
    : undefined, [module]);
  const defaultValues = useMemo(() => Object.fromEntries(formFields.map((field) => [field.name, ''])), [formFields]);
  const { register, handleSubmit, setValue, reset, formState: { errors } } = useForm({
    resolver: schema ? zodResolver(schema) : undefined,
    defaultValues,
    mode: 'onBlur',
  });
  const requiresImage = module?.transport === 'image-form' || module?.transport === 'raw-image';
  const needsFields = module?.transport === 'json' && module.id !== 'symptoms';

  useEffect(() => {
    reset(defaultValues);
    setFileError('');
    setNotice('');
    prediction.reset();
    if (module?.transport === 'json' && module.id !== 'symptoms') {
      for (const [name, value] of Object.entries(parseKeyedValues(prompt, module))) {
        setValue(name, value, { shouldValidate: true, shouldDirty: true });
      }
    }
  }, [toolId, defaultValues, reset]);

  useEffect(() => {
    if (!file) {
      setPreviewUrl('');
      return undefined;
    }
    const objectUrl = URL.createObjectURL(file);
    setPreviewUrl(objectUrl);
    return () => URL.revokeObjectURL(objectUrl);
  }, [file]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages, prediction.isPending, isResponding]);

  const updatePrompt = (value) => {
    setPrompt(value);
    if (needsFields && module) {
      for (const [name, fieldValue] of Object.entries(parseKeyedValues(value, module))) {
        setValue(name, fieldValue, { shouldValidate: true, shouldDirty: true });
      }
    }
  };

  const setSelectedFile = (nextFile) => {
    setFileError('');
    setNotice('');
    if (nextFile) {
      const error = validateImage(nextFile);
      if (error) {
        setFileError(error);
        return;
      }
    }
    setFile(nextFile);
  };

  const appendUserMessage = (messageModule = module, messageFile = file, messageText = prompt) => setMessages((current) => [...current, {
    id: globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`,
    role: 'user', text: messageText.trim(), file: messageFile,
    toolId: messageModule.id,
  }]);

  const run = async (values = {}) => {
    setNotice('');
    if (toolId === 'gemini_chat') {
      const requestPrompt = prompt.trim();
      const imageIntent = /(?:أشعة|اشعة|صدر|x[\s-]?ray|chest)/i.test(requestPrompt);
      const xrayModule = getModule('xray');

      if (file && imageIntent && xrayModule) {
        const requestFile = file;
        appendUserMessage(xrayModule, requestFile, requestPrompt || text('تحليل صورة الأشعة', 'Analyze the X-ray image'));
        setPrompt('');
        setFile(null);
        try {
          const result = await prediction.mutateAsync({ module: xrayModule, values: {}, file: requestFile });
          setMessages((current) => [...current, {
            id: globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`,
            role: 'assistant',
            result,
            module: xrayModule,
            text: result.clinical_summary || result.message || text('اكتمل فحص صورة الأشعة. راجع الإشارات مع مختص.', 'The X-ray screening is complete. Review the signals with a specialist.'),
          }]);
          setIsResponding(true);
          try {
            const explanation = await sendGeminiChat([
              { role: 'user', content: requestPrompt || text('اشرح نتيجة فحص الأشعة.', 'Explain the X-ray screening result.') },
            ], {
              patientId: patientId.trim() || null,
              patientContextConsent,
              toolResults: [{
                analysis_type: 'xray',
                file_attached: true,
                clinical_notes: requestPrompt,
                result,
              }],
            });
            setMessages((current) => [...current, {
              id: globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`,
              role: 'assistant',
              text: explanation.message,
            }]);
          } catch (error) {
            setMessages((current) => [...current, {
              id: globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`,
              role: 'assistant',
              error: getApiError(error),
              text: text('اكتمل الفحص، لكن تعذر توليد الشرح التفاعلي.', 'The screening completed, but the interactive explanation could not be generated.'),
            }]);
          } finally {
            setIsResponding(false);
          }
        } catch (error) {
          setMessages((current) => [...current, {
            id: globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`,
            role: 'assistant',
            error: error.userMessage || getApiError(error),
            text: text('تعذر فحص صورة الأشعة. حاول مرة أخرى.', 'The X-ray could not be screened. Please try again.'),
          }]);
          setPrompt(requestPrompt);
          setFile(requestFile);
        }
        return;
      }

      if (file && !imageIntent) {
        appendUserMessage(module, file, requestPrompt || text('حلل الصورة', 'Analyze the image'));
        setMessages((current) => [...current, {
          id: globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`,
          role: 'assistant',
          text: text('ما نوع التحليل المطلوب للصورة؟ اكتب مثلاً: «حلل أشعة الصدر» أو «استخرج القيم من تقرير المختبر».', 'What would you like me to do with the image? For example: “Analyze the chest X-ray” or “Extract values from the lab report”.'),
        }]);
        return;
      }

      if (!requestPrompt) {
        setNotice(text('اكتب رسالة أولاً.', 'Enter a message first.'));
        return;
      }
      const latestResultMessage = [...messages].reverse().find((message) => message.role === 'assistant' && message.result);
      if (latestResultMessage && isResultFollowUpQuestion(requestPrompt)) {
        appendUserMessage();
        setPrompt('');
        setMessages((current) => [...current, {
          id: globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`,
          role: 'assistant',
          text: buildResultFollowUp(latestResultMessage.result, isEnglish),
        }]);
        return;
      }
      const requestMessages = [
        ...messages
          .filter((message) => message.text && !message.error)
          .slice(-18)
          .map((message) => ({ role: message.role, content: message.text })),
        { role: 'user', content: requestPrompt },
      ];
      const latestToolResult = [...messages]
        .reverse()
        .find((message) => message.role === 'assistant' && message.result)?.result;
      setIsResponding(true);
      appendUserMessage();
      setPrompt('');
      try {
        const result = await sendGeminiChat(requestMessages, {
          patientId: patientId.trim() || null,
          patientContextConsent,
          toolResults: latestToolResult ? [{
            analysis_type: 'xray',
            file_attached: true,
            clinical_notes: requestPrompt,
            result: latestToolResult,
          }] : [],
        });
        setMessages((current) => [...current, {
          id: globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`,
          role: 'assistant',
          text: result.message,
        }]);
      } catch (error) {
        setMessages((current) => [...current, {
          id: globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`,
          role: 'assistant',
          error: getApiError(error),
          text: text('تعذر الحصول على رد من Gemini.', 'Gemini could not return an answer.'),
        }]);
        setPrompt(requestPrompt);
      } finally {
        setIsResponding(false);
      }
      return;
    }
    if (!module?.available) return;
    if (file && !requiresImage) return;
    if (module.id === 'symptoms' && !prompt.trim()) {
      setNotice(text('اكتب عرضاً واحداً على الأقل.', 'Enter at least one symptom.'));
      return;
    }
    if (requiresImage) {
      const imageError = validateImage(file);
      if (imageError) {
        setFileError(imageError);
        return;
      }
    }
    if (needsFields && module.id === 'sepsis' && !Object.values(values).some((value) => value !== '' && value != null)) {
      setNotice(text('أدخل قياساً واحداً على الأقل، أو اكتب الاسم والقيمة مثل HR=90.', 'Enter at least one measurement or use field=value, e.g. HR=90.'));
      return;
    }

    appendUserMessage();
    const requestPrompt = prompt.trim();
    const requestFile = file;
    setPrompt('');
    setFile(null);
    reset(defaultValues);
    try {
      const result = await prediction.mutateAsync({ module, values, file: requestFile });
      setMessages((current) => [...current, {
        id: globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`,
        role: 'assistant', result, module,
        text: result.clinical_summary || result.message || text('وصلت نتيجة الأداة المحددة.', 'The selected tool returned a result.'),
      }]);
    } catch (error) {
      setMessages((current) => [...current, {
        id: globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`,
        role: 'assistant', error: error.userMessage || text('تعذر الاتصال بالأداة المحددة.', 'Could not reach the selected tool.'),
        text: text('لم تُنتج الخدمة نتيجة. تحقق من اتصال الخادم والمدخلات.', 'The service returned no result. Check the server and inputs.'),
      }]);
      setPrompt(requestPrompt);
      setFile(requestFile);
    }
  };

  const submit = needsFields ? handleSubmit(run) : (event) => {
    event.preventDefault();
    void run(module?.id === 'symptoms' ? { symptoms: prompt } : {});
  };

  const clearConversation = () => {
    setMessages([]);
    setPrompt('');
    setFile(null);
    setFileError('');
    setNotice('');
    prediction.reset();
  };

  const addResourceToPrompt = (title) => {
    setPrompt((current) => [current.trim(), title].filter(Boolean).join(current.trim() ? '\n' : ''));
  };

  const dropImage = (event) => {
    event.preventDefault();
    const dropped = event.dataTransfer?.files?.[0];
    if (dropped) setSelectedFile(dropped);
  };

  const isEmpty = messages.length === 0;

  return (
    <div className={`assistant-workspace ${resourcesOpen ? '' : 'assistant-workspace-resources-closed'}`} onDragOver={(event) => event.preventDefault()} onDrop={dropImage}>
      {resourcesOpen && <ResourceLibrary isEnglish={isEnglish} onClose={() => setResourcesOpen(false)} onUseRecord={addResourceToPrompt} />}
      <div className="assistant-page">
      <header className="assistant-heading">
        <div className="assistant-heading-copy"><span className="eyebrow"><Sparkles size={13} /> {text('مساعد النماذج البحثية', 'Research model assistant')}</span><h1>{text('كيف يمكنني مساعدتك؟', 'What would you like to analyze?')}</h1><p>{text('اختر الأداة أولاً. اكتب الأعراض، أدخل قيماً بصيغة واضحة، أو أرفق صورة للفحص.', 'Choose a tool first. Enter symptoms, explicit field values, or attach an image for screening.')}</p></div>
        <div className="assistant-heading-actions">
          <button className="assistant-resource-toggle" type="button" onClick={() => setResourcesOpen((open) => !open)} aria-pressed={resourcesOpen}><BookOpen size={15} />{text('المصادر', 'Sources')}{resourcesOpen ? <PanelRightClose size={15} /> : <PanelRightOpen size={15} />}</button>
          <Link className="assistant-catalog-link" to="/models"><ListChecks size={15} /> {text('كل النماذج', 'All models')}</Link>
        </div>
      </header>

      {toolId === 'gemini_chat' && <div className="assistant-research-banner">
        <ShieldCheck size={15} />
        <label>{text('سياق مريض منزوع الهوية (اختياري):', 'De-identified patient context (optional):')} <input value={patientId} onChange={(event) => setPatientId(event.target.value)} placeholder="patient id" /></label>
        <label><input type="checkbox" checked={patientContextConsent} onChange={(event) => setPatientContextConsent(event.target.checked)} /> {text('أوافق على إرسال المؤشرات المنزوعة الهوية إلى Gemini', 'I consent to sending de-identified vitals to Gemini')}</label>
      </div>}

      <div className={`assistant-transcript ${isEmpty ? 'assistant-transcript-empty' : ''}`} ref={scrollRef} aria-live="polite">
        {isEmpty ? (
          <div className="assistant-welcome">
            <div className="assistant-welcome-mark"><Sparkles size={22} /></div>
            <h2>{text('من أين نبدأ؟', 'Where should we start?')}</h2>
            <p>{text('الأداة المختارة هي التي تحدد مسار الباك إند والموديل المستخدم. النص الحر لا يُحوّل تلقائياً إلى تشخيص أو قيم.', 'The selected tool determines the backend route and model. Free text is not automatically converted into diagnoses or measurements.')}</p>
            <div className="assistant-suggestions" aria-label={text('اقتراحات الأدوات', 'Suggested tools')}>
              {[
                ['symptoms', text('حلّل هذه الأعراض', 'Analyze these symptoms')],
                ['xray', text('افحص صورة أشعة صدر', 'Screen a chest X-ray')],
                ['lab_ocr', text('استخرج قيماً من تقرير مختبر', 'Extract values from a lab report')],
                ['diabetes', text('تقييم مؤشرات السكري', 'Review diabetes indicators')],
              ].map(([id, label]) => <button key={id} type="button" onClick={() => setPrompt(label)}>{label}</button>)}
            </div>
          </div>
        ) : messages.map((message) => (
          <motion.article key={message.id} className={`chat-message chat-message-${message.role}`} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
            <span className="chat-avatar" aria-hidden="true">{message.role === 'assistant' ? <Activity size={15} /> : 'أ'}</span>
            <div className="chat-message-body">
              {message.role === 'user' ? <><div className="chat-bubble">{message.text || text('يرجى تحليل المرفق', 'Please analyze the attachment')}</div>{message.file && <ChatImage file={message.file} isEnglish={isEnglish} />}<small><span>{toolTitle(message.toolId, isEnglish)}</span>{message.file && <span><FileImage size={12} /> {message.file.name}</span>}</small></> : <>{!message.result && <MarkdownMessage value={message.text} />}{message.error && <Alert>{message.error}</Alert>}{message.result?.extracted_vitals && Object.keys(message.result.extracted_vitals).length > 0 && <div className="ocr-candidates"><strong>{text('قيم OCR المرشحة · راجع التقرير الأصلي', 'OCR candidates · verify the original report')}</strong><dl>{Object.entries(message.result.extracted_vitals).map(([name, value]) => <div key={name}><dt>{name}</dt><dd>{value}</dd></div>)}</dl></div>}{message.result && <ResultCard result={message.result} module={message.module} />}</>}
            </div>
          </motion.article>
        ))}
        {(prediction.isPending || isResponding) && <div className="chat-pending" role="status" aria-live="polite"><span className="chat-avatar"><Activity size={15} /></span><span className="chat-pending-copy"><span className="chat-pending-dots" aria-hidden="true"><i /><i /><i /></span>{text('جاري كتابة الرد…', 'Writing a response…')}</span></div>}
      </div>

      <div className="assistant-compose-wrap">
        {module && needsFields && (
          <details className="assistant-fields" open>
            <summary><span><Check size={15} /> {text('بيانات النموذج', 'Model input fields')}</span><ChevronDown size={15} /></summary>
            <div className="assistant-fields-body">
              <p>{text('اكتب القيم هنا، أو اكتبها في الرسالة بصيغة field=value. لا يفسر النظام الوصف الحر كقياسات.', 'Enter values here or use field=value in the message. Free-form descriptions are not interpreted as measurements.')}</p>
              <div className="form-grid">
                {formFields.filter((field) => !field.advanced).map((field) => <Field key={field.name} field={field} register={register} error={errors[field.name]} language={isEnglish ? 'en' : 'ar'} />)}
              </div>
              {formFields.some((field) => field.advanced) && (
                <details className="advanced-fields">
                  <summary>{text('خصائص إضافية', 'Additional fields')}</summary>
                  <div className="form-grid">
                    {formFields.filter((field) => field.advanced).map((field) => <Field key={field.name} field={field} register={register} error={errors[field.name]} language={isEnglish ? 'en' : 'ar'} />)}
                  </div>
                </details>
              )}
            </div>
          </details>
        )}
        {notice && <Alert tone="warning">{notice}</Alert>}
        {fileError && <Alert>{fileError}</Alert>}
        <form className={`assistant-composer ${file ? 'assistant-composer-has-file' : ''}`} onSubmit={submit} onDragOver={(event) => event.preventDefault()} onDrop={dropImage}>
          {previewUrl && <div className="composer-file"><img src={previewUrl} alt={text('معاينة الصورة المرفقة', 'Attached image preview')} /><span>{file?.name}</span><button type="button" onClick={() => setSelectedFile(null)} aria-label={text('إزالة الصورة', 'Remove image')}><X size={15} /></button></div>}
          <div className="composer-toolbar">
            <textarea value={prompt} onChange={(event) => updatePrompt(event.target.value)} rows={1} placeholder={text('اكتب رسالتك هنا…', 'Write your message…')} aria-label={text('رسالتك', 'Your message')} disabled={prediction.isPending || isResponding} />
            <input ref={fileInputRef} className="sr-only" type="file" accept="image/jpeg,image/png,image/webp,image/bmp,image/tiff" onChange={(event) => setSelectedFile(event.target.files?.[0] || null)} />
            <button className="composer-attach" type="button" onClick={() => fileInputRef.current?.click()} aria-label={text('إضافة صورة للتحليل', 'Add an image for analysis')} title={requiresImage ? text('إرفاق صورة', 'Attach image') : text('أرفق صورة ثم اختر أداة تدعم الصور', 'Attach an image, then select an image tool')}><Paperclip size={17} /><span>{text('إرفاق صورة', 'Attach image')}</span></button>
            <button className="composer-send" type="submit" disabled={prediction.isPending || isResponding || !module?.available} aria-label={text('إرسال الطلب', 'Send request')} title={text('إرسال الطلب', 'Send request')}>{prediction.isPending || isResponding ? <Loading label="" /> : <ArrowUp size={18} />}</button>
          </div>
        </form>
        <div className="assistant-compose-foot"><span>{text('نوع الأداة ومسار الخدمة ظاهران بجوار زر الإرسال.', 'The selected tool and service are shown beside Send.')}</span><button type="button" onClick={clearConversation} disabled={isEmpty && !prompt && !file}>{text('محادثة جديدة', 'New chat')}</button></div>
      </div>
      </div>
    </div>
  );
}

function composerHint(module, isEnglish) {
  if (!module) return isEnglish ? 'Choose a tool to get started.' : 'اختر أداة للبدء.';
  if (module.id === 'symptoms') return isEnglish ? 'Describe symptoms, separated by commas or lines…' : 'اكتب الأعراض وافصل بينها بفاصلة أو سطر جديد…';
  if (module.transport === 'image-form') return isEnglish ? 'Attach a supported medical image…' : 'أرفق صورة طبية مدعومة…';
  if (module.transport === 'raw-image') return isEnglish ? 'Attach an image; this text is not sent to the image model…' : 'أرفق صورة؛ النص هنا لا يُرسل لموديل الصورة…';
  return isEnglish ? 'Add context or enter explicit field=value pairs…' : 'أضف سياقاً أو قيماً صريحة بصيغة field=value…';
}

function toolTitle(id, english) {
  if (id === 'gemini_chat') return english ? 'Gemini AI chat' : 'محادثة Gemini AI';
  const module = getModule(id);
  return module ? (english ? module.titleEn : module.title) : id;
}
