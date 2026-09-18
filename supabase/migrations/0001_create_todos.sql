-- Migration: create public.todos for PY /db/todos endpoints
-- Run in: Supabase Dashboard -> SQL Editor -> New query -> paste -> Run
-- (publishable key cannot run DDL; this must be executed as a project owner)

create table if not exists public.todos (
  id bigint generated always as identity primary key,
  name text not null,
  created_at timestamptz not null default now()
);

alter table public.todos enable row level security;

drop policy if exists "Allow anon all" on public.todos;

create policy "Allow anon all" on public.todos
  for all to anon using (true) with check (true);
