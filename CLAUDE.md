# CLAUDE.md — Precedent engineering spec (Python)

**Precedent — institutional memory, enforced.** A Slack-native agent that (1) extracts team
decisions into a human-ratified, cited canon, (2) defends that canon in real time against drift
with private nudges, and (3) exposes it over MCP so other AI agents consult it before acting.

> This is the machine-facing spec. The human operation lives in `PRECEDENT_TEAM_PLAYBOOK.md`
> (frozen). The on-disk `PRECEDENT_BUILD_PROMPT.md` is the **superseded TypeScript** version —
> ignore it; this project is Python.

## Stack (versions locked from a real install — do not bump blindly)
- Python 3.11 (spec target 3.12; 3.11 in use locally — Bolt supports both)
- slack-bolt 1.29 / slack-sdk 3.43 · SQLAlchemy 2.0 · pgvector 0.4 (server pgvector 0.8) · psycopg 3.3
- anthropic 0.115 (`MODEL_GATE=claude-haiku-4-5`, `MODEL_REASON=claude-sonnet-4-6`)
- voyageai 0.4 (`voyage-3`, 1024-dim) — swappable via `services/embeddings.py`
- MCP (Phase 6): `mcp<2.0` over Streamable HTTP — v2 is pre-release past our deadline

## Verified API surface (checked against installed source — NOT assumed)
- `from slack_bolt import App, Assistant`; register with **`app.assistant(assistant)`** (NOT `app.use`).
  Assistant handlers: `@assistant.thread_started`, `@assistant.user_message`, `@assistant.thread_context_changed`.
- Assistant utilities: `set_status`, `set_suggested_prompts` (max 4), `set_title`, `get_thread_context`, `say_stream`.
- **RTS has no typed SDK method.** Call `client.api_call("assistant.search.context", params=…)` /
  `"assistant.search.info"`. Requires a fresh `action_token` from a message/app_mention event in the
  same request cycle. Hot path (Sentinel) **never** calls RTS — local pgvector only.
- `App(...)` needs a token string to construct even with `token_verification_enabled=False`.
  There is **no** `ignoring_self_events` constructor kwarg — filter bot/self messages manually (G4).

## Hard constraints (non-negotiable)
1. No invented APIs — verify against installed package source before writing a call.
2. Phase-gated: no next phase until this phase's exit checklist passed against a **real** system.
3. Sentinel hot path uses local pgvector only — zero RTS calls.
4. Every LLM system prompt lives in `/prompts/*.md`, loaded at runtime (never inlined).
5. Every interactive action idempotent — Slack retries; double-clicks must not duplicate canon/drift.
6. Human-in-the-loop: nothing reaches `status='ratified'` without a human Approve. `propose_decision`
   (MCP) writes `proposed` only.
7. Zero scope creep — if it's not in the Playbook IN list, the answer is "roadmap."

## Layout
```
src/precedent/
  config.py telemetry.py
  db/        schema.py client.py migrate.py ddl.sql   # ddl.sql = migration source of truth
  slack/     app.py listeners/ blocks/
  agents/    gatekeeper|extractor|sentinel|archivist   (Phases 1–4)
  services/  anthropic|embeddings|canon|rts|canvas     (Phases 1–5)
  mcp/       server|tools|auth                         (Phase 6)
prompts/ tests/ docs/ scripts/seed/
```

## Local dev
```bash
# real Postgres+pgvector (host 5432/5433 may be taken by a native PG — we use 55432)
docker run -d --name precedent-pg -e POSTGRES_USER=precedent -e POSTGRES_PASSWORD=precedent \
  -e POSTGRES_DB=precedent -p 55432:5432 pgvector/pgvector:pg16
cp .env.example .env            # fill secrets; DATABASE_URL=postgresql://precedent:precedent@localhost:55432/precedent
python -m precedent.db.migrate  # apply schema
python -m precedent.slack.app   # boot Socket Mode (needs SLACK_BOT_TOKEN + SLACK_APP_TOKEN)
```

## Provider note
Dev runs on **Groq** (LLM: `llama-3.3-70b-versatile` reason / `llama-3.1-8b-instant` gate) + **Voyage**
`voyage-3.5` (1024-dim) embeddings — both free-tier, swap via `LLM_PROVIDER` / `EMBED_MODEL`.
⚠️ Voyage free tier is 3 RPM without a payment method — batch embeds; add a (free) card before judging.

## Phases — all built & verified against real services (Groq/Voyage/Postgres/live MCP client)
- P0 scaffold · P1 manual capture (**live**: reaction→card→ratify→embedded, verified with real thread)
- P2 Gatekeeper (real Groq 4/4, <1.5s) · P3 Sentinel — **eval 30/30**, drift card + supersede
- P4 Archivist (streamed cited answer, real Groq) + RTS client (verified surface; live action_token pending)
- P5 Registrar — Canvas Register (live create+edit), App Home dashboard (live counts+pending+drift), digest
- P6 MCP — 4 tools verified via a **real MCP client** (official SDK) incl. full propose→ratify round-trip
- P7 seed — 12 rulings live in DB (correct PRE-006→PRE-014 lineage); all 6 landmines logically correct
  (each fires correctly in isolation; back-to-back reliability gated on Voyage rate limit, see below)
- P8 hardening — retry-with-backoff on embeddings; pytest 5/5; test-data cleanup from demo canon
- **Remaining:** confirm Voyage payment method lifts the RPM cap (re-test 6/6 burst) · live Slack UI
  walkthrough of autonomous capture + drift card firing from a human typing · Claude Desktop MCP config
  (vs. the raw SDK client already used to verify) · eventual deploy (Railway/Fly, out of local-dev scope).

## Run
`python -m precedent.db.migrate` · `python -m precedent.slack.app` (Socket Mode) · `python -m precedent.mcp.server` (:8933)
Seed: `python scripts/seed/insert_canon.py` · Eval: `python tests/eval_runner.py` · `pytest tests/test_smoke.py`
