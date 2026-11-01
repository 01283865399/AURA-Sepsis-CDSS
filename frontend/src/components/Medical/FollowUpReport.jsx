import { AlertTriangle, ArrowRight, ClipboardList } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useLocale } from '../../hooks/useLocale';
import '../../styles/follow-up-report.css';

export default function FollowUpReport({ report }) {
  const { text } = useLocale();

  return (
    <section className="follow-up-report" aria-labelledby="follow-up-title">
      <header className="follow-up-heading"><span><ClipboardList size={17} /></span><div><span className="eyebrow">{text('إرشاد منظم', 'STRUCTURED SUMMARY')}</span><h3 id="follow-up-title">{report.title}</h3></div></header>
      <p className="follow-up-summary">{report.summary}</p>
      <div className="follow-up-actions"><h4>{text('ما الخطوة التالية؟', 'What to do next')}</h4><ol>{report.actions.map((action, index) => <li key={index}><span>{index + 1}</span><p>{action}</p></li>)}</ol></div>
      {report.emergency && <aside className="follow-up-emergency"><AlertTriangle size={17} /><p>{report.emergency}</p></aside>}
      <footer className="follow-up-source"><Link to="/research">{text('تفاصيل حالة النموذج والدرجة', 'Model status and score details')} <ArrowRight size={13} /></Link></footer>
    </section>
  );
}
