# Supabase patient directory setup

The patient directory supports `sqlite` (local development default) and `supabase`
storage. FastAPI is the only component that talks to Supabase. Do not put a
Supabase secret/service-role key in Vite variables, React code, or a committed
environment file.

## 1. Create the table

In Supabase, open **SQL Editor**, paste and run
[`backend/supabase/migrations/20261001140000_create_patients.sql`](../backend/supabase/migrations/20261001140000_create_patients.sql).

The migration enables row-level security and grants table access only to
`service_role`. Browser clients must not access this table directly.

## 2. Install the backend client

```powershell
.\venv\Scripts\python.exe -m pip install -r backend\requirements-supabase.txt
```

## 3. Configure the FastAPI process

Set the values in the environment that launches Uvicorn:

```powershell
$env:PATIENT_STORAGE_BACKEND = "supabase"
$env:SUPABASE_URL = "https://YOUR_PROJECT_REF.supabase.co"
$env:SUPABASE_SECRET_KEY = "YOUR_SERVER_ONLY_SECRET_KEY"
.\venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Use the current server-side secret key from the Supabase API keys page. If the
project only provides the legacy key, `SUPABASE_SERVICE_ROLE_KEY` is accepted
as a server-side fallback. Never use either key in frontend environment
variables. Restart the API after changing environment values.

When `PATIENT_STORAGE_BACKEND=supabase` is selected, missing settings or
connection failures return an explicit API error; the service does not silently
fall back to SQLite. To switch back to local development storage, set
`PATIENT_STORAGE_BACKEND=sqlite` or unset it.

## Data and deployment warning

The current API stores directory demographics and the initial Age/Gender fields.
It does not persist a measurement history or model assessments. The example
schema is for development; it does not by itself provide authentication,
authorization, audit logging, retention controls, backups, or clinical
compliance. Do not store identifiable patient information until the Supabase
project and application have been reviewed and configured for the applicable
health-data regulations.

When SQLite is selected, the active local database is
`data/patients.sqlite3`. The pre-refactor database snapshot is retained beside
it as `data/patients.sqlite3.pre-refactor`.
