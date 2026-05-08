create extension if not exists vector;

create table if not exists public.gio_conversations (
  id uuid primary key,
  title text not null default 'New Chat',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.gio_messages (
  id uuid primary key,
  conversation_id uuid not null references public.gio_conversations(id) on delete cascade,
  role text not null,
  content text not null,
  provider text,
  model text,
  thinking_content text,
  embedding vector(1536),
  created_at timestamptz not null default now()
);

create table if not exists public.gio_conversation_summaries (
  id uuid primary key,
  conversation_id uuid not null unique references public.gio_conversations(id) on delete cascade,
  content text not null,
  model text,
  embedding vector(1536),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.gio_dream_entries (
  id uuid primary key,
  conversation_id uuid not null references public.gio_conversations(id) on delete cascade,
  title text not null,
  content text not null,
  model text,
  source_message_ids jsonb not null default '[]'::jsonb,
  embedding vector(1536),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists gio_conversations_updated_at_idx
  on public.gio_conversations(updated_at desc);

create index if not exists gio_messages_conversation_id_idx
  on public.gio_messages(conversation_id, created_at);

create index if not exists gio_conversation_summaries_conversation_id_idx
  on public.gio_conversation_summaries(conversation_id);

create index if not exists gio_dream_entries_conversation_id_idx
  on public.gio_dream_entries(conversation_id, updated_at desc);

-- Backfill the newest legacy hidden summary message for each conversation into the
-- dedicated summary table. Keep the old hidden rows for backward compatibility.
insert into public.gio_conversation_summaries (
  id,
  conversation_id,
  content,
  model,
  embedding,
  created_at,
  updated_at
)
select
  latest.id,
  latest.conversation_id,
  latest.content,
  latest.model,
  latest.embedding,
  latest.created_at,
  latest.created_at
from (
  select distinct on (conversation_id)
    id,
    conversation_id,
    content,
    model,
    embedding,
    created_at
  from public.gio_messages
  where role = 'summary'
  order by conversation_id, created_at desc
) as latest
on conflict (conversation_id) do nothing;
