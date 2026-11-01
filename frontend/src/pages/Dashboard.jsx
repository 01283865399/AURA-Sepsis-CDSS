import { Activity, ArrowUpLeft, ClipboardCheck, Database, ShieldCheck } from 'lucide-react';
import { Area, AreaChart, Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Link } from 'react-router-dom';
import { MODULES } from '../api/endpoints';
import { Panel } from '../components/UI/primitives';
import { useApiHealth } from '../hooks/useApiHealth';
import { usePredictionStore } from '../store/predictionStore';
import { formatDate } from '../utils/formatters';
import { useLocale } from '../hooks/useLocale';

export default function Dashboard() {
  const history = usePredictionStore((state) => state.history);
  const health = useApiHealth();
  const { isEnglish, text } = useLocale();
  const grouped = Object.entries(history.reduce((result, item) => {
    result[item.modelId] = (result[item.modelId] || 0) + 1;
    return result;
  }, {})).map(([modelId, count]) => { const module = MODULES.find((entry) => entry.id === modelId); return { name: (isEnglish ? module?.titleEn : module?.title) || modelId, count }; }).sort((a, b) => b.count - a.count).slice(0, 7);
  const timeline = history.slice(0, 14).reverse().map((item, index) => ({
    name: new Intl.DateTimeFormat(isEnglish ? 'en' : 'ar-EG', { day: 'numeric', month: 'short' }).format(new Date(item.createdAt)),
    score: Math.round((item.predictions?.[0]?.probability || 0) * 100),
    order: index + 1,
  }));

  return (
    <div className="page-stack">
      <div className="page-title-row"><div><span className="eyebrow">OVERVIEW · LOCAL DATA</span><h1>{text('لوحة المتابعة', 'Dashboard')}</h1><p>{text('ملخص تشغيل الواجهة والسجل المحفوظ في هذا المتصفح.', 'Workspace status and analysis history saved in this browser.')}</p></div><Link className="button button-primary" to="/models">{text('تحليل جديد', 'New analysis')} <ArrowUpLeft size={16} /></Link></div>
      <div className="metric-grid">
        <Metric icon={ClipboardCheck} label={text('فحوصات في السجل', 'Saved analyses')} value={history.length} tone="mint" />
        <Metric icon={Activity} label={text('مسارات متاحة', 'Available routes')} value={MODULES.filter((module) => module.available).length} tone="blue" />
        <Metric icon={ShieldCheck} label={text('حالة Model API', 'Model API status')} value={health.isSuccess ? text('متصل', 'Online') : text('غير متصل', 'Offline')} tone={health.isSuccess ? 'mint' : 'coral'} />
        <Metric icon={Database} label={text('تخزين الفحوصات', 'Analysis storage')} value={text('محلي', 'Local')} tone="gold" />
      </div>
      <div className="chart-grid">
        <Panel className="chart-panel"><div className="panel-heading"><div><span className="eyebrow">MODEL ACTIVITY</span><h2>{text('الفحوصات حسب النموذج', 'Analyses by model')}</h2></div></div>{grouped.length ? <div className="chart-canvas"><ResponsiveContainer width="100%" height="100%"><BarChart data={grouped} margin={{ top: 10, right: 8, left: -20, bottom: 0 }}><CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--line)" /><XAxis dataKey="name" tick={{ fill: 'var(--muted)', fontSize: 10 }} axisLine={false} tickLine={false} /><YAxis allowDecimals={false} tick={{ fill: 'var(--muted)', fontSize: 10 }} axisLine={false} tickLine={false} /><Tooltip cursor={{ fill: 'var(--surface-soft)' }} /><Bar dataKey="count" name={text('عدد الفحوصات', 'Analyses')} fill="var(--teal)" radius={[5, 5, 0, 0]} maxBarSize={40} /></BarChart></ResponsiveContainer></div> : <ChartEmpty message={text('ستظهر الرسوم بعد حفظ تحليلات في المتصفح.', 'Charts appear after analyses are saved in this browser.')} />}</Panel>
        <Panel className="chart-panel"><div className="panel-heading"><div><span className="eyebrow">RECENT ESTIMATES</span><h2>{text('درجات النتائج الأخيرة', 'Recent model scores')}</h2></div></div>{timeline.length ? <div className="chart-canvas"><ResponsiveContainer width="100%" height="100%"><AreaChart data={timeline} margin={{ top: 10, right: 8, left: -20, bottom: 0 }}><defs><linearGradient id="scoreFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="var(--coral)" stopOpacity={0.28} /><stop offset="95%" stopColor="var(--coral)" stopOpacity={0.02} /></linearGradient></defs><CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--line)" /><XAxis dataKey="name" tick={{ fill: 'var(--muted)', fontSize: 10 }} axisLine={false} tickLine={false} /><YAxis domain={[0, 100]} tick={{ fill: 'var(--muted)', fontSize: 10 }} axisLine={false} tickLine={false} /><Tooltip formatter={(value) => [`${value}%`, text('درجة النموذج', 'Model score')]} /><Area type="monotone" dataKey="score" stroke="var(--coral)" strokeWidth={2} fill="url(#scoreFill)" /></AreaChart></ResponsiveContainer></div> : <ChartEmpty message={text('ستظهر الرسوم بعد حفظ تحليلات في المتصفح.', 'Charts appear after analyses are saved in this browser.')} />}</Panel>
      </div>
      <Panel className="recent-panel"><div className="panel-heading"><div><span className="eyebrow">LATEST</span><h2>{text('أحدث الفحوصات', 'Recent analyses')}</h2></div><Link to="/history">{text('عرض السجل', 'View history')} <ArrowUpLeft size={15} /></Link></div>{history.length ? <div className="recent-list">{history.slice(0, 5).map((item) => { const module = MODULES.find((entry) => entry.id === item.modelId); return <Link to={`/modules/${item.modelId}`} className="recent-row" key={item.id}><span className="recent-dot" /><span className="recent-name">{(isEnglish ? module?.titleEn : module?.title) || item.modelName}</span><strong>{item.predictions?.[0]?.condition || item.detail || text('تم التحليل', 'Analysis complete')}</strong><time>{formatDate(item.createdAt, isEnglish ? 'en' : 'ar')}</time></Link>; })}</div> : <ChartEmpty message={text('لا توجد تحليلات في هذا المتصفح بعد.', 'No analyses in this browser yet.')} />}</Panel>
    </div>
  );
}

function Metric({ icon: Icon, label, value, tone }) {
  return <Panel className="metric-card"><span className={`metric-icon metric-${tone}`}><Icon size={18} /></span><div><small>{label}</small><strong>{value}</strong></div></Panel>;
}

function ChartEmpty({ message = 'ستظهر الرسوم بعد حفظ تحليلات في المتصفح.' }) {
  return <div className="chart-empty">{message}</div>;
}
