# Razzy Chat

Razzy Chat is a Flask-based personal chatbot server for Gio.

It currently exposes three main app surfaces:

- `/` - Razzy Dev Console
- `/razzy` - Razzy personal chat UI
- `/gio` - Gio Chat, a Supabase-backed ChatGPT-style interface

The project is built to support local and cloud model providers without splitting into five different half-finished apps.

## What exists right now

### Core app
- Flask API server
- SQLite-backed legacy/local conversation storage for the generic chat and Razzy routes
- basic security headers, CORS, and API key protection on protected routes
- lightweight rate limiting
- health endpoint

### Providers
- OpenAI
- Ollama
- Anthropic

### `/gio` features
- persistent conversations in Supabase
- conversation list and message history
- dynamic OpenAI model listing
- real OpenAI streaming over NDJSON
- message footer showing provider/model when available
- embeddings stored for user and assistant messages
- semantic recall from embeddings
- rolling summaries stored in a dedicated Supabase summary table when available, with backward compatibility for older hidden `summary` message rows
- first-pass Dream Mode storage and browse flow for reflection entries generated from conversation history

### `/razzy` features
- Razzy identity/profile endpoint
- Razzy session/chat endpoints
- Razzy memory remember/recall endpoints
- simple personal UI

### Twitter/X features
- status endpoint
- read helpers
- post / reply / quote / delete scaffold
- structural tests exist

Important: live Twitter/X posting is still blocked by X-side API enrollment/access, not just local code.

## Current reality, bluntly

This app is functional, but it is not fully production-clean yet.

Known important caveats:
- live traffic is currently being served by **Waitress**, not the Flask dev server
- `/gio` now has the dedicated live Supabase summary table in place, but the embeddings pipeline still needs a fuller end-to-end production proof pass
- README used to be stale, and it still needed another reality pass after live verification

## Project layout

```text
app.py
requirements.txt
supabase_gio_schema.sql
TODO.md
unified_server/
  app_factory.py
  config.py
  database.py
  gio_repository.py
  gio_service.py
  memory.py
  models.py
  providers.py
  razzy_identity.py
  razzy_memory.py
  razzy_service.py
  repository.py
  security.py
  service.py
  supabase_client.py
  twitter_client.py
  twitter_service.py
  static/
    app.css
    app.js
    gio.css
    gio.html
    gio.js
    index.html
    razzy.html
tests/
```

## Requirements

- Python 3.13-ish environment already works here
- Ollama installed locally if you want local models
- OpenAI API key for OpenAI chat, embeddings, and `/gio` streaming
- Anthropic API key if you want Anthropic available
- Supabase project for `/gio`

## Installation

```bash
cd "/home/giosterr44/Documents/ruizTechServices/project/python/server/fucking Around/fuck-around-1"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Then fill in the env vars you actually need.

## Run locally

### Production-ish local run with Waitress

```bash
cd "/home/giosterr44/Documents/ruizTechServices/project/python/server/fucking Around/fuck-around-1"
source .venv/bin/activate
APP_RUNNER=waitress DEBUG=false USE_RELOADER=false python app.py
```

### Development run with Flask reloader

```bash
cd "/home/giosterr44/Documents/ruizTechServices/project/python/server/fucking Around/fuck-around-1"
source .venv/bin/activate
APP_RUNNER=flask DEBUG=true USE_RELOADER=true FLASK_ENV=development python app.py
```

Default local URLs:
- `http://127.0.0.1:8000`
- `http://0.0.0.0:8000`

## Routes

### Public routes
- `GET /`
- `GET /razzy`
- `GET /gio`
- `GET /gio/dreams`
- `GET /health`
- `GET /api/providers`
- `GET /api/razzy/profile`

### Generic chat routes (API key protected)
- `POST /api/conversations`
- `GET /api/conversations`
- `GET /api/conversations/<conversation_id>/messages`
- `POST /api/chat`

### Razzy routes (API key protected except profile)
- `POST /api/razzy/session`
- `POST /api/razzy/chat`
- `POST /api/razzy/remember`
- `GET /api/razzy/memory/<conversation_id>`

### Gio routes (API key protected)
- `GET /api/gio/models`
- `POST /api/gio/session`
- `GET /api/gio/conversations`
- `GET /api/gio/conversations/<conversation_id>/messages`
- `GET /api/gio/dreams`
- `GET /api/gio/dreams/<dream_id>`
- `POST /api/gio/conversations/<conversation_id>/dream`
- `POST /api/gio/chat`
- `POST /api/gio/chat/stream`

### Twitter/X routes (API key protected)
- `GET /api/twitter/status`
- `GET /api/twitter/me`
- `GET /api/twitter/posts/<post_id>`
- `GET /api/twitter/timeline/user/<user_id>`
- `POST /api/twitter/post`
- `POST /api/twitter/posts/<post_id>/reply`
- `POST /api/twitter/posts/<post_id>/quote`
- `DELETE /api/twitter/posts/<post_id>`

## API key behavior

Protected routes require:

```text
X-API-Key: your-api-key
```

If `API_KEY` is blank, protection behavior depends on the middleware/config, so do not assume blank means safe. Set a real key.

## Environment variables

### Core
```bash
FLASK_ENV=development
HOST=0.0.0.0
PORT=8000
API_KEY=change-me
ALLOWED_ORIGINS=*
```

### Provider defaults
```bash
DEFAULT_PROVIDER=ollama
DEFAULT_MODEL=lfm2.5-thinking:latest
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=lfm2.5-thinking:latest
```

