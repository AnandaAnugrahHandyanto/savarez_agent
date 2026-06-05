create table public.profiles (
  id uuid primary key,
  owner_id uuid not null
);

alter table public.profiles enable row level security;

create policy "profiles own rows"
on public.profiles
for select
to authenticated
using (auth.uid() = owner_id);
