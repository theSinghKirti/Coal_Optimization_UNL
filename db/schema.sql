-- UPRVUNL Coal Optimization Platform — Database Schema
-- Target: Supabase Postgres, region ap-south-1 (Mumbai)
-- Run via Supabase SQL editor or `supabase db push`

create extension if not exists "uuid-ossp";

-- =========================================================
-- 1. Reference data
-- =========================================================

create table plants (
    plant_id        uuid primary key default uuid_generate_v4(),
    name            text not null unique,         -- 'Anpara', 'Obra B', 'Obra C', 'Harduaganj', 'Harduaganj Extn-II',
                                                    -- 'Parichha', 'Jawaharpur', 'Panki Extn'
    capacity_mw     numeric,
    is_pithead      boolean default false,
    coal_req_100plf_mt_day numeric,                -- coal requirement at 100% PLF, MT/day
    created_at      timestamptz default now()
);

create table coal_companies (
    company_id      uuid primary key default uuid_generate_v4(),
    name            text not null unique           -- NCL, BCCL, CCL, SECL, ECL ...
);

-- =========================================================
-- 2. Versioned rule registry (FSA / Bridge Linkage constraints)
--    Populated either by deterministic parse (Step 5) or
--    Claude extraction + human approval (Step 6)
-- =========================================================

create table documents (
    document_id     uuid primary key default uuid_generate_v4(),
    doc_type        text not null check (doc_type in
                      ('FSA','BRIDGE_LINKAGE','ORDER','LANDED_COST','VC','FORM_19','ACTION_PLAN','OTHER')),
    plant_id        uuid references plants(plant_id),
    counterparty    text,                           -- coal company / agency
    period_start    date,
    period_end      date,
    storage_path    text,                            -- Supabase Storage object path (or Drive link)
    file_name       text,
    uploaded_by     uuid,                            -- auth.users id
    uploaded_at     timestamptz default now(),
    template_version text                            -- for spreadsheet template mapping (Step 5 watch-out)
);

create table constraints_registry (
    constraint_id   uuid primary key default uuid_generate_v4(),
    plant_id        uuid references plants(plant_id) not null,
    company_id      uuid references coal_companies(company_id) not null,
    linkage_type    text not null check (linkage_type in ('FSA','BRIDGE_LINKAGE')),
    acq_lac_mt      numeric,                         -- Annual Contracted Quantity, Lac MT
    trigger_level_pct numeric,                       -- trigger level for SHAKTI-type penalties
    take_or_pay_pct numeric,
    gcv_band_kcal_kg_min numeric,
    gcv_band_kcal_kg_max numeric,
    valid_from      date,
    valid_to        date,
    source_document_id uuid references documents(document_id),
    source_clause   text,                            -- citation: clause / page reference
    extraction_confidence numeric,                   -- 0-1, set by Claude extraction (null if deterministic parse)
    status          text not null default 'pending' check (status in ('pending','approved','rejected','superseded')),
    version         int not null default 1,
    approved_by     uuid,
    approved_at     timestamptz,
    created_at      timestamptz default now()
);

-- append-only: never UPDATE a row in place once approved; insert a new version and mark old superseded
create index idx_constraints_plant on constraints_registry(plant_id);
create index idx_constraints_status on constraints_registry(status);

-- =========================================================
-- 3. Daily operational data (Step 3 form + future ingestion)
-- =========================================================

create table daily_fuel (
    entry_id        uuid primary key default uuid_generate_v4(),
    plant_id        uuid references plants(plant_id) not null,
    report_date     date not null,
    fuel_type       text not null check (fuel_type in ('COAL','LDO','LSHS')),
    monthly_linkage_mt numeric,
    opening_balance_mt numeric,
    receipt_mt      numeric,
    consumption_release_mt numeric,
    closing_balance_mt numeric,
    days_stock_cover numeric,
    rakes_received  numeric,
    generation_mu   numeric,
    plf_pct         numeric,
    reconciliation_flag boolean default false,        -- true if opening+receipt-consumption != closing (entry error)
    reconciliation_delta numeric,
    submitted_by    uuid,
    submitted_via   text default 'form' check (submitted_via in ('form','whatsapp_import','xlsx_import')),
    created_at      timestamptz default now(),
    unique (plant_id, report_date, fuel_type)
);

