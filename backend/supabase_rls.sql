-- Optional Supabase table policies for Nexora user-owned data.
-- Apply these only if these tables are created in Supabase.
-- Nexora uses Clerk for identity. Store Clerk user ids in user_id.

-- Expected shared shape:
--   id uuid primary key default gen_random_uuid()
--   user_id text not null
--   created_at timestamptz not null default now()
--   updated_at timestamptz not null default now()

alter table if exists public.projects enable row level security;
alter table if exists public.workflows enable row level security;
alter table if exists public.memory enable row level security;
alter table if exists public.audit_logs enable row level security;
alter table if exists public.api_keys enable row level security;
alter table if exists public.user_settings enable row level security;

drop policy if exists "Users can read own projects" on public.projects;
create policy "Users can read own projects"
  on public.projects for select
  to authenticated
  using ((auth.jwt() ->> 'sub') = user_id);
drop policy if exists "Users can write own projects" on public.projects;
create policy "Users can write own projects"
  on public.projects for all
  to authenticated
  using ((auth.jwt() ->> 'sub') = user_id)
  with check ((auth.jwt() ->> 'sub') = user_id);

drop policy if exists "Users can read own workflows" on public.workflows;
create policy "Users can read own workflows"
  on public.workflows for select
  to authenticated
  using ((auth.jwt() ->> 'sub') = user_id);
drop policy if exists "Users can write own workflows" on public.workflows;
create policy "Users can write own workflows"
  on public.workflows for all
  to authenticated
  using ((auth.jwt() ->> 'sub') = user_id)
  with check ((auth.jwt() ->> 'sub') = user_id);

drop policy if exists "Users can read own memory" on public.memory;
create policy "Users can read own memory"
  on public.memory for select
  to authenticated
  using ((auth.jwt() ->> 'sub') = user_id);
drop policy if exists "Users can write own memory" on public.memory;
create policy "Users can write own memory"
  on public.memory for all
  to authenticated
  using ((auth.jwt() ->> 'sub') = user_id)
  with check ((auth.jwt() ->> 'sub') = user_id);

drop policy if exists "Users can read own audit logs" on public.audit_logs;
create policy "Users can read own audit logs"
  on public.audit_logs for select
  to authenticated
  using ((auth.jwt() ->> 'sub') = user_id);
drop policy if exists "Users can insert own audit logs" on public.audit_logs;
create policy "Users can insert own audit logs"
  on public.audit_logs for insert
  to authenticated
  with check ((auth.jwt() ->> 'sub') = user_id);

drop policy if exists "Users can read own API keys" on public.api_keys;
create policy "Users can read own API keys"
  on public.api_keys for select
  to authenticated
  using ((auth.jwt() ->> 'sub') = user_id);
drop policy if exists "Users can manage own API keys" on public.api_keys;
create policy "Users can manage own API keys"
  on public.api_keys for all
  to authenticated
  using ((auth.jwt() ->> 'sub') = user_id)
  with check ((auth.jwt() ->> 'sub') = user_id);

drop policy if exists "Users can read own settings" on public.user_settings;
create policy "Users can read own settings"
  on public.user_settings for select
  to authenticated
  using ((auth.jwt() ->> 'sub') = user_id);
drop policy if exists "Users can manage own settings" on public.user_settings;
create policy "Users can manage own settings"
  on public.user_settings for all
  to authenticated
  using ((auth.jwt() ->> 'sub') = user_id)
  with check ((auth.jwt() ->> 'sub') = user_id);
