import { useEffect, useState } from 'react';
import axios from 'axios';
import { ArrowLeft, ArrowRight, Bed, LoaderCircle, Plus, RefreshCw, Users } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import PatientFormModal from './PatientFormModal';
import './pages.css';

const API_URL = import.meta.env.VITE_CLINICAL_API_URL || 'http://127.0.0.1:8000';

export default function PatientsDirectory() {
  const navigate = useNavigate();
  const [patients, setPatients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showAddPatient, setShowAddPatient] = useState(false);

  const loadPatients = async () => {
    setLoading(true);
    setError('');
    try {
      const response = await axios.get(`${API_URL}/api/patients`, { timeout: 10000 });
      setPatients(response.data);
    } catch (requestError) {
      setError(requestError.response?.data?.detail || 'Could not load the patient directory. Check that the API is running and try again.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadPatients();
  }, []);

  const openPatient = (patient) => navigate(`/patients/${patient.patient_id}`);

  return (
    <main className="directory-page">
      <header className="directory-header">
        <Link className="directory-brand" to="/"><span><Users size={19} /></span>MEDIMIND <b>AI</b></Link>
        <div className="directory-header-actions">
          <Link className="directory-home-link" to="/"><ArrowLeft size={16} /> Home</Link>
          <button className="directory-primary-button directory-add-button" type="button" onClick={() => setShowAddPatient(true)}><Plus size={17} /> Add Patient</button>
        </div>
      </header>

      <section className="directory-main">
        <div className="directory-title-row">
          <div><p className="directory-eyebrow">CARE WORKSPACE</p><h1>Patients</h1><p className="directory-subtitle">Select a patient to open their clinical dashboard.</p></div>
          <button className="directory-refresh" type="button" onClick={() => void loadPatients()} disabled={loading} aria-label="Refresh patients"><RefreshCw size={16} className={loading ? 'directory-spin' : ''} /></button>
        </div>

        <div className="directory-storage-note"><strong>Development environment:</strong> Patient storage is not configured for clinical use. Do not use identifiable real patient data.</div>
        {error && <div className="directory-error" role="alert">{error}</div>}
        {loading ? (
          <div className="directory-loading"><LoaderCircle className="directory-spin" size={22} /> Loading patients…</div>
        ) : patients.length ? (
          <div className="patient-card-grid">
            {patients.map((patient) => (
              <button className="patient-card" type="button" key={patient.patient_id} onClick={() => openPatient(patient)}>
                <span className="patient-avatar">{patient.name.trim().charAt(0).toUpperCase()}</span>
                <span className="patient-card-main"><strong>{patient.name}</strong><span>Age {patient.age} · {patient.gender}</span></span>
                <span className="patient-bed"><Bed size={14} /> Bed {patient.bed_number}</span>
                <span className={`patient-risk-badge ${patient.risk_tier === 'High' ? 'risk-high' : patient.risk_tier === 'Medium' ? 'risk-medium' : patient.risk_tier === 'Low' ? 'risk-low' : 'risk-unknown'}`}>{patient.risk_tier || 'Not assessed'}</span>
                <ArrowRight className="patient-card-arrow" size={17} />
              </button>
            ))}
          </div>
        ) : !error ? (
          <section className="directory-empty"><span><Users size={25} /></span><h2>No patients yet</h2><p>Add a patient record to open a patient-specific assessment dashboard.</p><button className="directory-primary-button" type="button" onClick={() => setShowAddPatient(true)}><Plus size={17} /> Add Patient</button></section>
        ) : null}
      </section>
      <footer className="directory-footer">MediMind AI · Research decision-support workspace</footer>
      {showAddPatient && <PatientFormModal onClose={() => setShowAddPatient(false)} onCreated={(patient) => navigate(`/patients/${patient.patient_id}`)} />}
    </main>
  );
}