create index idx_daily_fuel_plant_date on daily_fuel(plant_id, report_date);

-- =========================================================
-- 4. Cost inputs (landed cost / VC / Form-19, from Step 5 parsing)
-- =========================================================

create table cost_inputs (
    cost_id         uuid primary key default uuid_generate_v4(),
    plant_id        uuid references plants(plant_id) not null,
    company_id      uuid references coal_companies(company_id),
    period_start    date,
    period_end      date,
    coal_procured_mt numeric,
    basic_rate_rs_mt numeric,
    freight_rs_mt   numeric,
    landed_cost_rs_mt numeric,
    gcv_kcal_kg     numeric,
    variable_cost_rs_kwh numeric,
    source_document_id uuid references documents(document_id),
    created_at      timestamptz default now()
);

create index idx_cost_inputs_plant on cost_inputs(plant_id);

-- =========================================================
-- 5. Optimization runs (Step 7)
-- =========================================================

create table optimization_runs (
    run_id          uuid primary key default uuid_generate_v4(),
    run_date        timestamptz default now(),
    objective       text default 'min_blended_landed_cost',
    status          text default 'completed',
    total_cost_rs   numeric,
    baseline_cost_rs numeric,
    savings_rs      numeric,
    constraints_version_snapshot jsonb,                -- which constraint rows / versions were active
    triggered_by    uuid,
    notes           text
);

create table optimization_allocations (
    allocation_id   uuid primary key default uuid_generate_v4(),
    run_id          uuid references optimization_runs(run_id) on delete cascade,
    plant_id        uuid references plants(plant_id),
    company_id      uuid references coal_companies(company_id),
    allocated_qty_mt numeric,
    landed_cost_rs_mt numeric,
    acq_utilisation_pct numeric
);

-- =========================================================
-- 6. Audit log (append-only)
-- =========================================================

create table audit_log (
    audit_id        uuid primary key default uuid_generate_v4(),
    actor_id        uuid,
    action          text not null,                      -- 'CONSTRAINT_APPROVED','CONSTRAINT_OVERRIDDEN','DOCUMENT_UPLOADED','RUN_TRIGGERED', etc.
    entity_type     text,
    entity_id       uuid,
    detail          jsonb,
    created_at      timestamptz default now()
);

-- =========================================================
-- 7. Row-Level Security (enable on every table; policies added per role)
-- =========================================================

alter table plants enable row level security;
alter table documents enable row level security;
alter table constraints_registry enable row level security;
alter table daily_fuel enable row level security;
alter table cost_inputs enable row level security;
alter table optimization_runs enable row level security;
alter table optimization_allocations enable row level security;
alter table audit_log enable row level security;

-- Example baseline policy (read for authenticated org users; write restricted by role claim)
-- Replace 'org_member' with your actual JWT role claim check.
create policy "org members can read plants" on plants
    for select using (auth.role() = 'authenticated');

-- Repeat / customize per-table policies for plant_operator / fuel_cell / management / auditor roles.

-- =========================================================
-- 8. IPP Variable Cost Tie-Ups & Action Plans (VC Reduction Rules)
-- =========================================================

create table ipp_vc_agreements (
    agreement_id    uuid primary key default uuid_generate_v4(),
    ipp_name        text not null,                         -- e.g. 'Bajaj Energy, Lalitpur TPS'
    ipp_vc          numeric not null,                      -- Variable Charges (Rs/Unit) for IPP
    unl_tps_name    text not null,                         -- e.g. 'Panki' or 'Harduaganj D'
    plant_id        uuid references plants(plant_id),      -- optional mapped plant_id
    unl_vc          numeric not null,                      -- Variable Charges (Rs/Unit) for UPRVUNL TPS
    tied_ipp_details text,                                 -- Tied IPP for VC reduction and Location
    minimization_rule text,                                -- Ways to minimise VC to keep UNL TPS in MoD above tied/comparable IPP
    target_vc       numeric,                               -- Target VC (Rs/Unit) after action
    period_start    date,
    period_end      date,
    created_at      timestamptz default now()
);

alter table ipp_vc_agreements enable row level security;
create policy "org members can read ipp_vc_agreements" on ipp_vc_agreements
    for select using (auth.role() = 'authenticated');

