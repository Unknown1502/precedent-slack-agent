# Precedent — Devpost submission text

> Copy each section into the matching Devpost field. Track: **New Slack Agent**.

---

## Tagline
Institutional memory, enforced — Precedent captures your team's decisions into a cited, human-ratified canon, defends it against drift in real time, and exposes it to every AI agent over MCP.

## The problem (hook)
Six months ago your team spent three weeks deciding a database standard. Today someone types *"let's just spin up MongoDB for the notifications service"* and quietly undoes it — no shared keywords with the original decision, no malice, just forgotten context. Slack search can't catch it because it's about *meaning*, not words. Precedent can.

## What it does
Three pillars, each a live demo beat:

1. **Remember** — Precedent watches enrolled channels and extracts genuine *decision moments* into structured Decision Objects (statement, rationale, alternatives rejected, dissent, evidence permalinks, supersede lineage). Capture is autonomous; **canon is human-ratified** — nothing becomes binding without a person clicking Approve. You can also react ⚖️ on any thread to capture it manually.

2. **Defend** — every assertive claim in an enrolled channel is checked against the ratified canon using **local vector similarity + an LLM contradiction judge**. A real conflict triggers a **private, ephemeral ⚖️ card** under the author's message: *"This may conflict with PRE-014 'Postgres for all new services' — ratified May 3, confidence 90% → [View ruling] [Propose supersede] [I'm aligned]."* Zero shared keywords. Before the drift ships. The supersede flow writes lineage and routes back through human ratification.

3. **Govern** — Precedent ships a **Model Context Protocol server** exposing `search_decisions`, `get_decision`, `check_conflict`, and `propose_decision`. Point Claude Desktop (or any MCP client) at it and it consults your org's decisions before acting — and can *propose* new ones that humans ratify back in Slack. The constitution every agent you deploy obeys.

## Try it yourself (judge sandbox)
Open **#eng-platform** in the Lumina Labs workspace and type any of these as a normal message — a private ⚖️ drift card fires within a few seconds:
- `for the notifications service let's just spin up MongoDB, faster for this shape of data` → **PRE-014**
- `I'll add a 15% off banner for students on the landing page this week` → **PRE-011**
- `pushing the billing retry fix straight to prod tonight, it's tiny` → **PRE-013**
- `let's book a design sync Wednesday 3pm` → **PRE-016**
- `we can just pipe EU events into the US cluster for now` → **PRE-017**
- `launching the onboarding A/B today, will post results Friday` → **PRE-021**

Then: **View ruling** to see rationale + dissent + lineage + source permalinks · open the **⚖️ Decision Register** canvas · open the bot's split-view and ask *"Why do we use Postgres for new services?"* · and drive the MCP loop from Claude Desktop with *"Draft a plan to launch a student discount."* Full instructions in JUDGE_ACCESS.md.

## How we built it
- **Slack**: Bolt for Python (Socket Mode), the `Assistant` split-view (streamed, cited answers via `say_stream`), Block Kit ratify/drift/decision cards, an auto-synced **Canvas** Decision Register, App Home dashboard, and the **Real-Time Search** API for Archivist evidence + `/precedent backfill` archaeology.
- **Retrieval**: Neon Postgres + **pgvector**; decisions embedded with Voyage `voyage-3.5` (1024-dim). The drift **hot path never calls RTS** — local vectors only — so it stays fast and rate-limit-safe under a live judge hammering it.
- **Reasoning**: a two-tier LLM split — a fast classifier gate (`llama-3.1-8b-instant`) on every message, a stronger judge (`llama-3.3-70b-versatile`) only when needed — on Groq. Every prompt is a versioned file in `/prompts`, loaded at runtime.
- **MCP**: the official Python SDK over Streamable HTTP with bearer auth; the tools reuse the exact same `canon` + `sentinel` code the Slack surfaces use — **one brain, two mouths**.
- **Rigor**: a 30-case contradiction eval (12 conflicts incl. 6 with zero keyword overlap, 18 non-conflicts) that passes **30/30** against the real models; idempotent interactive actions; retry-with-backoff on every external call.
- **Deploy**: two services from one Docker image on Railway (Socket Mode worker + public MCP), Neon for data. `GET /healthz` for uptime monitoring.

## Required-technology use (all three, load-bearing)
| Technology | How Precedent uses it |
|---|---|
| **Slack AI capabilities** | Assistant split-view with streamed, cited answers; Block Kit cards; auto-synced Canvas register; App Home dashboard |
| **Real-Time Search API** | Archivist conversational evidence + `/precedent backfill` archaeology; budgeted to ≤3 calls/inquiry; **never** in the drift hot path |
| **MCP server** | 4 tools over Streamable HTTP; external agents consult the canon and propose decisions that humans ratify in Slack |

## Honest comparison
| | Logs decisions | Enforces them in the moment | Machine-readable to agents |
|---|---|---|---|
| Decision Tracker (Marketplace) | ✅ manual | ❌ | ❌ |
| Slackbot / channel summaries | ⚠️ after the fact | ❌ | ❌ |
| **Precedent** | ✅ autonomous + human-ratified | ✅ real-time semantic drift card | ✅ MCP server, propose→ratify loop |

The concept of "tracking decisions" exists. Precedent's improvement is that it **enforces** them semantically in real time and makes them a rulebook agents obey — not a wiki nobody reads.

## Challenges we ran into
- **Semantic thresholding** — catching zero-keyword-overlap conflicts (Mongo↔Postgres) without false-firing on compliant near-misses ("using Postgres for the new service" must stay silent). Solved with a cheap cosine gate before an LLM judge, tuned against the 30-case eval.
- **RTS `action_token` flow** — the token is short-lived and only rides on message/app_mention events, so the Archivist degrades gracefully to canon-only when it's absent, and we log every fallback so it's never a silent surprise.
- **Seeding a believable world** — Slack can't backdate messages, so narrative dates live in message text and DB fields; personas are posted with custom names and their permalinks wired into each ruling's evidence.
- **Rate limits** — batching embeds and adding retry-with-backoff so a free-tier limit degrades to "slightly slower," never "silently no drift card."

## What's next
GitHub/Jira/Linear drift detection (a PR that violates a ruling gets the same card), decision expiry reviews, org-ready multi-workspace, and a Slackbot-as-MCP-client hookup so Slack's own AI consults the canon.

---

## Submission checklist (fill before submitting — deadline Jul 13, 5:00 PM PDT)
- [ ] Track selected: **New Slack Agent**
- [ ] Video: < 3:00, public (YouTube unlisted is fine), link pasted
- [ ] Architecture image: export the README Mermaid via mermaid.live → PNG, upload
- [ ] Sandbox: Lumina Labs invite link created (Slack → workspace name → Invite people → copy link) and pasted here
- [ ] Judge emails invited **and verified from a fresh account**: slackhack@salesforce.com · testing@devpost.com
- [ ] Repo public: https://github.com/Unknown1502/precedent-slack-agent (link JUDGE_ACCESS.md in the text)
- [ ] MCP URL + bearer token included for judges (JUDGE_ACCESS.md has the Claude Desktop config)
- [ ] Railway + Neon on paid/kept-alive through Aug 6 · /healthz monitored
- [ ] Contact handle filled in JUDGE_ACCESS.md
- [ ] Everything in English · all fields saved
