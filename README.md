# ⚖️ Precedent — institutional memory, enforced

A Slack-native agent that turns team conversations into a **cited, human-ratified canon of
decisions**, defends that canon in real time against drift with private nudges, and exposes it over
**MCP** so other AI agents consult it before acting.

Three pillars: **Remember** (manual + autonomous capture → human-ratified canon) · **Defend**
(real-time drift detection, local-only) · **Govern** (MCP server with a propose → human-ratify loop).

## Setup (≈5 minutes after prerequisites)

Prerequisites: Python 3.11+, Docker (for local Postgres+pgvector), a Slack app (Socket Mode), a
[Groq](https://console.groq.com) API key (free), and a [Voyage](https://dashboard.voyageai.com) API
key (free tier; add a payment method to lift the 3 req/min cap — the free token allotment still
applies, judging demos need the higher throughput).

```bash
python -m venv .venv && . .venv/Scripts/activate      # Windows Git Bash
pip install -e .

# 1) Real Postgres + pgvector (host may already run PG on 5432/5433 — we publish 55432)
docker run -d --name precedent-pg \
  -e POSTGRES_USER=precedent -e POSTGRES_PASSWORD=precedent -e POSTGRES_DB=precedent \
  -p 55432:5432 pgvector/pgvector:pg16

# 2) Configure
cp .env.example .env
#   fill: SLACK_BOT_TOKEN / SLACK_APP_TOKEN / SLACK_SIGNING_SECRET (see docs/slack-app-manifest.yaml)
#         GROQ_API_KEY, VOYAGE_API_KEY
#   DATABASE_URL=postgresql://precedent:precedent@localhost:55432/precedent

# 3) Apply schema
python -m precedent.db.migrate

# 4) Seed the demo world (12 rulings, incl. PRE-006 -> PRE-014 lineage)
python scripts/seed/insert_canon.py

# 5) Boot the Slack app (Socket Mode)
python -m precedent.slack.app

# 6) (optional) MCP server, for external agents (Claude Desktop etc.)
python -m precedent.mcp.server
```

Then in Slack: `/precedent help`, or `/precedent enroll` in a channel to turn on autonomous capture
and drift defense there.

## What's implemented

| Phase | Feature | Status |
|---|---|---|
| 0 | Scaffold: schema, Bolt app boot, App Home stub | done |
| 1 | Manual capture: `:scales:` reaction → Extractor → Ratify card → ratified + embedded | done |
| 2 | Gatekeeper: autonomous decision-moment detection on enrolled channels | done |
| 3 | Sentinel: real-time drift defense (local pgvector only) + supersede flow | done — 30/30 eval |
| 4 | Archivist: assistant split-view Q&A, streamed, canon + optional RTS evidence | done |
| 5 | Registrar: Canvas Decision Register, App Home dashboard, digest | done |
| 6 | MCP server: 4 tools over Streamable HTTP, bearer auth, `/healthz` — verified from Claude Desktop | done |
| 7 | Seed world: 12 rulings + persona story arcs with real evidence permalinks; `/precedent backfill` + `@precedent backfill` archaeology (history scan, RTS-assisted when a token is present) | done |
| 8 | Hardening: retries, idempotency, tests | done |

## Tests

```bash
pytest tests/test_smoke.py -q        # fast, no external services
python tests/eval_runner.py          # 30-case contradiction eval (real Groq + Voyage)
```

## Layout

See [CLAUDE.md](CLAUDE.md) for the engineering spec, verified API-surface notes, hard constraints,
and the phase plan. Internal LLM prompts are versioned in [`prompts/`](prompts/). Judge walkthrough:
[docs/JUDGE_ACCESS.md](docs/JUDGE_ACCESS.md).

## Provider note

Dev runs on **Groq** (`llama-3.3-70b-versatile` / `llama-3.1-8b-instant`) + **Voyage** (`voyage-3.5`,
1024-dim) — both swappable via `LLM_PROVIDER` / `EMBED_MODEL` in `.env`. The hot path (Sentinel)
never calls Slack's RTS API — local pgvector only.