### Gio / Supabase
```bash
SUPABASE_URL=
SUPABASE_PUBLISHABLE_KEY=
SUPABASE_SERVICE_ROLE_KEY=
GIO_DEFAULT_PROVIDER=openai
GIO_DEFAULT_MODEL=gpt-4.1-mini
GIO_CONVERSATIONS_TABLE=gio_conversations
GIO_MESSAGES_TABLE=gio_messages
GIO_SUMMARIES_TABLE=gio_conversation_summaries
GIO_DREAMS_TABLE=gio_dream_entries
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
GIO_RECENT_MESSAGES_LIMIT=12
GIO_RECALL_TOP_K=5
GIO_RECALL_MIN_SCORE=0.2
GIO_SUMMARY_TRIGGER_MESSAGES=8
GIO_SUMMARY_MODEL=gpt-4.1-mini
GIO_DREAM_MODEL=gpt-4.1-mini
GIO_DREAM_SOURCE_LIMIT=8
```

### Twitter/X
```bash
TWITTER_API_KEY=
TWITTER_API_SECRET=
TWITTER_ACCESS_TOKEN=
TWITTER_ACCESS_TOKEN_SECRET=
TWITTER_BEARER_TOKEN=
TWITTER_USER_ID=
TWITTER_BASE_URL=https://api.twitter.com
TWITTER_TIMEOUT_SECONDS=30
```

## Supabase setup for `/gio`

Run the SQL in:

```text
supabase_gio_schema.sql
```

inside the Supabase SQL Editor for your project.

Target schema includes:
- `gio_conversations`
- `gio_messages`
- `gio_conversation_summaries`
- vector embeddings on `gio_messages.embedding`
- optional vector embeddings on `gio_conversation_summaries.embedding`

Current live reality:
- `gio_conversations`, `gio_messages`, and `gio_conversation_summaries` now exist and are working
- live summary writes now go to `gio_conversation_summaries`
- backward compatibility remains for setups or older conversations that still only have hidden `summary` rows in `gio_messages`
- summary content is used by the backend context builder, but filtered out of normal `/gio` message history responses
- correction-heavy turns can now force a summary refresh sooner, so stale facts are less likely to linger after explicit user updates like “actually” or “correction:”

## How `/gio` context works right now

The app no longer sends the full raw conversation transcript every turn.

Current prompt assembly is roughly:

```text
system prompt
+ latest rolling summary
+ recalled older relevant messages from embeddings
+ recent message window
+ current user message
```

That is much better than brute-force replaying the entire chat forever.

### Known behavior worth knowing

- rolling summaries are not the same thing as long-term reflective memory, they are just compact conversation context for `/gio`
- explicit user corrections now get special handling so the summary can refresh sooner instead of waiting only for the older-context threshold
- Dream Mode should use its own storage path later, rather than reusing `gio_conversation_summaries`

## Streaming behavior

`POST /api/gio/chat/stream` now uses real OpenAI streaming.

Current transport format:
- `application/x-ndjson`

Current event types:
- `meta`
- `delta`
- `done`
- `error`

Important limitation:
- true streaming is currently implemented for the OpenAI `/gio` path
- other providers are not yet at parity in the streaming route

## Tests

Run the test suite with:

```bash
cd "/home/giosterr44/Documents/ruizTechServices/project/python/server/fucking Around/fuck-around-1"
source .venv/bin/activate
pytest
```

Current status during the latest pass:
- `30 passed`

Tests currently cover:
- auth
- health
- generic chat
- conversations
- Razzy flows
- Twitter/X structural behavior
- Gio context builder logic, semantic recall, and rolling summary behavior

What is still missing:
- fuller `/gio` endpoint-level test coverage
- stronger streaming contract tests

## Deployment notes

Current live setup on the Pi uses:
- systemd for the Flask service
- systemd for `cloudflared`
- Cloudflare Tunnel for remote access

Current live runtime reality:
- the `razzy-flask.service` unit is active
- the app is serving live traffic with `Server: waitress`
- the unit still starts `python app.py` from the project venv
- the next cleanup is to make the service's production mode explicit in systemd instead of relying on app defaults

## Security notes

- `.env` is ignored by git, but do not get lazy about secrets
- some real credentials were used during development, so key rotation is still smart before broader sharing
- keep this repo private until you finish the cleanup pass if you care about not being reckless

## Recommended next work

Read:
- `TODO.md`

Best next steps, in order:
1. re-verify `/gio` behavior after any service restart or deployment change
2. design Dream Mode storage and schema as a separate path from `gio_conversation_summaries`
3. document the embedding/search architecture more explicitly
4. only then consider trimming fallback summary behavior

## Quick curl examples

### Health
```bash
curl http://127.0.0.1:8000/health
```

### Create generic conversation
```bash
curl -X POST http://127.0.0.1:8000/api/conversations \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"title":"Test Chat"}'
```

### Create Gio conversation
```bash
curl -X POST http://127.0.0.1:8000/api/gio/session \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"title":"New Chat"}'
```

### Send Gio chat message
```bash
curl -X POST http://127.0.0.1:8000/api/gio/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"conversation_id":"your-conversation-id","message":"Hello","provider":"openai","model":"gpt-4.1-mini"}'
```

## Final note

This app is finally converging into one real source of truth.
That part is good.

The next mistakes to avoid are:
- adding more routes without tightening deployment
- pretending partial memory architecture is final
- shipping repo junk or stale docs again
