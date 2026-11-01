import { Link } from 'react-router-dom';
import { useLocale } from '../../hooks/useLocale';

export default function Footer() {
  const { text } = useLocale();
  return (
    <footer className="app-footer">
      <span>© MediMind AI · {text('منصة النماذج الطبية البحثية', 'Medical research model workspace')}</span>
      <Link to="/research">{text('حالة الاستخدام والاعتماد', 'Use and validation status')}</Link>
      <nav className="app-footer-links" aria-label={text('معلومات قانونية', 'Legal information')}>
        <Link to="/disclaimer">{text('إخلاء المسؤولية', 'Disclaimer')}</Link>
        <Link to="/privacy">{text('الخصوصية', 'Privacy')}</Link>
        <Link to="/terms">{text('شروط الاستخدام', 'Terms')}</Link>
      </nav>
    </footer>
  );
}
