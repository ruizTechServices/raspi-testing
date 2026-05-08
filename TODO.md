# TODO - Razzy Chat

A realistic next-steps list based on the app's current state as of 2026-04-29.

## Done already

- [x] Core Flask app is running and reachable locally and through Cloudflare Tunnel.
- [x] Test suite is green: `30 passed`.
- [x] `/` dev console works.
- [x] `/razzy` personal chat UI works.
- [x] `/gio` has Supabase-backed conversations/messages.
- [x] `/gio` has dynamic OpenAI model listing.
- [x] `/gio` has real OpenAI streaming over NDJSON.
- [x] `/gio` shows message model/provider footer in the UI.
- [x] `/gio` stores embeddings for user and assistant messages.
- [x] `/gio` uses semantic recall from embeddings.
- [x] `/gio` uses rolling summaries with dedicated summary storage support and backward compatibility.
- [x] Twitter/X endpoints exist and are tested structurally.

## Priority 1, stabilize production behavior

### 1. Replace Flask dev server with a production runner
Status: done

Reality check from live verification on 2026-04-29:
- the running service is serving through **Waitress** now
- `/health`, `/`, and `/gio` are live behind Waitress
- systemd runtime is now explicitly pinned with:
  - `APP_RUNNER=waitress`
  - `DEBUG=false`
  - `USE_RELOADER=false`

Why this matters:
- the old dev-server mismatch problem was real
- production behavior is now explicit instead of inferred from defaults

Definition of done:
- [x] use Gunicorn, Waitress, or another sane production runner
- [x] disable debug and reloader in service mode
- [x] update systemd service accordingly with explicit production env / runner behavior
- [x] confirm `/health`, `/gio`, and `/razzy` still work after the swap

### 2. Make environment modes explicit
Status: done

Why this matters:
- right now dev/prod behavior is too implicit
- deployment should not depend on accidental defaults

Definition of done:
- [x] `debug` controlled by config, not hardcoded in `app.py`
- [x] clear dev vs prod settings in `.env.example`
- [x] document exact startup commands for both modes

## Priority 2, tighten Gio memory architecture

### 3. Improve rolling summary policy
Status: done

Already done:
- [x] latest summary is injected into prompt context
- [x] summary refresh now happens after completed assistant turns instead of mid-turn
- [x] duplicate summary churn is suppressed
- [x] tests cover summary visibility and longer summary behavior

Definition of done:
- [x] summaries update predictably
- [x] duplicate or low-value summaries are reduced
- [x] long conversations stay coherent without ballooning prompt size

### 4. Consider dedicated summary storage
Status: done

Reality check from live verification on 2026-04-29:
- `gio_conversation_summaries` now exists in live Supabase
- direct live repository probe now writes summaries to the dedicated table, not hidden `summary` messages
- service-level summary generation probe also writes to the dedicated table
- backward compatibility still works for older hidden `summary` message rows when a conversation has no dedicated summary row yet
- no `/gio` regression was introduced while fixing the summary path and stale-conversation bug

Why this matters:
- hidden summary messages were a useful bridge, but the dedicated table is the cleaner long-term shape
- live production behavior now matches the intended summary-storage path in code

Definition of done:
- [x] choose one:
  - [x] `gio_conversation_summaries` table, or
  - [ ] summary fields on `gio_conversations`
- [x] add migration SQL
- [x] update repository/service layer
- [x] preserve backward compatibility for existing hidden summary rows if needed
- [x] apply the live Supabase migration so `gio_conversation_summaries` actually exists in production

### 5. Add retrieval quality controls
Status: done

Already done:
- [x] recall uses cosine similarity over stored embeddings from the same conversation
- [x] older recalled context is separated from the recent window
- [x] duplicate recalled snippets are filtered out
- [x] recalled user context and assistant context are separated into clearer prompt sections
- [x] tests cover semantic recall behavior

Definition of done:
- [x] recall pulls genuinely useful older context
- [x] prompt quality improves measurably on longer conversations

### 5b. Prove the embeddings pipeline end-to-end in live runtime
Status: done

Reality check from live verification on 2026-04-29:
- `GioService._embed()` is generating embeddings live through OpenAI
- user-message embeddings are being stored live in `gio_messages`
- assistant-message embeddings are being stored live in `gio_messages`
- summary embeddings are being stored live in `gio_conversation_summaries`
- semantic recall successfully pulled older relevant context during a controlled live smoke test
- prompt context builder was directly inspected live and confirmed to inject:
  - system prompt
  - latest rolling summary
  - semantic recall block
  - recent window
