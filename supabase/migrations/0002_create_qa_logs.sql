-- Migration: create public.qa_logs for /chat + /mida-assistant session history
-- Run in: Supabase Dashboard -> SQL Editor -> New query -> paste -> Run
-- (publishable key cannot run DDL; this must be executed as a project owner)

create table if not exists public.qa_logs (
  id bigint generated always as identity primary key,
  endpoint text not null,
  user_message text not null,
  answer text not null,
  extra jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

alter table public.qa_logs enable row level security;

drop policy if exists "Allow anon insert" on public.qa_logs;

-- Writes only, no anon reads — qa_logs can contain merchant-identifying
-- questions, unlike the todos demo table.
create policy "Allow anon insert" on public.qa_logs
  for insert to anon with check (true);
