# Razzy Chat

A personal AI server for Gio, running on a Raspberry Pi 5 and served publicly
at `razzy.justtools.net` through a Cloudflare Tunnel.

**What this site is for:** Gio talks to Razzy through WhatsApp. This web app
*supplements* that conversation with buttons and simple interfaces — a system
dashboard, Ollama controls, the Gio assistant, and info widgets. It is not a
replacement chat UI; the Razzy web-chat endpoints were deliberately removed
and return `410 Gone`.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the module system,
layering, and how to add features.

## Pages

| Path | What it is |
|---|---|
| `/` | **Razzy Command Center** — system overview (Pi temperature, LLM status, service health), Ollama start/stop buttons, recent Gio chats, and the **World Snapshot** widgets (weather, public IP, crypto, currency converter, NASA picture of the day). |
| `/console` | Developer testing console for the local multi-provider chat API. |
| `/razzy` | Razzy status view: Pi temperature + LLM connection cards with Ollama controls. (Chatbot removed from this page.) |
| `/gio` | Gio — Supabase-backed ChatGPT-style assistant with streaming, semantic recall, and rolling summaries. |
| `/gio/dreams` | Dream Mode browser — reflection entries generated from Gio conversations. |

## API routes

Auth: routes marked 🔑 require the `X-API-Key` header (matched against
`API_KEY` in `.env`). Everything is rate-limited to 120 requests/minute.

### Health & system
| Route | Notes |
|---|---|
| `GET /health` | Liveness check. |
| `GET /api/system/temperature` | Pi CPU temperature snapshot (15 s cache). |
| `GET /api/system/llm-status` | Ollama + OpenAI reachability probes. |
| `POST /api/system/ollama/control` 🔑 | `{"action": "start"\|"stop"\|"restart"\|"status"}` → `sudo systemctl` on `ollama.service`. |

### Local chat (SQLite)
| Route | Notes |
|---|---|
| `GET /api/providers` | Provider/model catalog (OpenAI, Ollama, Anthropic). |
| `POST /api/conversations` 🔑 | Create conversation. |
| `GET /api/conversations` 🔑 | List conversations. |
| `GET /api/conversations/<id>/messages` 🔑 | Messages for a conversation. |
| `PATCH /api/conversations/<id>` 🔑 | Rename. |
| `DELETE /api/conversations/<id>` 🔑 | Delete. |
| `POST /api/chat` 🔑 | One chat turn; `{conversation_id?, message, provider?, model?}`. |

### Gio (Supabase)
| Route | Notes |
|---|---|
| `GET /api/gio/models` 🔑 | Curated OpenAI model list. |
| `POST /api/gio/session` 🔑 | Create conversation. |
| `GET /api/gio/conversations` 🔑 | List conversations. |
| `GET /api/gio/conversations/<id>/messages` 🔑 | Messages (hidden summary rows filtered out). |
| `PATCH /api/gio/conversations/<id>` 🔑 / `DELETE ...` 🔑 | Rename / delete. |
| `POST /api/gio/chat` 🔑 | One turn (embeddings + recall + rolling summary). |
| `POST /api/gio/chat/stream` 🔑 | NDJSON stream: `meta` → `delta`* → `done` (or `error`). |
| `GET /api/gio/dreams` 🔑, `GET /api/gio/dreams/<id>` 🔑 | List / fetch dream entries. |
| `POST /api/gio/conversations/<id>/dream` 🔑 | Generate a dream entry. |

### Razzy
| Route | Notes |
|---|---|
| `GET /api/razzy/profile` | Identity card (RAZZY 🦉). |
| `POST /api/razzy/session` · `POST /api/razzy/chat` · `POST /api/razzy/remember` · `GET /api/razzy/memory/<id>` 🔑 | All return **410 Gone** — Razzy chat lives in WhatsApp. |

### Twitter/X
`GET /api/twitter/status` · `GET /api/twitter/me` · `GET /api/twitter/posts/<id>` ·
`GET /api/twitter/timeline/user/<id>` · `POST /api/twitter/post` ·
`POST /api/twitter/posts/<id>/reply` · `POST /api/twitter/posts/<id>/quote` ·
`DELETE /api/twitter/posts/<id>` — all 🔑, backed by OAuth 1.0a credentials.
Live posting is still gated by X-side API enrollment, not local code.