- `scripts/verify_gio_summary_storage.py` now gives us one reusable live verification probe for summary-storage behavior

Why this matters:
- we now have proof that the retrieval stack is not just present in code, it is actually functioning in production
- the next work is no longer “does it work at all?”, it is “how do we make it more robust and more productively useful?”

Definition of done:
- [x] confirm user-message embeddings are being generated and stored live
- [x] confirm assistant-message embeddings are being generated and stored live
- [x] confirm summary embeddings are generated and stored correctly in whichever summary path is active
- [x] run a live semantic-recall smoke test that proves older relevant context is actually retrieved for a targeted follow-up question
- [x] verify the prompt context builder is injecting summary + recalled context + recent window in the intended order during real requests
- [x] add one explicit test or diagnostic helper for embedding/search verification so future regressions are easier to catch

### 5c. Add embedding-driven Dream Mode for standby reflection
Status: in progress

Already done:
- [x] Dream Mode now has its own storage path via `gio_dream_entries`
- [x] manual dream generation endpoint exists for a conversation
- [x] dream entries can be listed and viewed in a first-pass `/gio/dreams` browser
- [x] dream entries store source message ids plus their own embedding

Decision:
- Dream Mode should get **its own table/storage path**, not reuse `gio_conversation_summaries`
- `gio_conversation_summaries` is operational memory for live chat compression, not a home for reflective artifacts

Concept:
- when Razzy is idle, use stored embeddings plus summaries/history to reflect on prior conversations instead of doing nothing
- dream output should not be fake mysticism, it should be structured reflection over memory clusters, unresolved threads, repeated themes, and possible durable insights
- dreams should be able to compound on prior dream outputs when useful, but without turning into recursive slop

Why this matters:
- it gives embeddings a second high-value use beyond retrieval during live chat
- it could improve long-term memory quality, self-consistency, and proactive insight generation
- it fits the standby/heartbeat model better than constant random chatter

Definition of done:
- [ ] define what counts as a “dream input set” (recent chats, high-similarity clusters, summaries, unresolved threads, repeated themes)
- [ ] define what counts as a “dream output” (reflection note, distilled insight, candidate long-term memory, unresolved question, emotional/theme analysis)
- [x] decide where dream outputs are stored
- [ ] add guardrails so dream outputs do not overwrite source memory or endlessly self-reference
- [ ] add a clustering or retrieval pass that groups semantically related memories/messages for contemplation
- [ ] support compounding on prior dream outputs only when signal is high
- [ ] choose trigger conditions for standby dreaming (heartbeat idle window, cron, low-activity periods, manual invoke)
- [ ] document token/cost limits and rate limits so Dream Mode does not burn money while idle
- [ ] verify whether dream outputs should stay internal, be user-visible on request, or selectively promoted into long-term memory
- [x] add a frontend route/page to browse dream outputs
- [x] add a nav link so Gio can open the dream view directly from the UI
- [ ] define whether dream entries are read-only by default or editable with automatic re-embedding after text changes
- [ ] if editing is allowed, regenerate embeddings automatically on save rather than exposing raw embedding edits
- [ ] define whether manual edits create a revision history so dream output provenance is not lost

## Priority 3, finish `/gio` UX properly

### 6. Add rename and delete chat actions
Status: done

Why this matters:
- conversation list exists, but lifecycle controls are incomplete
- current UX still feels prototype-ish

Definition of done:
- [x] rename conversation
- [x] delete conversation
- [x] update UI state cleanly without reload weirdness
- [x] test the API and frontend paths

notes(Gio added)
- [x] delete button does not work, fixed after live server restart and retest
- [x] rename button does not work, fixed after live server restart and retest

### 7. Add better streaming UX polish
Status: done

Already done:
- [x] real streaming works for OpenAI
- [x] browser caching issue was patched with asset versioning
- [x] better loading/finalizing states exist in the UI
- [x] cancel/abort streaming support exists
- [x] interrupted streams fail clearly in the UI
- [x] streaming and completed message states are visually distinct
- [x] composer/input bar is anchored like a real chat surface
- [x] transcript is the main scroll region instead of the whole page fighting itself
- [x] mobile nav now collapses behind a hamburger menu
- [x] mobile chat history now works as a slide-out sidebar/drawer

