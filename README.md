# Unified Server

A cohesive Python server that merges the strongest parts of `server-2`, `server-3`, and `server-main` into one maintainable project.

## What it includes

- Modular architecture inspired by `server-main`
- Flask HTTP API
- SQLite conversation persistence
- Provider abstraction for OpenAI, Ollama, and Anthropic-ready wiring
- Razzy persona layer with dedicated identity config
- Razzy memory endpoints for remember/recall
- Razzy chat UI at `/razzy`
- Optional memory recall/extraction layer
- Security basics:
  - API key protection for protected routes
  - CORS
  - security headers
  - lightweight rate limiting
- Health endpoint

## Project structure

```text
unified_server/
  api/
  core/
  providers/
  storage/
  app.py
```

## Setup

```bash
cd "/home/giosterr44/Documents/ruizTechServices/project/python/server/fucking Around"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and set what you need.

## Run

```bash
cd "/home/giosterr44/Documents/ruizTechServices/project/python/server/fucking Around"
source .venv/bin/activate
python app.py
```

Server defaults to:
- `http://127.0.0.1:8000`
- `http://0.0.0.0:8000`

## Useful endpoints

Public:
- `GET /health`
- `GET /api/providers`

Protected (needs `X-API-Key` when `API_KEY` is set):
- `POST /api/conversations`
- `GET /api/conversations`
- `GET /api/conversations/<conversation_id>/messages`
- `POST /api/chat`

## Example health check

```bash
curl http://127.0.0.1:8000/health
```

## Example create conversation

```bash
curl -X POST http://127.0.0.1:8000/api/conversations \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"title":"Test Chat"}'
```

## Tests

Install dependencies, then run:

```bash
cd "/home/giosterr44/Documents/ruizTechServices/project/python/server/fucking Around/fuck-around-1"
source .venv/bin/activate
pytest
```

The test suite uses fake providers, so it does not depend on live OpenAI, Ollama, or Anthropic calls.

## Notes

- OpenAI support requires `OPENAI_API_KEY`
- Ollama support requires local Ollama running on `OLLAMA_BASE_URL`
- Anthropic provider is scaffolded for later completion
