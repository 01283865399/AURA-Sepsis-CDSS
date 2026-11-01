import { useState } from 'react';
import axios from 'axios';
import { LoaderCircle, UserRound, X } from 'lucide-react';

const API_URL = import.meta.env.VITE_CLINICAL_API_URL || 'http://127.0.0.1:8000';

export default function PatientFormModal({ onClose, onCreated }) {
  const [name, setName] = useState('');
  const [age, setAge] = useState('');
  const [bedNumber, setBedNumber] = useState('');
  const [gender, setGender] = useState('Female');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const submitPatient = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError('');
    try {
      const response = await axios.post(`${API_URL}/api/patients`, {
        name: name.trim(),
        age: Number(age),
        bed_number: bedNumber.trim(),
        gender,
      }, { timeout: 10000 });
      onCreated(response.data);
    } catch (requestError) {
      const detail = requestError.response?.data?.detail;
      setError(typeof detail === 'string'
        ? detail
        : 'Could not save the patient. Check the entered values and confirm that the API is running.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="patient-modal-backdrop" role="presentation" onMouseDown={(event) => {
      if (event.target === event.currentTarget && !saving) onClose();
    }}>
      <section className="patient-modal" role="dialog" aria-modal="true" aria-labelledby="patient-modal-title">
        <button className="patient-modal-close" type="button" aria-label="Close" onClick={onClose} disabled={saving}><X size={18} /></button>
        <span className="patient-modal-icon"><UserRound size={20} /></span>
        <p className="directory-eyebrow">NEW PATIENT</p>
        <h2 id="patient-modal-title">Add patient</h2>
        <p className="patient-modal-copy">Create a directory entry to open a patient-specific dashboard.</p>
        <form onSubmit={submitPatient}>
          <label>Patient name<input autoFocus required maxLength={120} value={name} onChange={(event) => setName(event.target.value)} /></label>
          <div className="patient-form-row">
            <label>Age<input required type="number" min="0" max="120" value={age} onChange={(event) => setAge(event.target.value)} /></label>
            <label>Bed number<input required maxLength={32} value={bedNumber} onChange={(event) => setBedNumber(event.target.value)} /></label>
          </div>
          <label>Gender<select value={gender} onChange={(event) => setGender(event.target.value)}><option value="Female">Female</option><option value="Male">Male</option></select></label>
          <p className="patient-storage-note">Development environment only. Do not enter identifiable real patient data.</p>
          {error && <p className="patient-form-error" role="alert">{error}</p>}
          <button className="directory-primary-button patient-submit" type="submit" disabled={saving}>
            {saving ? <><LoaderCircle className="directory-spin" size={17} /> Saving…</> : '+ Add New Patient'}
          </button>
        </form>
      </section>
    </div>
  );
}
