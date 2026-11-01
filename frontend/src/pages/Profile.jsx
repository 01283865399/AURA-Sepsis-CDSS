import { KeyRound, Languages, Moon, ShieldCheck } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { useUiStore } from '../store/uiStore';
import { Panel } from '../components/UI/primitives';
import { useLocale } from '../hooks/useLocale';

export default function Profile() {
  const { isEnglish, text } = useLocale();
  const auth = useAuth();
  const theme = useUiStore((state) => state.theme);
  const language = useUiStore((state) => state.language);
  return (
    <div className="page-stack"><div className="page-title-row"><div><span className="eyebrow">LOCAL PREFERENCES</span><h1>{text('الإعدادات والملف', 'Preferences and profile')}</h1><p>{text('إعدادات العرض وحالة التكامل في هذا المتصفح.', 'Display settings and integration status for this browser.')}</p></div></div>
      <div className="profile-grid"><Panel className="profile-card"><span className="profile-icon"><Languages size={19} /></span><h2>{text('التفضيلات', 'Preferences')}</h2><dl><div><dt>{text('اللغة', 'Language')}</dt><dd>{language === 'ar' ? 'العربية' : 'English'}</dd></div><div><dt>{text('المظهر', 'Theme')}</dt><dd>{theme === 'light' ? text('فاتح', 'Light') : text('داكن', 'Dark')}</dd></div><div><dt>{text('مكان التخزين', 'Storage')}</dt><dd>{text('هذا المتصفح', 'This browser')}</dd></div></dl><p>{text('غيّر اللغة أو المظهر من الأزرار في الشريط العلوي.', 'Change language or theme from the top bar.')}</p></Panel>
        <Panel className="profile-card"><span className="profile-icon profile-icon-amber"><KeyRound size={19} /></span><h2>{text('الحسابات والمصادقة', 'Accounts and authentication')}</h2><p>{auth.message}</p><div className="auth-status"><span className={`status-dot ${auth.isAuthenticated ? 'status-success' : 'status-warning'}`} /> {auth.isAuthenticated ? `${auth.user?.username} · ${auth.user?.role}` : text('غير مسجل الدخول', 'Not signed in')}</div><small>{text('استخدم حسابات بحثية فقط. سياق المريض لا يُرسل إلى Gemini إلا بعد موافقة صريحة وإخفاء الهوية.', 'Use research accounts only. Patient context is sent to Gemini only after explicit consent and de-identification.')}</small></Panel>
        <Panel className="profile-card"><span className="profile-icon profile-icon-green"><ShieldCheck size={19} /></span><h2>{text('الخصوصية', 'Privacy')}</h2><p>{text('سجل التحليلات يحفظ اسم النموذج والنتيجة والتوقيت فقط، دون قيم النموذج أو اسم مريض.', 'Analysis history stores only the model, result, and time. It does not retain inputs or patient names.')}</p><p>{text('امسح سجل التحليلات من صفحة السجل عند استخدام جهاز مشترك.', 'Clear local history when using a shared device.')}</p></Panel>
      </div>
    </div>
  );
}
