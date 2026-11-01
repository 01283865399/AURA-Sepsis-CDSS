# MedlinePlus Connect integration

The project uses the existing provenance-aware downloader at
`scripts/medical_data/downloaders/medlineplus.py`; it deliberately does not
create a second HTTP client under a separate `fetchers` package.

## Language and content limits

MedlinePlus Connect documents problem-code responses in **English and
Spanish**. Arabic (`ar`) is rejected before any network request. Do not label
Connect results as Arabic or claim that it supplies Arabic content.

Connect is a code-to-patient-education link service. It can return zero matches
for a valid ICD-10-CM code; a missing response is preserved as a non-match.
Its response includes a page title, URL, HTML summary, and sometimes
synonyms/attribution. It is not a complete condition monograph API.

NLM states that some MedlinePlus material is public domain, while other
material is copyrighted/licensed (including specified medical encyclopedia
and drug content). Therefore raw responses and generated summaries are marked
`item_level_terms_and_attribution_review_required`; they are not published
automatically or labeled universally public domain.

Official references:

- [MedlinePlus Connect overview](https://medlineplus.gov/medlineplus-connect/)
- [MedlinePlus Connect web service technical documentation](https://medlineplus.gov/medlineplus-connect/web-service/)
- [Using MedlinePlus content](https://medlineplus.gov/about/using/usingcontent/)

## Fetching a bounded condition batch

After building `data/medical_content/final/complete/conditions.json`, select
the 500 `condition_content_candidate` records with exact ICD-10-CM crosswalks.
The CLI automatically narrows that file to these candidates and rejects more
than 500 distinct codes:

```powershell
.\venv\Scripts\python.exe -m scripts.medical_data.orchestrator `
  --sources medlineplus `
  --medlineplus-condition-file data/medical_content/final/complete/conditions.json `
  --medlineplus-languages en es
```

This makes at most one lookup per unique code and requested language, with a
half-second pause between requests. The 500 candidates in the current build
contain 279 unique ICD-10-CM codes, so this example issues at most 558 requests.
Each individual response and aggregate result are saved under
`data/medical_content/raw/medlineplus/` with SHA-256 provenance sidecars.

For individual code lookups, the existing CLI remains available:

```powershell
.\venv\Scripts\python.exe -m scripts.medical_data.orchestrator `
  --sources medlineplus --medlineplus-codes E11.9 J18.9 --language en
```

Only exact codes present on the supplied condition records are used; names are
not guessed into codes. Results remain draft-only and require source-specific
copyright, attribution, and clinical review before any broader reuse.