Definition of done:
- [x] streaming feels reliable on phone and desktop
- [x] interrupted streams fail clearly and recover cleanly
- [x] `/gio` is meaningfully more usable on mobile than the old prototype layout

### 8. Support optional reasoning/thinking display only when real data exists
Status: done

Why this matters:
- UI has a shape for thinking content, but current `/gio` flow does not populate it meaningfully
- fake reasoning UI is worse than none

Definition of done:
- [x] only show reasoning accordion when provider returns real separate reasoning data
- [x] do not guess or synthesize fake hidden-thought content

## Priority 4, improve tests and docs

### 9. Expand `/gio` test coverage beyond context builder logic
Status: done

Already covered:
- [x] context builder logic
- [x] semantic recall behavior
- [x] rolling summary visibility behavior
- [x] first-pass rolling summary creation behavior
- [x] endpoint tests for `/api/gio/session`
- [x] `/api/gio/conversations`
- [x] `/api/gio/conversations/<id>/messages`
- [x] `/api/gio/chat`
- [x] `/api/gio/chat/stream`
- [x] rename/delete Gio conversation endpoints

Definition of done:
- [x] Gio routes have dedicated API tests
- [x] streaming contract is tested well enough to catch regressions

### 10. Rewrite README to match reality
Status: done

Why this matters:
- current README is stale in places
- some structure notes do not match the actual tree
- `/gio` capabilities and deployment details are under-documented

Definition of done:
- [x] document `/`, `/razzy`, `/gio`
- [x] document Supabase setup clearly
- [x] document streaming behavior and current provider limitations
- [x] document systemd + Cloudflare Tunnel deployment shape

### 10b. Document the embedding/search architecture more explicitly
Status: todo

Why this matters:
- embedding behavior is important enough that it should not stay half-hidden in code
- future debugging will be easier if the retrieval path, summary path, and live verification method are documented plainly

Definition of done:
- [ ] document where embeddings are created
- [ ] document where embeddings are stored
- [ ] document how semantic recall selection works today
- [ ] document current limitations and what still needs live verification

## Priority 5, repo and deployment hygiene

### 11. Clean repo-local clutter before sharing broadly
Status: done

Already done:
- [x] `.gitignore` was tightened to ignore stronger local junk and archives
- [x] `cloudflared.deb` was moved out of the app repo
- [x] tracked files were scanned for obvious secret leakage
- [x] additional local artifact ignoring was strengthened

Definition of done:
- [x] repo contains source, docs, tests, and intentional setup artifacts only

### 12. Secret rotation after GitHub push
Status: blocked outside app code

Why this matters:
- live secrets were previously pasted in chat and written into `.env`
- even if `.env` is ignored, assume rotation is still wise

Definition of done:
- [ ] rotate OpenAI key if needed
- [ ] rotate Anthropic key if needed
- [ ] rotate Supabase service role key if needed
- [ ] rotate Twitter/X credentials if needed

## Priority 6, deferred but important

### 13. Upgrade Ollama and install the intended Gemma 4 model
Status: blocked outside app code

Current blocker:
- installed Ollama version is too old for the intended `gemma4` pull

Definition of done:
- [ ] upgrade Ollama on the Pi
- [ ] install the correct Gemma 4 target
- [ ] verify it appears in `/api/providers` and works in chat

### 14. Revisit Twitter/X only after access tier is fixed
Status: blocked by platform access

Already done:
- [x] code scaffold exists
- [x] structural tests exist for the Twitter/X endpoint layer

Why this still matters:
- live functionality is blocked by X-side enrollment/access, not just local implementation

Definition of done:
- [ ] confirm app/project enrollment level
- [ ] confirm correct credentials and app context
- [ ] re-test live read/post/delete paths

## Remaining blockers

The codebase-side list is close, but not fully complete.

What still remains beyond ordinary feature work:

1. prove the embeddings pipeline end-to-end in live runtime
2. design and implement embedding-driven Dream Mode for standby reflection
3. document the embedding/search architecture more explicitly
4. rotate live secrets if needed
5. upgrade Ollama on the Pi and install the intended Gemma 4 model
6. fix X/Twitter API access tier/enrollment so the live endpoints can actually work
