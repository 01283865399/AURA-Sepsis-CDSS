import { useState } from 'react';
import { ArrowRight, HeartPulse, ShieldCheck, Sparkles } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import PatientFormModal from './PatientFormModal';
import './pages.css';

export default function HomePage() {
  const navigate = useNavigate();
  const [showAddPatient, setShowAddPatient] = useState(false);

  return (
    <main className="landing-page">
      <div className="landing-orb landing-orb-one" />
      <div className="landing-orb landing-orb-two" />
      <header className="landing-header">
        <a className="landing-brand" href="/" aria-label="MediMind AI home">
          <span className="landing-brand-icon"><HeartPulse size={23} /></span>
          <span>MEDIMIND <b>AI</b></span>
        </a>
        <span className="landing-status"><span /> Clinical decision support workspace</span>
      </header>

      <section className="landing-content">
        <div className="landing-copy">
          <p className="landing-kicker"><Sparkles size={15} /> EARLY WARNING · CLINICAL WORKFLOW</p>
          <h1>Clinical insight,<br /><span>centered on each patient.</span></h1>
          <p className="landing-description">A unified workspace for reviewing patient observations, model estimates, and explainable decision-support information.</p>
          <div className="landing-actions">
            <button className="directory-primary-button landing-primary" type="button" onClick={() => setShowAddPatient(true)}>+ Add New Patient <ArrowRight size={17} /></button>
            <button className="directory-secondary-button" type="button" onClick={() => navigate('/patients')}>View All Patients</button>
          </div>
          <p className="landing-disclaimer"><ShieldCheck size={15} /> Research and decision-support software. Not a substitute for clinician judgment or validated medical equipment.</p>
        </div>
        <div className="landing-visual" aria-hidden="true">
          <div className="visual-grid" />
          <div className="visual-ring visual-ring-outer" />
          <div className="visual-ring visual-ring-inner" />
          <div className="visual-cross"><HeartPulse size={76} strokeWidth={1.25} /></div>
          <div className="visual-node node-top"><span /><b>OBSERVATIONS</b><small>Patient-centered review</small></div>
          <div className="visual-node node-right"><span /><b>MODEL INSIGHT</b><small>Explainable estimate</small></div>
          <div className="visual-node node-bottom"><span /><b>CLINICAL CONTEXT</b><small>Review with care team</small></div>
          <div className="visual-line visual-line-one" />
          <div className="visual-line visual-line-two" />
        </div>
      </section>
      <footer className="landing-footer"><span>MediMind AI · Research decision support</span><span>Patient storage must be configured for development</span></footer>
      {showAddPatient && <PatientFormModal onClose={() => setShowAddPatient(false)} onCreated={(patient) => navigate(`/patients/${patient.patient_id}`)} />}
    </main>
  );
}
