import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Activity,
  BookOpen,
  ChevronLeft,
  ChevronRight,
  Database,
  FileText,
  Link2,
  LoaderCircle,
  Search,
  Sparkles,
  X,
} from 'lucide-react';
import { modelApi, getApiError } from '../../api/client';

const COLLECTIONS = [
  { id: 'conditions', label: 'Conditions', labelAr: 'الأمراض', icon: Activity },
  { id: 'symptoms', label: 'HPO concepts', labelAr: 'مفاهيم HPO', icon: Sparkles },
  { id: 'symptom_terms', label: 'Symptom terms', labelAr: 'مصطلحات الأعراض', icon: FileText },
  { id: 'symptom2disease_reports', label: 'Symptom narratives', labelAr: 'روايات الأعراض', icon: FileText },
  { id: 'associations', label: 'Associations', labelAr: 'الارتباطات', icon: Link2 },
  { id: 'qa', label: 'Q&A', labelAr: 'أسئلة وأجوبة', icon: BookOpen },
  { id: 'icd10_index', label: 'ICD-10-CM', labelAr: 'رموز ICD-10-CM', icon: Database },
  { id: 'specialists', label: 'Specialists', labelAr: 'التخصصات', icon: Activity },
  { id: 'emergency_signs', label: 'Emergency signs', labelAr: 'علامات الطوارئ', icon: Activity },
  { id: 'references', label: 'References', labelAr: 'المراجع', icon: Link2 },
];

const getRecordTitle = (record, collection, english) => {
  if (collection === 'conditions') return record.condition_en || record.condition_id;
  if (collection === 'symptoms') return record.name_en || record.phenotype_id;
  if (collection === 'symptom_terms') return record.name_en || record.symptom_id;
  if (collection === 'symptom2disease_reports') return record.source_label || record.report_id;
  if (collection === 'associations') {
    return `${record.condition_name_source_text || record.condition_source_id} → ${record.symptom_name_source_text || record.symptom_source_id}`;
  }
  if (collection === 'qa') return record.question_en;
  if (collection === 'icd10_index') return `${record.code} · ${record.coding_system}`;
  return english ? 'Source record' : 'سجل مصدر';
};

function getRecordDetail(record, collection) {
  if (collection === 'conditions') {
    return record.description?.long_en
      || record.healthcare_rag_documents?.[0]?.content_en
      || record.selection_policy;
  }
  if (collection === 'symptoms') return record.definition_source_text;
  if (collection === 'symptom_terms') return record.record_type;
  if (collection === 'symptom2disease_reports') return record.patient_narrative_en;
  if (collection === 'associations') return record.association_status;
  if (collection === 'qa') return record.answer_en;
  if (collection === 'icd10_index') return record.condition_ids?.join(', ');
  if (collection === 'references') return record.url;
  return null;
}

function useResourcePage(collection, query, offset) {
  const searchQuery = collection === 'qa' ? query.trim() : '';
  return useQuery({
    queryKey: ['complete-medical-resource', collection, searchQuery, offset],
    queryFn: async () => {
      const url = searchQuery
        ? '/api/v1/medical-content/complete-drafts/qa/search'
        : `/api/v1/medical-content/complete-drafts/${collection}`;
      const params = searchQuery
        ? { q: searchQuery, offset, limit: 20 }
        : { offset, limit: 20 };
      return (await modelApi.get(url, { params })).data;
    },
    retry: false,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });
}