### Integrations (free public APIs; endpoints are public reads)
| Route | Upstream |
|---|---|
| `GET /api/integrations/weather` | [Open-Meteo](https://open-meteo.com) — current + 3-day forecast for the configured location. |
| `GET /api/integrations/network/public-ip` | [ipify](https://www.ipify.org) — the Pi's public WAN IP. |
| `GET /api/integrations/crypto/prices` | [CoinGecko](https://www.coingecko.com) — USD spot + 24h change for `CRYPTO_COINS`. |
| `GET /api/integrations/currency/convert?amount&from&to` | [Frankfurter](https://frankfurter.dev) (ECB reference rates). |
| `GET /api/integrations/apod` | [NASA APOD](https://api.nasa.gov) — works out of the box with `DEMO_KEY`. |

Responses are cached server-side (2 min – 6 h per source) to stay polite to
the free APIs. Upstream failures return `503` with a friendly JSON error (503 instead of 502 because Cloudflare replaces origin 502 bodies with its own error page, which would hide the message).

## Setup

```bash
cd "/home/giosterr44/Documents/ruizTechServices/project/python/server/fucking Around/fuck-around-1"
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env   # then fill in real values — especially a strong API_KEY
```

> The project path contains a space — always quote it in shell commands.

Run locally:

```bash
.venv/bin/python app.py                               # waitress (default)
APP_RUNNER=flask DEBUG=true .venv/bin/python app.py   # flask dev server
```

Tests:

```bash
.venv/bin/python -m pytest -q    # 64 tests, no network, isolated temp DB
bash test_api.sh                 # curl smoke test against a running server
```

## Configuration

All configuration comes from `.env` (see `.env.example` for every variable)
and is loaded once into a `Settings` object (`unified_server/settings.py`).
Highlights:

- `API_KEY` — the `X-API-Key` value for protected routes. **If left empty,
  auth is bypassed entirely** (dev-only behavior). Set a strong unique value
  in production and never leave it at `change-me`.
- `DEFAULT_PROVIDER` / `DEFAULT_MODEL` — local chat defaults.
- `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL`.
- `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `GIO_*` — Gio storage and
  memory tuning (see `supabase_gio_schema.sql` for the schema).
- `GIO_DREAM_RECALL_*` — occasional associative reflection during Gio chat:
  with probability `GIO_DREAM_RECALL_PROBABILITY` (default 0.25) the
  `GIO_DREAM_RECALL_TOP_K` (default 5) dreams most similar to the current
  message are recalled into context as Gio's own past reflections.
- `TWITTER_*` — OAuth 1.0a credentials for X.
- `NASA_API_KEY`, `WEATHER_LATITUDE`/`WEATHER_LONGITUDE`/`WEATHER_LOCATION_NAME`,
  `CRYPTO_COINS`, `CURRENCY_DEFAULT_BASE` — World Snapshot widgets.

## Deployment (production)

The live site runs under systemd:

```bash
sudo systemctl status razzy-flask.service     # waitress on port 8000
sudo systemctl restart razzy-flask.service    # deploy new code
journalctl -u razzy-flask.service -n 50       # check for startup errors
```

`/etc/cloudflared/config.yml` tunnels `razzy.justtools.net` →
`http://localhost:8000`.

## Project layout

```
app.py                  entrypoint (systemd runs this; don't move it)
unified_server/
├── app_factory.py      create_app(): extensions + service wiring + blueprints
├── settings.py         Settings dataclass, get_settings()
├── security.py         X-API-Key check + security headers
├── core/               shared prompt, conversation helpers, chat-turn engine
├── web/                one blueprint per feature (routing only)
├── chat/               local SQLite chat stack + unified memory service
├── razzy/              Razzy identity + service
├── gio/                Gio assistant (facade + chat/recall/summaries/dreams/catalog)
├── providers/          OpenAI / Ollama / Anthropic adapters + registry
├── system/             Pi temperature, LLM probes, Ollama systemctl control
├── integrations/       free public-API widget clients
├── twitter/            X/Twitter client + service
└── static/             vanilla HTML/CSS/JS pages
tests/                  64 pytest tests (fakes injected via create_app / blueprints)
docs/ARCHITECTURE.md    module system, layering, how to add features
supabase_gio_schema.sql Gio tables (pgvector) + legacy summary backfill
```
