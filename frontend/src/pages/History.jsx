import { Download, Search, Trash2 } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import toast from 'react-hot-toast';
import { MODULES } from '../api/endpoints';
import TopKPredictions from '../components/Charts/TopKPredictions';
import { Button, Panel } from '../components/UI/primitives';
import { usePredictionStore } from '../store/predictionStore';
import { formatDate } from '../utils/formatters';
import { useLocale } from '../hooks/useLocale';

export default function History() {
  const { isEnglish, text } = useLocale();
  const history = usePredictionStore((state) => state.history);
  const clearHistory = usePredictionStore((state) => state.clearHistory);
  const [search, setSearch] = useState('');
  const [searchParams] = useSearchParams();
  const requestedModel = searchParams.get('model');
  const initialModel = MODULES.some((entry) => entry.id === requestedModel && entry.available) ? requestedModel : 'all';
  const [model, setModel] = useState(initialModel);
  useEffect(() => setModel(initialModel), [initialModel]);
  const [expanded, setExpanded] = useState(null);
  const filtered = useMemo(() => history.filter((item) => {
    const matchesModel = model === 'all' || item.modelId === model;
    const matchesSearch = `${item.modelId} ${item.modelName} ${item.detail || ''} ${item.predictions?.[0]?.condition || ''}`.toLowerCase().includes(search.toLowerCase());
    return matchesModel && matchesSearch;
  }), [history, model, search]);

  const exportPdf = async () => {
    if (!filtered.length) return toast.error(text('لا توجد نتائج للتصدير.', 'There are no results to export.'));
    const { jsPDF } = await import('jspdf');
    const document = new jsPDF({ unit: 'mm', format: 'a4' });
    document.setFont('helvetica', 'bold');
    document.setFontSize(17);
    document.text('MediMind AI Research Analysis History', 16, 20);
    document.setFont('helvetica', 'normal');
    document.setFontSize(9);
    document.text('Research use only. Not a diagnosis or treatment recommendation.', 16, 27);
    let y = 39;
    filtered.slice(0, 35).forEach((item, index) => {
      const first = item.predictions?.[0];
      const line = `${index + 1}. ${item.modelId} | ${first?.condition || item.detail || 'Analysis'} | ${first ? `${(first.probability * 100).toFixed(1)}%` : 'See response'} | ${new Date(item.createdAt).toLocaleString('en')}`;
      const wrapped = document.splitTextToSize(line, 178);
      if (y + wrapped.length * 5 > 278) { document.addPage(); y = 18; }
      document.text(wrapped, 16, y);
      y += wrapped.length * 5 + 3;
    });
    document.save('medimind-research-history.pdf');
    toast.success(text('تم إنشاء ملف PDF.', 'PDF report created.'));
  };

  const removeAll = () => {
    if (!window.confirm(text('مسح سجل التحليلات المحلي من هذا المتصفح؟', 'Clear local analysis history from this browser?'))) return;
    clearHistory();
    toast.success(text('تم مسح السجل المحلي.', 'Local history cleared.'));
  };

  return (
    <div className="page-stack">
      <div className="page-title-row"><div><span className="eyebrow">BROWSER STORAGE</span><h1>{text('سجل التحليلات', 'Analysis history')}</h1><p>{text('السجل محلي لهذا المتصفح ولا يحتوي على قيم الإدخال.', 'Stored in this browser only; submitted values are not retained.')}</p></div><div className="title-actions"><Button variant="secondary" type="button" onClick={exportPdf}><Download size={16} /> PDF</Button><Button variant="danger" type="button" onClick={removeAll} disabled={!history.length}><Trash2 size={16} /> {text('مسح', 'Clear')}</Button></div></div>
      <Panel className="history-panel"><div className="history-filters"><label className="search-box"><Search size={16} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder={text('ابحث في النموذج أو النتيجة', 'Search model or result')} /></label><label className="select-filter"><span>{text('النموذج', 'Model')}</span><select value={model} onChange={(event) => setModel(event.target.value)}><option value="all">{text('كل النماذج', 'All models')}</option>{MODULES.filter((module) => module.available).map((module) => <option value={module.id} key={module.id}>{isEnglish ? module.titleEn : module.title}</option>)}</select></label></div>
        <div className="history-table-wrap"><table className="history-table"><thead><tr><th>{text('النموذج', 'Model')}</th><th>{text('النتيجة الأعلى', 'Top result')}</th><th>{text('الدرجة', 'Score')}</th><th>{text('التاريخ', 'Date')}</th><th><span className="sr-only">{text('التفاصيل', 'Details')}</span></th></tr></thead><tbody>{filtered.map((item) => { const module = MODULES.find((entry) => entry.id === item.modelId); const first = item.predictions?.[0]; return <tr key={item.id}><td><strong>{(isEnglish ? module?.titleEn : module?.title) || item.modelName}</strong><small>{item.modelName}</small></td><td>{first?.condition || item.detail || text('استجابة فحص', 'Screening response')}</td><td>{first ? `${(first.probability * 100).toFixed(1)}%` : '—'}</td><td>{formatDate(item.createdAt, isEnglish ? 'en' : 'ar')}</td><td><button className="text-button" type="button" onClick={() => setExpanded(expanded === item.id ? null : item.id)}>{expanded === item.id ? text('إخفاء', 'Hide') : text('التفاصيل', 'Details')}</button></td></tr>; })}</tbody></table></div>
        {!filtered.length && <div className="empty-state">{history.length ? text('لا توجد نتائج مطابقة للتصفية.', 'No results match these filters.') : text('لا توجد تحليلات محفوظة بعد.', 'No analyses saved yet.')}</div>}
        {filtered.map((item) => { const module = MODULES.find((entry) => entry.id === item.modelId); return expanded === item.id && <div className="history-expanded" key={`${item.id}-expanded`}><strong>{(isEnglish ? module?.titleEn : module?.title) || item.modelId} · {formatDate(item.createdAt, isEnglish ? 'en' : 'ar')}</strong><TopKPredictions predictions={item.predictions || []} /></div>; })}
      </Panel>
    </div>
  );
}
