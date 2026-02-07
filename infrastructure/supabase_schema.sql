-- PreGrade (minimal multi-tenant SaaS foundation)
-- Apply in Supabase SQL editor.

create table if not exists tenants (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  created_at timestamptz not null default now()
);

create table if not exists api_keys (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  name text not null,
  key_hash text not null unique,
  created_at timestamptz not null default now(),
  revoked_at timestamptz null
);

create index if not exists api_keys_tenant_id_idx on api_keys(tenant_id);

create table if not exists usage_events (
  id bigserial primary key,
  tenant_id uuid null references tenants(id) on delete set null,
  api_key_id uuid null references api_keys(id) on delete set null,
  request_id text null,
  route text not null,
  status_code int not null,
  gatekeeper_accepted boolean null,
  reason_codes jsonb null,
  duration_ms int null,
  created_at timestamptz not null default now()
);

create index if not exists usage_events_tenant_id_idx on usage_events(tenant_id);
create index if not exists usage_events_created_at_idx on usage_events(created_at);
