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

create table if not exists public.gio_knowledge_documents (
  id uuid primary key,
  source_key text not null unique,
  title text not null,
  url text,
  tags jsonb not null default '[]'::jsonb,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.gio_knowledge_chunks (
  id uuid primary key,
  document_id uuid not null references public.gio_knowledge_documents(id) on delete cascade,
  chunk_index integer not null,
  content text not null,
  token_count integer not null default 0,
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

create index if not exists gio_knowledge_documents_source_key_idx
  on public.gio_knowledge_documents(source_key);

create index if not exists gio_knowledge_chunks_document_id_idx
  on public.gio_knowledge_chunks(document_id, chunk_index);

create index if not exists gio_knowledge_chunks_embedding_idx
  on public.gio_knowledge_chunks
  using ivfflat (embedding vector_cosine_ops)
  with (lists = 100);

create or replace function public.match_gio_knowledge_chunks(
  query_embedding_text text,
  match_count integer default 5,
  min_score double precision default 0.2
)
returns table (
  chunk_id uuid,
  document_id uuid,
  source_key text,
  title text,
  url text,
  tags jsonb,
  content text,
  score double precision
)
language sql
as $$
  select
    chunks.id as chunk_id,
    docs.id as document_id,
    docs.source_key,
    docs.title,
    docs.url,
    docs.tags,
    chunks.content,
    1 - (chunks.embedding <=> query_embedding_text::vector) as score
  from public.gio_knowledge_chunks as chunks
  join public.gio_knowledge_documents as docs on docs.id = chunks.document_id
  where chunks.embedding is not null
    and 1 - (chunks.embedding <=> query_embedding_text::vector) >= min_score
  order by chunks.embedding <=> query_embedding_text::vector
  limit greatest(match_count, 1);
$$;

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