export default function ResourceLibrary({ isEnglish, onClose, onUseRecord }) {
  const [collection, setCollection] = useState('conditions');
  const [query, setQuery] = useState('');
  const [offset, setOffset] = useState(0);
  const page = useResourcePage(collection, query, offset);
  const coverage = useQuery({
    queryKey: ['complete-medical-resource-coverage'],
    queryFn: async () => (
      await modelApi.get('/api/v1/medical-content/complete-drafts/coverage')
    ).data,
    retry: false,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

  const selectedCollection = COLLECTIONS.find((item) => item.id === collection);
  const records = page.data?.records || [];
  const range = useMemo(
    () => ({
      first: page.data?.total ? offset + 1 : 0,
      last: Math.min(offset + records.length, page.data?.total || 0),
    }),
    [offset, page.data?.total, records.length],
  );

  const selectCollection = (nextCollection) => {
    setCollection(nextCollection);
    setOffset(0);
  };

  return (
    <aside className="resource-library" aria-label={isEnglish ? 'Medical source library' : 'مكتبة المصادر الطبية'}>
      <header className="resource-library-header">
        <div className="resource-library-title">
          <span className="resource-library-icon"><BookOpen size={17} /></span>
          <div>
            <strong>{isEnglish ? 'Source library' : 'مكتبة المصادر'}</strong>
            <small>{isEnglish ? 'Browse connected datasets' : 'تصفّح مجموعات البيانات المرتبطة'}</small>
          </div>
        </div>
        <button type="button" className="resource-close" onClick={onClose} aria-label={isEnglish ? 'Close resources' : 'إغلاق المصادر'}>
          <X size={17} />
        </button>
      </header>

      <div className="resource-coverage">
        <span className="resource-coverage-icon"><Database size={15} /></span>
        <div>
          <strong>{coverage.data?.counts?.conditions?.toLocaleString() || '—'}</strong>
          <span>{isEnglish ? 'condition terms' : 'مصطلح مرض'}</span>
        </div>
        <div>
          <strong>{coverage.data?.counts?.qa?.toLocaleString() || '—'}</strong>
          <span>{isEnglish ? 'Q&A records' : 'سؤال وجواب'}</span>
        </div>
      </div>

      <div className="resource-tabs" role="tablist" aria-label={isEnglish ? 'Source collections' : 'مجموعات المصادر'}>
        {COLLECTIONS.map(({ id, label, labelAr, icon: Icon }) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={collection === id}
            className={collection === id ? 'resource-tab resource-tab-active' : 'resource-tab'}
            onClick={() => selectCollection(id)}
          >
            <Icon size={14} />
            <span>{isEnglish ? label : labelAr}</span>
          </button>
        ))}
      </div>

      <label className="resource-search">
        <Search size={15} />
        <input
          type="search"
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setOffset(0);
          }}
          placeholder={collection === 'qa'
            ? (isEnglish ? 'Search English Q&A…' : 'ابحث في Q&A الإنجليزية…')
            : (isEnglish ? 'Search this page…' : 'ابحث في الصفحة الحالية…')}
          aria-label={isEnglish ? 'Search resources' : 'البحث في المصادر'}
        />
        {query && <button type="button" onClick={() => setQuery('')} aria-label={isEnglish ? 'Clear search' : 'مسح البحث'}><X size={13} /></button>}
      </label>

      {collection !== 'qa' && query.trim() && (
        <p className="resource-search-note">
          {isEnglish
            ? 'Search filters the records on this page only.'
            : 'يبحث ضمن سجلات الصفحة الحالية فقط.'}
        </p>
      )}

      <div className="resource-results" aria-live="polite">
        {page.isPending && (
          <div className="resource-state"><LoaderCircle className="spin" size={20} />{isEnglish ? 'Loading source records…' : 'جارٍ تحميل سجلات المصدر…'}</div>
        )}
        {page.isError && (
          <div className="resource-state resource-state-error">
            <Database size={18} />
            <strong>{isEnglish ? 'Source service unavailable' : 'خدمة المصادر غير متاحة'}</strong>
            <span>{getApiError(page.error)}</span>
          </div>
        )}
        {!page.isPending && !page.isError && records.length === 0 && (
          <div className="resource-state">
            <Search size={18} />
            <span>{isEnglish ? 'No records found.' : 'لم يتم العثور على سجلات.'}</span>
          </div>
        )}
        {records.filter((record) => {
          if (!query.trim() || collection === 'qa') return true;
          const searchable = [
            getRecordTitle(record, collection, isEnglish),
            getRecordDetail(record, collection),
            record.condition_id,
            record.phenotype_id,
            record.code,
          ].filter(Boolean).join(' ').toLocaleLowerCase();
          return searchable.includes(query.trim().toLocaleLowerCase());
        }).map((record, index) => {
          const title = getRecordTitle(record, collection, isEnglish);
          const detail = getRecordDetail(record, collection);
          const reference = record.source_references?.find((item) => item.url?.startsWith('https://'))
            || record.references?.find((item) => item.url?.startsWith('https://'));
          return (
            <article className="resource-record" key={record.condition_id || record.phenotype_id || record.symptom_id || record.association_id || record.qa_id || record.report_id || record.code || record.reference_id || index}>
              <div className="resource-record-top">
                <span className="resource-record-kind">{selectedCollection?.label}</span>
                {record.not_for_clinical_use && <span className="resource-draft-badge">{isEnglish ? 'Draft' : 'مسودة'}</span>}
              </div>
              <h3>{title}</h3>
              {collection === 'qa' && record.answer_en
                ? <p className="resource-answer">{record.answer_en}</p>
                : detail && <p className="resource-detail">{detail}</p>}
              {collection === 'conditions' && record.icd10_codes?.length > 0 && (
                <div className="resource-code-list">
                  {record.icd10_codes.slice(0, 4).map((code) => <code key={code}>{code}</code>)}
                </div>
              )}
              {collection === 'symptom2disease_reports' && record.source_dataset_url && (
                <a className="resource-source-link" href={record.source_dataset_url} target="_blank" rel="noreferrer"><Link2 size={12} />{isEnglish ? 'Dataset source' : 'مصدر البيانات'}</a>
              )}
              {reference?.url && <a className="resource-source-link" href={reference.url} target="_blank" rel="noreferrer"><Link2 size={12} />{reference.source || (isEnglish ? 'Source' : 'المصدر')}</a>}
              <button type="button" className="resource-use-button" onClick={() => onUseRecord(title)}>
                {isEnglish ? 'Add to message' : 'إضافة إلى الرسالة'}
                <ChevronLeft size={14} />
              </button>
            </article>
          );
        })}
      </div>

      {page.data && (
        <footer className="resource-pagination">
          <span>{range.first}–{range.last} {isEnglish ? 'of' : 'من'} {page.data.total?.toLocaleString()}</span>
          <div>
            <button type="button" disabled={offset === 0 || page.isFetching} onClick={() => setOffset((value) => Math.max(0, value - 20))} aria-label={isEnglish ? 'Previous page' : 'الصفحة السابقة'}><ChevronRight size={16} /></button>
            <button type="button" disabled={offset + 20 >= (page.data.total || 0) || page.isFetching} onClick={() => setOffset((value) => value + 20)} aria-label={isEnglish ? 'Next page' : 'الصفحة التالية'}><ChevronLeft size={16} /></button>
          </div>
        </footer>
      )}

      {coverage.isError && <p className="resource-footnote">{isEnglish ? 'Coverage statistics are not available.' : 'إحصاءات التغطية غير متاحة.'}</p>}
      <p className="resource-footnote">{isEnglish ? 'Source data is unreviewed research content; not for clinical use.' : 'بيانات المصدر محتوى بحثي غير مراجع؛ غير مخصص للاستخدام السريري.'}</p>
    </aside>
  );
}
