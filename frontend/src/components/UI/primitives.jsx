import { AlertCircle, Check, LoaderCircle, UploadCloud } from 'lucide-react';
import { useLocale } from '../../hooks/useLocale';
import { cn } from '../../lib/utils';

export function Button({ children, variant = 'primary', className = '', ...props }) {
  return <button className={cn('button', `button-${variant}`, className)} {...props}>{children}</button>;
}

export function Panel({ children, className = '', ...props }) {
  return <section className={cn('panel', className)} {...props}>{children}</section>;
}

export function Field({ field, register, error, language = 'ar' }) {
  const label = language === 'ar' ? field.label : (field.labelEn || field.name);
  const controlProps = { id: field.name, ...register(field.name), required: field.required, 'aria-invalid': Boolean(error), 'aria-describedby': error ? `${field.name}-error` : undefined };
  return (
    <label className="form-field" htmlFor={field.name}>
      <span>{label}{field.required && <b aria-label="required"> *</b>}</span>
      {field.type === 'select' ? (
        <select {...controlProps}><option value="">اختر…</option>{field.options?.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select>
      ) : (
        <input {...controlProps} type={field.type || 'text'} min={field.min} max={field.max} step={field.step} placeholder={field.placeholder || ''} autoComplete="off" />
      )}
      {error && <small className="field-error" id={`${field.name}-error`} role="alert">{error.message}</small>}
    </label>
  );
}

export function FileUpload({ file, onChange, error, accept = 'image/jpeg,image/png,image/webp,image/bmp,image/tiff' }) {
  const { text } = useLocale();
  return (
    <label className={`file-drop ${error ? 'file-drop-error' : ''}`}>
      <input type="file" accept={accept} onChange={(event) => onChange(event.target.files?.[0] || null)} />
      <span className="file-icon"><UploadCloud size={21} /></span>
      <strong>{file?.name || text('اختر صورة للتحليل', 'Choose an image to analyze')}</strong>
      <small>{text('JPEG أو PNG أو WEBP · حتى 10 MB', 'JPEG, PNG, WEBP, BMP, or TIFF · up to 10 MB')}</small>
      {error && <em role="alert"><AlertCircle size={14} /> {error}</em>}
      {file && <span className="file-ready"><Check size={14} /> {text('جاهز للإرسال', 'Ready to upload')}</span>}
    </label>
  );
}

export function Loading({ label }) {
  const { text } = useLocale();
  return <span className="loading-inline" role="status"><LoaderCircle size={17} className="spin" />{label || text('جارٍ التحميل', 'Loading')}</span>;
}

export function Alert({ children, tone = 'error' }) {
  return <div className={`alert alert-${tone}`} role={tone === 'error' ? 'alert' : 'status'}><AlertCircle size={17} />{children}</div>;
}

export function Badge({ children, tone = 'neutral' }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}
