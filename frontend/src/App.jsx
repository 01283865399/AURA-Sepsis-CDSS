import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import ClinicalDashboard from './ClinicalDashboard';
import HomePage from './HomePage';
import PatientsDirectory from './PatientsDirectory';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/patients" element={<PatientsDirectory />} />
        <Route path="/patients/:patientId" element={<ClinicalDashboard />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
