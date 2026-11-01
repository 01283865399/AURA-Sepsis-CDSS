import { Suspense, lazy } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import Layout from './components/Layout/Layout';

const Home = lazy(() => import('./pages/Home'));
const Landing = lazy(() => import('./pages/Landing'));
const Assistant = lazy(() => import('./pages/Assistant'));
const Dashboard = lazy(() => import('./pages/Dashboard'));
const History = lazy(() => import('./pages/History'));
const Profile = lazy(() => import('./pages/Profile'));
const About = lazy(() => import('./pages/About'));
const ResearchStatus = lazy(() => import('./pages/ResearchStatus'));
const LegalPage = lazy(() => import('./pages/LegalPage'));
const AuthUnavailable = lazy(() => import('./pages/AuthUnavailable'));
const NotFound = lazy(() => import('./pages/NotFound'));
const ModulePage = lazy(() => import('./pages/modules/ModulePage'));
const ClinicalDashboard = lazy(() => import('./ClinicalDashboard'));
const PatientsDirectory = lazy(() => import('./PatientsDirectory'));

function PageLoader() {
  return <div className="page-loader" role="status">جارٍ تحميل الصفحة…</div>;
}

export default function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<PageLoader />}>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route element={<Layout />}>
            <Route path="assistant" element={<Assistant />} />
            <Route path="models" element={<Home />} />
            <Route path="dashboard" element={<Dashboard />} />
            <Route path="history" element={<History />} />
            <Route path="labs/history" element={<Navigate to="/history?model=lab_ocr" replace />} />
            <Route path="labs" element={<Navigate to="/modules/lab_ocr" replace />} />
            <Route path="profile" element={<Profile />} />
            <Route path="about" element={<About />} />
            <Route path="research" element={<ResearchStatus />} />
            <Route path="disclaimer" element={<LegalPage />} />
            <Route path="privacy" element={<LegalPage />} />
            <Route path="terms" element={<LegalPage />} />
            <Route path="login" element={<AuthUnavailable />} />
            <Route path="register" element={<AuthUnavailable />} />
            <Route path="modules/:moduleId" element={<ModulePage />} />
            <Route path="patients" element={<PatientsDirectory />} />
            <Route path="patients/:patientId" element={<ClinicalDashboard />} />
            <Route path="*" element={<NotFound />} />
          </Route>
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}
