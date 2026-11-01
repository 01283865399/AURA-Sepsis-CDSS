import { ArrowUpLeft, LockKeyhole, ShieldAlert } from 'lucide-react';
import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import { authenticate, getApiError } from '../api/client';
import { Panel } from '../components/UI/primitives';
import { useUiStore } from '../store/uiStore';
import './legal.css';

export default function AuthUnavailable() {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const isEnglish = useUiStore((state) => state.language) === 'en';
  const isRegister = pathname === '/register';
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('viewer');
  const [busy, setBusy] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    try {
      await authenticate(isRegister ? '/api/auth/register' : '/api/auth/login', {
        username, password, ...(isRegister ? { role } : {}),
      });
      toast.success(isEnglish ? 'Signed in successfully.' : 'تم تسجيل الدخول بنجاح.');
      navigate('/assistant');
    } catch (error) {
      toast.error(getApiError(error));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page-stack auth-unavailable-page">
      <div className="page-title-row">
        <div>
          <span className="eyebrow">ACCOUNT ACCESS</span>
          <h1>{isEnglish ? (isRegister ? 'Create an account' : 'Sign in') : (isRegister ? 'إنشاء حساب' : 'تسجيل الدخول')}</h1>
          <p>{isEnglish ? 'Use a research account. Do not reuse a production password.' : 'استخدم حسابًا بحثيًا فقط، ولا تستخدم كلمة مرور إنتاجية.'}</p>
        </div>
      </div>
      <Panel className="auth-unavailable-panel">
        <span className="auth-unavailable-icon"><LockKeyhole size={24} /></span>
        <span className="eyebrow">{isEnglish ? 'AUTHENTICATION NOT CONFIGURED' : 'المصادقة غير مهيأة'}</span>
        <h2>{isEnglish ? 'No login service is connected' : 'لا توجد خدمة دخول متصلة'}</h2>
        <p>{isEnglish ? 'Passwords are hashed in the backend and tokens are signed server-side.' : 'يتم تشفير كلمات المرور في الخادم وتوقيع الرموز داخله.'}</p>
        <form className="auth-form" onSubmit={submit}>
          <label className="form-field"><span>{isEnglish ? 'Username' : 'اسم المستخدم'}</span><input value={username} onChange={(event) => setUsername(event.target.value)} required autoComplete="username" /></label>
          <label className="form-field"><span>{isEnglish ? 'Password' : 'كلمة المرور'}</span><input type="password" minLength={isRegister ? 12 : 1} value={password} onChange={(event) => setPassword(event.target.value)} required autoComplete={isRegister ? 'new-password' : 'current-password'} /></label>
          {isRegister && <label className="form-field"><span>{isEnglish ? 'Role' : 'الدور'}</span><select value={role} onChange={(event) => setRole(event.target.value)}><option value="viewer">Viewer</option><option value="researcher">Researcher</option></select></label>}
          <button className="button button-primary" type="submit" disabled={busy}>{busy ? '…' : (isEnglish ? (isRegister ? 'Create account' : 'Sign in') : (isRegister ? 'إنشاء الحساب' : 'تسجيل الدخول'))}</button>
        </form>
        <div className="auth-unavailable-warning"><ShieldAlert size={16} />{isEnglish ? 'Research-only access. Never reuse production credentials.' : 'وصول بحثي فقط. لا تستخدم بيانات اعتماد الإنتاج.'}</div>
        <div className="auth-unavailable-actions">
          <Link className="button button-primary" to="/assistant">{isEnglish ? 'Open research workspace' : 'افتح مساحة العمل البحثية'} <ArrowUpLeft size={15} /></Link>
          <Link className="button button-secondary" to="/profile">{isEnglish ? 'Local preferences' : 'التفضيلات المحلية'}</Link>
          {!isRegister && <Link className="auth-switch-link" to="/register">{isEnglish ? 'Registration status' : 'حالة إنشاء الحساب'}</Link>}
          {isRegister && <Link className="auth-switch-link" to="/login">{isEnglish ? 'Sign-in status' : 'حالة تسجيل الدخول'}</Link>}
        </div>
      </Panel>
    </div>
  );
}
