-- Optional Supabase table policies for Nexora user-owned data.
-- Apply these only if these tables are created in Supabase.

-- Expected shared shape:
--   id uuid primary key default gen_random_uuid()
--   user_id uuid not null references auth.users(id) on delete cascade
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
  using (auth.uid() = user_id);
drop policy if exists "Users can write own projects" on public.projects;
create policy "Users can write own projects"
  on public.projects for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

drop policy if exists "Users can read own workflows" on public.workflows;
create policy "Users can read own workflows"
  on public.workflows for select
  using (auth.uid() = user_id);
drop policy if exists "Users can write own workflows" on public.workflows;
create policy "Users can write own workflows"
  on public.workflows for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

drop policy if exists "Users can read own memory" on public.memory;
create policy "Users can read own memory"
  on public.memory for select
  using (auth.uid() = user_id);
drop policy if exists "Users can write own memory" on public.memory;
create policy "Users can write own memory"
  on public.memory for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

drop policy if exists "Users can read own audit logs" on public.audit_logs;
create policy "Users can read own audit logs"
  on public.audit_logs for select
  using (auth.uid() = user_id);
drop policy if exists "Users can insert own audit logs" on public.audit_logs;
create policy "Users can insert own audit logs"
  on public.audit_logs for insert
  with check (auth.uid() = user_id);

drop policy if exists "Users can read own API keys" on public.api_keys;
create policy "Users can read own API keys"
  on public.api_keys for select
  using (auth.uid() = user_id);
drop policy if exists "Users can manage own API keys" on public.api_keys;
create policy "Users can manage own API keys"
  on public.api_keys for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

drop policy if exists "Users can read own settings" on public.user_settings;
create policy "Users can read own settings"
  on public.user_settings for select
  using (auth.uid() = user_id);
drop policy if exists "Users can manage own settings" on public.user_settings;
create policy "Users can manage own settings"
  on public.user_settings for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);
