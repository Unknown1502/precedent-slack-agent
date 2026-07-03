# ⚖️ Precedent — institutional memory, enforced

A Slack-native agent that turns team conversations into a **cited, human-ratified canon of
decisions**, defends that canon in real time against drift with private nudges, and exposes it over
**MCP** so other AI agents consult it before acting.

Three pillars: **Remember** (capture decisions) · **Defend** (real-time drift detection) ·
**Govern** (MCP server with a propose → human-ratify loop).

## Setup (≈90 seconds after prerequisites)

Prerequisites: Python 3.11+, Docker (for local Postgres+pgvector), a Slack app (Socket Mode), and
Anthropic + Voyage API keys.

```bash
python -m venv .venv && . .venv/Scripts/activate      # Windows Git Bash
pip install -e .

# 1) Real Postgres + pgvector (host may already run PG on 5432/5433 — we publish 55432)
docker run -d --name precedent-pg \
  -e POSTGRES_USER=precedent -e POSTGRES_PASSWORD=precedent -e POSTGRES_DB=precedent \
  -p 55432:5432 pgvector/pgvector:pg16

# 2) Configure
cp .env.example .env      # fill SLACK_*, ANTHROPIC_API_KEY, VOYAGE_API_KEY
#   DATABASE_URL=postgresql://precedent:precedent@localhost:55432/precedent

# 3) Apply schema
python -m precedent.db.migrate

# 4) Boot the Slack app (Socket Mode)
python -m precedent.slack.app
```

Then in Slack: `/precedent help`.

## Layout
See [CLAUDE.md](CLAUDE.md) for the engineering spec, verified API-surface notes, hard constraints,
and the phase plan. Internal LLM prompts are versioned in [`prompts/`](prompts/).

## Status
Phase 0 (scaffold) complete: schema applied and verified against a real Postgres; Bolt app
constructs and registers `/precedent` + App Home listeners. Live Slack boot verified once workspace
tokens are configured.
