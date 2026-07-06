# ⚖️ Precedent — institutional memory, enforced

A Slack-native agent that turns team conversations into a **cited, human-ratified canon of
decisions**, defends that canon in real time against drift with private nudges, and exposes it over
**MCP** so other AI agents consult it before acting.

Three pillars: **Remember** (manual + autonomous capture → human-ratified canon) · **Defend**
(real-time drift detection, local-only) · **Govern** (MCP server with a propose → human-ratify loop).

## Architecture

Two invariants hold everywhere: **(1)** nothing enters the canon as `ratified` without a human
clicking **Approve**, and **(2)** the drift hot path uses **local pgvector only — never the
Real-Time Search API**. The Slack surfaces and the MCP server call the *same* `canon` + `sentinel`
code — one brain, two mouths. Full component breakdown, data model, and request lifecycles:
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

```mermaid
flowchart TD
    subgraph SLACK["Slack workspace"]
        MSG["Channel message"]
        REACT["scales reaction · /precedent"]
        SPLIT["Assistant split-view Q and A"]
        SURF["App Home + Canvas Register"]
    end

    subgraph WORKER["Bolt for Python · Socket Mode worker · Railway"]
        GATE{{"Gatekeeper<br/>llama-3.1-8b · every message<br/>decision_moment · assertive_claim · neither"}}
        EXTRACT["Extractor<br/>thread → Decision Object"]
        SENTINEL["Sentinel — drift defense<br/>embed → pgvector top-k → LLM judge"]
        ARCHIVIST["Archivist<br/>streamed, cited answer"]
        REGISTRAR["Registrar<br/>Canvas · App Home · digest"]
    end

    CANON[("Canon — Neon Postgres + pgvector<br/>decisions · lineage · drift_events · enrollment")]
    VOYAGE["Voyage voyage-3.5<br/>embeddings 1024-dim"]
    GROQ["Groq LLMs"]

    subgraph MCPBOX["MCP server · Streamable HTTP + bearer · Railway"]
        MCPTOOLS["search_decisions · get_decision<br/>check_conflict · propose_decision"]
    end
    AGENT["Claude Desktop / any MCP client"]
    HUMAN{{"Human Approve<br/>— nothing is ratified without this —"}}

    MSG --> GATE
    GATE -->|decision_moment| EXTRACT
    GATE -->|assertive_claim| SENTINEL
    REACT --> EXTRACT
    SPLIT --> ARCHIVIST

    EXTRACT -->|Ratify card| HUMAN
    SENTINEL -->|ephemeral drift card| MSG
    SENTINEL -->|Propose supersede| HUMAN
    HUMAN -->|ratify / supersede + embed| CANON
    ARCHIVIST --> SPLIT
    REGISTRAR --> SURF

    EXTRACT --> CANON
    SENTINEL --> CANON
    ARCHIVIST --> CANON
    REGISTRAR --> CANON
    SENTINEL -->|claim embedding| VOYAGE
    VOYAGE --> CANON
    ARCHIVIST -.->|RTS ≤3 · questions only| SLACK

    GATE -.-> GROQ
    EXTRACT -.-> GROQ
    SENTINEL -.-> GROQ
    ARCHIVIST -.-> GROQ

    AGENT <-->|MCP| MCPTOOLS
    MCPTOOLS --> CANON
    MCPTOOLS -->|check_conflict| SENTINEL
    MCPTOOLS -->|propose_decision| HUMAN
```

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

## Live deployment

Production runs as **two Railway services from the one Dockerfile** (Socket Mode worker + MCP
server) against **Neon** Postgres+pgvector:

```bash
curl https://daring-rejoicing-production-01d2.up.railway.app/healthz
# {"status":"ok","service":"precedent-mcp"}   (tool calls require a bearer token; no auth → 401)
```

Full judge walkthrough: [docs/JUDGE_ACCESS.md](docs/JUDGE_ACCESS.md) · Deploy runbook + gotchas:
[docs/DEPLOY.md](docs/DEPLOY.md).

## Try it yourself (judge sandbox)

In the **Lumina Labs** workspace, type any of these as a normal message — a private, ephemeral ⚖️
**drift card** fires within a few seconds, citing the ruling it conflicts with (zero shared keywords):

| Message | Fires | Why it's hard |
|---|---|---|
| `for the notifications service let's just spin up MongoDB, faster for this shape of data` | **PRE-014** | MongoDB vs "Postgres" — no shared words |
| `I'll add a 15% off banner for students on the landing page this week` | **PRE-011** | discount freeze until Q4 review |
| `pushing the billing retry fix straight to prod tonight, it's tiny` | **PRE-013** | billing change with no feature flag |
| `let's book a design sync Wednesday 3pm` | **PRE-016** | no-meeting Wednesdays |
| `we can just pipe EU events into the US cluster for now` | **PRE-017** | EU data residency |
| `launching the onboarding A/B today, will post results Friday` | **PRE-021** | unregistered A/B test |

> Debounce by design: **one card per person per channel per ~2 min** — fire each landmine in a
> *different* channel (`#eng-platform`, `#pricing`, `#growth`, …) or wait between them.

Then: **📖 View ruling** → rationale, dissent, lineage, source permalinks · open the **⚖️ Canvas
Decision Register** · ask the assistant split-view *"Why do we use Postgres for new services?"* · and
from **Claude Desktop** (MCP config in [JUDGE_ACCESS.md](docs/JUDGE_ACCESS.md)) ask *"Draft a plan to
launch a student discount"* → it calls `check_conflict`, surfaces **PRE-011**, and `propose_decision`
posts a Ratify card back into Slack for a human to approve.

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
