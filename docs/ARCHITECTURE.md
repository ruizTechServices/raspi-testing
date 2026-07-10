# Architecture

Razzy Chat is a Flask + Waitress server on a Raspberry Pi 5, deployed via the
`razzy-flask.service` systemd unit and exposed publicly at
`razzy.justtools.net` through a Cloudflare Tunnel.

**Purpose:** Gio chats with Razzy through WhatsApp. This site *supplements*
that with buttons and simple interfaces — dashboards, system controls, and
info widgets — not a chat UI. Razzy's web chat endpoints intentionally return
`410 Gone`; keep new features button-shaped.

## Layers

```
web/            HTTP blueprints (routing, status codes, JSON shapes — no business logic)
   │
services        chat/service.py · razzy/service.py · gio/service.py · twitter/service.py
   │            system/ (temperature, llm probes, ollama control) · integrations/ (public APIs)
   │
repositories    chat/repository.py (SQLite) · gio/repository.py (Supabase PostgREST)
   │
storage         data/chat.db · Supabase (embeddings, summaries, dreams)
```

Cross-cutting: `settings.py` (configuration), `security.py` (API key +
security headers), `core/` (shared prompt, conversation helpers, chat-turn
engine), `providers/` (OpenAI / Anthropic / Ollama adapters).

## Package map

| Package | Responsibility |
|---|---|
| `unified_server/app_factory.py` | Composition root: extensions, default service construction, blueprint registration. `create_app(service, razzy_service, twitter_service, gio_service)` — every service is injectable (this is how tests swap in fakes). |
| `unified_server/settings.py` | `Settings` dataclass loaded once from `.env` via `get_settings()`. Read lazily at call time — never import values at module level. `config.py` is a deprecated shim over it. |
| `unified_server/web/` | One blueprint factory per feature: `health`, `system`, `chat`, `gio`, `twitter`, `razzy` (profile + 410 stubs), `integrations`, `pages`. No `url_prefix`; paths are literal. |
| `unified_server/core/` | `prompts.py` (default system prompt), `conversations.py` (`ConversationStore` Protocol, `require_conversation`, `derive_auto_title`), `chat_engine.py` (`run_chat_turn` — the shared turn skeleton for ChatService/RazzyService). |
| `unified_server/chat/` | Local SQLite stack: models, database (schema + connections), repository, unified `MemoryService` (parameterized by `MemoryProfile`: `CHAT_PROFILE` / `RAZZY_PROFILE`), `ChatService`. |
| `unified_server/razzy/` | Razzy identity data + `RazzyService` (SQLite-backed; web chat removed, WhatsApp is the chat surface). |
| `unified_server/gio/` | Supabase-backed assistant, decomposed: `service.py` (facade), `chat.py` (turns + NDJSON streaming + reasoning extraction), `recall.py` (semantic recall), `summaries.py` (rolling summary), `dreams.py` (Dream Mode), `catalog.py` (model list/filter), `embeddings.py`, `heuristics.py`, `repository.py`, `supabase_client.py`. |
| `unified_server/providers/` | `ChatProvider` Protocol, one module per provider (lazy SDK clients), `ProviderRegistry` + model catalogs. |
| `unified_server/system/` | Pi telemetry and control: `PiTemperatureMonitor` (instance TTL cache, injectable reader/clock), LLM status probes, `systemctl_ollama` (sudo systemctl wrapper). |
| `unified_server/integrations/` | Free public-API widget clients (Open-Meteo, ipify, CoinGecko, Frankfurter, NASA APOD) over a shared `CachedHttpClient` (TTL cache per URL, injectable session/clock). |
| `unified_server/twitter/` | Self-contained X/Twitter v2 client (OAuth1) + validation service. |
| `unified_server/static/` | Vanilla HTML/CSS/JS, flat layout, per-feature file groups (`index.html`+`dashboard.js`+`widgets.js`, `console.*`, `gio.*`, `razzy.*`, shared `nav.js`/`app.css`). No build step. |

## Key decisions

**Two persistence stacks, one shared core.** SQLite (`chat.db`) serves local
chat + memory cells; Supabase serves Gio (it needs pgvector embeddings).
They are deliberately not unified — instead both repositories satisfy the
`ConversationStore` Protocol and share `require_conversation` /
`derive_auto_title` from `core/`.

