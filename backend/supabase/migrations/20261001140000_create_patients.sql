-- Patient directory schema for the FastAPI service.
-- The API accesses this table with a server-side Supabase secret/service-role key.
-- Never expose that key in the React application.

create table if not exists public.patients (
    patient_id uuid primary key default gen_random_uuid(),
    name text not null check (char_length(btrim(name)) between 1 and 120),
    age smallint not null check (age between 0 and 120),
    bed_number text not null check (char_length(btrim(bed_number)) between 1 and 32),
    gender text not null check (gender in ('Female', 'Male')),
    risk_tier text not null default 'Not assessed',
    vital_signs jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create index if not exists patients_created_at_idx
    on public.patients (created_at desc);

alter table public.patients enable row level security;

-- No policies are granted to anon/authenticated clients.
-- FastAPI uses the server-only secret key, which bypasses RLS.
revoke all on table public.patients from anon, authenticated;
grant select, insert, update, delete on table public.patients to service_role;
