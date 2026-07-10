# TODO — Razzy Chat

Refreshed 2026-07-09, after the extreme-modularity refactor. Guiding
principle for new features: this site supplements WhatsApp chat with Razzy
using **buttons and simple interfaces**, not chat UIs (see README).

## Done (as of 2026-07-09)

- [x] Production runner (Waitress) + explicit systemd runtime env — live since 2026-07-02.
- [x] `/gio`: Supabase conversations, dynamic model listing, NDJSON streaming,
      embeddings, semantic recall, rolling summaries (dedicated table + legacy fallback).
- [x] Dream Mode storage, manual generation endpoint, and browser UI.
- [x] **Refactor 2026-07-09:** lazy `Settings` core; monolithic `app_factory`
      split into `web/` blueprints + `system/` domain; `chat/`, `razzy/`,
      `gio/`, `providers/`, `twitter/`, `integrations/` packages; GioService
      god-object decomposed into facade + collaborators; memory service
      unified; duplication (titling, validation, chat skeleton) removed;
      dead Twitter bearer code deleted. Route map verified unchanged.
- [x] Fixed latent test bug: the suite used to write into the production
      `data/chat.db` (import-time `DB_PATH` binding). Tests are now isolated.
- [x] World Snapshot widgets: Open-Meteo weather, ipify public IP, CoinGecko
      crypto, Frankfurter currency converter, NASA APOD — backend proxy
      endpoints with TTL caches + dashboard cards. 64 tests green.
- [x] README rewritten to match reality; docs/ARCHITECTURE.md added.

## Priority 1 — security hygiene

- [ ] **Rotate `API_KEY`.** The live key is the `change-me` default and the
      public pages ship it as the localStorage fallback — anyone who guesses
      it can use the authed endpoints (incl. Ollama systemctl control and
      Twitter posting). Gio explicitly chose to keep `change-me` for now
      (2026-07-09); revisit when rotating the other secrets. To rotate: set a
      strong value in `.env`, restart the service, update `razzy_api_key` in
      localStorage on your devices.
- [ ] Rotate OpenAI / Anthropic / Supabase service-role / Twitter secrets
      (carried over from the old list; still pending).
- [ ] Consider refusing to start (or loudly warning) in production when
      `API_KEY` is empty — the empty-key auth bypass is dev-only behavior.
- [x] Audit `data/chat.db` and delete the junk conversations left by the
      old test-isolation bug — done 2026-07-09: purged 10 junk conversations
      + 8 orphaned memory cells, vacuumed; only real data remains.

## Priority 2 — Dream Mode substance (carried over, still in progress)

- [x] Dream storage fixed 2026-07-09: `gio_dream_entries` was missing from the
      razzy-db Supabase project (schema applied via SQL editor from
      supabase_gio_schema.sql). /gio/dreams now loads; entries can be generated
      per conversation via POST /api/gio/conversations/<id>/dream.

- [ ] Define the dream input set / output contract more rigorously.
- [ ] Guardrails against self-referential dreams (dreams feeding on dreams).
- [ ] Clustering / retrieval pass over dream embeddings.
- [ ] Trigger conditions (idle timer / cron / heartbeat) + token/cost limits.
- [ ] Edit / revision-history semantics for dream entries.

## Priority 3 — deliberate deferrals

- [ ] Remove the `unified_server/config.py` compat shim once nothing imports
      it (grep for `unified_server.config`; `scripts/` was already migrated).
- [ ] Optional: per-feature folders under `static/` (deliberately skipped —
      churn/benefit ratio failed; flat layout with name prefixes is fine).
- [ ] Flask-Limiter uses `memory://` storage — fine for one Waitress process;
      revisit if the app ever runs multi-process.
- [ ] Upgrade Ollama + install newer local models (blocked: old Ollama build).
- [ ] Twitter/X live posting (blocked by X-side API enrollment, not code).

## Widget ideas that fit the site's purpose (buttons, not chat)

- [ ] Public-holiday card (Nager.Date, free/no key).
- [ ] Sunrise/sunset times folded into the weather card (sunrise-sunset.org).
- [ ] "Word of the day" card (Free Dictionary API).
- [ ] One-click Razzy actions that send canned prompts to WhatsApp flows.