**Lazy settings.** All configuration flows through `get_settings()` at call
time. This is what makes `monkeypatch.setattr(get_settings(), "DB_PATH", ...)`
work in tests (the old import-time constants silently sent test writes to the
production database). `config.py` remains only as a PEP 562 compatibility
shim and is scheduled for removal.

**GioService is a facade.** The public surface (and its constructor
`(repository=None, providers=None)`) is stable; logic lives in collaborators
that all share one repository instance (its Supabase table-detection cache
must stay singular per app). The attributes `openai_client`, `_embed`,
`_summarize_messages`, and `_dream_from_sources` are deliberate seams —
collaborators reach them through late-bound callbacks, so swapping them on an
instance (as the tests do) affects everything consistently.

**Auth model.** `require_api_key` checks `X-API-Key` against
`Settings.API_KEY` (constant-time). If `API_KEY` is empty the check is
*bypassed* — dev-only behavior; production must always set a strong key.
Public reads (health, temperature, llm-status, providers, razzy profile,
integrations, HTML pages) skip the key on purpose. Flask-Limiter caps all
routes at 120 req/min (in-memory).

## Gio memory pipeline

1. Each user/assistant message is embedded (OpenAI `text-embedding-3-small`)
   and stored with the message row.
2. **Recall** (`gio/recall.py`): on each turn, prior messages outside the
   recent window are scored by cosine similarity against the new user
   message; top snippets above `GIO_RECALL_MIN_SCORE` are injected as a
   system block.
3. **Rolling summary** (`gio/summaries.py`): once enough messages age out of
   the recent window (or a correction-like user message appears), they are
   summarized into one per-conversation summary row (dedicated table, with a
   legacy fallback to hidden `role="summary"` message rows).
4. **Dream Mode** (`gio/dreams.py`): on demand, a reflection entry is
   generated from selected sources (recent + correction-like + high-priority
   older messages) and stored in `gio_dream_entries` with its own embedding.
5. **Dream recall / reflection** (`gio/chat.py::_build_dream_reflection_block`):
   while assembling the prompt, with probability `GIO_DREAM_RECALL_PROBABILITY`
   the current user-message embedding is matched against every stored dream
   (across all conversations) and the `GIO_DREAM_RECALL_TOP_K` most similar
   above `GIO_DREAM_RECALL_MIN_SCORE` are injected as the assistant's own
   remembered impressions — associative rather than random. Retrieval is
   best-effort: any storage failure silently skips the block so chat never
   breaks. The similarity primitives live in `gio/embeddings.py`:
   `cosine_similarity` (stateless, single-pass) and `top_k_similar`
   (stateless streaming top-k with an O(k) bounded heap).

## How to add a feature

1. Business logic: a new module/package under `unified_server/` with an
   injectable constructor (dependencies default to real implementations).
2. HTTP: a blueprint factory in `unified_server/web/<feature>.py`; register
   it in `web/__init__.py::register_blueprints`. Public reads follow the
   temperature-endpoint posture; anything with side effects gets
   `@require_api_key`.
3. Config: add fields to `Settings` (+ `.env.example`).
4. Tests: build the blueprint with fakes (see `tests/test_integrations.py`)
   or inject a fake service through `create_app` (see `tests/conftest.py`).
5. Frontend: keep it button-shaped; add a card to the relevant page's file
   group under `static/`.

## Testing strategy

- `tests/conftest.py` wires `create_app` with fake providers/twitter and a
  temp SQLite DB (`temp_db` patches `get_settings().DB_PATH`).
- Endpoint contract tests drive HTTP against injected fakes
  (`test_gio_api.py`, `test_twitter.py`, `test_integrations.py`).
- Behavior unit tests poke the Gio facade's seams directly
  (`test_gio_context.py`).
- `test_api.sh` is a curl smoke test against a running server.

## Deployment

- `razzy-flask.service`: `WorkingDirectory=` project root,
  `ExecStart=.venv/bin/python app.py` (via `bash -lc` because the path
  contains a space — always quote it in shell commands). Drop-in
  `runtime.conf` pins `APP_RUNNER=waitress`, `DEBUG=false`.
- After deploying code: `sudo systemctl restart razzy-flask.service`, then
  check `journalctl -u razzy-flask.service -n 50` and `curl localhost:8000/health`.
- Cloudflare Tunnel (`/etc/cloudflared/config.yml`) maps
  `razzy.justtools.net → localhost:8000`; everything else 404s.
