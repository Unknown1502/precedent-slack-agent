# PRECEDENT — MASTER BUILD PROMPT
### Paste this file into your AI coding agent (Claude Code: save as CLAUDE.md in repo root; Cursor: add to project rules). Work strictly phase-by-phase. Do not skip acceptance criteria.

---

## ROLE & MISSION

You are the lead engineer implementing **Precedent**, a Slack AI agent for the Slack Agent Builder Challenge (deadline July 13, 2026). Precedent (1) extracts team decisions from Slack threads into human-ratified, structured "Decision Objects" with evidence permalinks and supersede lineage, (2) detects in real time when a new message semantically contradicts a ratified decision and privately nudges the author with a cited card, and (3) exposes the decision canon over an MCP server so external AI agents can search it, check plans against it, and propose new decisions that humans ratify in Slack.

Optimize for: demo reliability (the drift card must fire 10/10 on scripted inputs), judge-readable code, and product polish. This is a hackathon vertical slice, not a platform — when in doubt, choose the simpler implementation that demos flawlessly.

## NON-NEGOTIABLE CONSTRAINTS

1. **Stack:** Node 20 + TypeScript everywhere. Slack: **Bolt for JavaScript** (`@slack/bolt`), Socket Mode in dev, HTTP mode in prod. DB: **Postgres + pgvector** (Neon), ORM: **drizzle**. LLM: **Anthropic API** (`@anthropic-ai/sdk`) — `claude-haiku-4-5` for the Gatekeeper classifier, `claude-sonnet-4-6` for Extractor/Sentinel/Archivist (verify current model IDs at https://docs.claude.com/en/docs/about-claude/models before pinning; keep model IDs in env). Embeddings: `voyage-3` (1024-dim) via Voyage API, or `text-embedding-3-small` (1536-dim) — pick ONE, set `EMBED_DIM` accordingly, and keep an `embeddings.ts` adapter so it's swappable. MCP: `@modelcontextprotocol/sdk` with **Streamable HTTP** transport. Deploy: Railway or Fly.
2. **RTS rate discipline:** `assistant.search.context` is limited (~10/min/user). It is **NEVER called in the per-message hot path**. Drift detection uses the local pgvector index only. RTS is used solely in: Archivist user inquiries (≤3 calls per inquiry, enforced by a counter) and `/precedent backfill` (≤5 calls, admin-triggered).
3. **Human-in-the-loop:** nothing enters canon with status `ratified` without a human clicking Approve on a Ratify card. `propose_decision` over MCP creates `proposed` rows only.
4. **Privacy defaults:** drift cards are ephemeral (author-only). The bot processes only channels where it is a member AND enrollment mode is `observe`. Store permalinks + short quotes (≤200 chars) as evidence, never full transcripts.
5. **Never block a channel:** every LLM call has a 15s timeout + 2 retries; on failure, log and stay silent. All Slack action handlers `ack()` within 3 seconds (do heavy work after ack).
6. **Scope freeze:** do NOT build integrations (GitHub/Jira), web dashboards, multi-workspace support, or anything not listed in the phases below.

## REPOSITORY LAYOUT (create exactly this)

```
precedent/
├─ CLAUDE.md                      # this file
├─ package.json  pnpm-workspace.yaml  tsconfig.base.json  .env.example
├─ apps/slack/src/
│  ├─ app.ts                      # Bolt init (Socket/HTTP switch), Assistant middleware wiring
│  ├─ listeners/ messages.ts actions.ts commands.ts events.ts assistant.ts reactions.ts home.ts
│  ├─ agents/ gatekeeper.ts extractor.ts sentinel.ts archivist.ts
│  ├─ blocks/ ratifyCard.ts driftCard.ts decisionCard.ts appHome.ts digest.ts
│  └─ services/ anthropic.ts embeddings.ts canon.ts rts.ts canvas.ts slack.ts telemetry.ts
├─ apps/mcp/src/ server.ts tools.ts auth.ts
├─ packages/db/src/ schema.ts client.ts migrate.ts
├─ prompts/ gatekeeper.md extractor.md sentinel.md archivist.md   # versioned prompt files, loaded at runtime
├─ scripts/seed/ world.ts personas.ts arcs/*.ts run-seed.ts insert-canon.ts
├─ tests/ contradiction.eval.jsonl eval-runner.ts extractor.fixtures.test.ts
└─ docs/ WORLD.md DEMO_SCRIPT.md JUDGE_ACCESS.md architecture.md
```

## ENV (.env.example)

```
SLACK_BOT_TOKEN= SLACK_APP_TOKEN= SLACK_SIGNING_SECRET=
ANTHROPIC_API_KEY= MODEL_GATE=claude-haiku-4-5 MODEL_REASON=claude-sonnet-4-6
VOYAGE_API_KEY= EMBED_MODEL=voyage-3 EMBED_DIM=1024
DATABASE_URL= MCP_BEARER_TOKEN= PORT=3000 MODE=socket|http
DRIFT_THRESHOLD=0.78 SEED_MODE=0
```

## SLACK APP MANIFEST (features to enable in api.slack.com/apps)

- **Agents & AI Apps: ON** (required for assistant threads + RTS action_token delivery).
- Bot scopes: `app_mentions:read, channels:history, groups:history, im:history, mpim:history, chat:write, chat:write.customize, reactions:read, reactions:write, commands, users:read, canvases:read, canvases:write, assistant:write, search:read.public` (add `search:read.private` if sandbox allows).
- Events (bot): `message.channels, message.groups, message.im, message.mpim, app_mention, reaction_added, assistant_thread_started, assistant_thread_context_changed, app_home_opened, member_joined_channel`.
- Slash command: `/precedent` (subcommands: `log`, `backfill`, `help`).
- Interactivity: ON (Socket Mode in dev handles it).

## ⚠️ SLACK GOTCHAS — READ BEFORE EACH PHASE (hard-won; violating these wastes a day)

G1 **action_token for RTS:** bot-token calls to `assistant.search.context` require an `action_token` found in the event payload (message / app_mention events on AI-enabled apps). It is short-lived — capture it in the listener and use it immediately in the same request flow; never store it for later.
G2 **Semantic mode** triggers when the query is a natural-language *question* AND the workspace has Slack AI Search. Always phrase Archivist RTS queries as questions ("What did the team decide about database choices?"). Call `assistant.search.info` at startup and log capabilities; degrade gracefully to keyword mode.
G3 **No backdating:** `chat.postMessage` cannot set past timestamps. The seeded world's "history" is carried by narrative dates *inside message text* and by `decided_at` fields in the DB (the drift card cites the DB date, e.g., "ratified May 3"). Do not attempt ts spoofing.
G4 **Bot-message loops:** seeded messages are bot-authored (`subtype: bot_message` / `bot_id` set). The Gatekeeper listener must skip: our own bot's messages, `message_changed/deleted` subtypes, and anything when `SEED_MODE=1`. Judges' *human* messages are what trigger drift live.
G5 **Membership required:** message events only arrive for channels the bot is in. The seed script must invite/join the bot to every seeded channel.
G6 **ack() fast:** Bolt action/command handlers must `ack()` immediately; run LLM work after. Ephemeral drift card: `chat.postEphemeral({channel, user: authorId, thread_ts?})`.
G7 **Permalinks:** collect via `chat.getPermalink` right after each seed post; store in evidence. RTS results also return permalinks — prefer those for Archivist citations.
G8 **Canvas:** create a standalone canvas via `canvases.create`, update via `canvases.edit` (document content operations, markdown). Keep one "Decision Register" canvas ID in DB; on every canon change, regenerate the full markdown and replace (simplest reliable sync). Link it in App Home and pin in #decisions.
G9 **Assistant middleware:** use Bolt's `Assistant` class — handlers for `threadStarted` (send greeting + `setSuggestedPrompts`) and `userMessage` (set `setStatus('consulting the case law…')`, then respond). If token/SDK supports streaming APIs use them; otherwise post once and edit via throttled `chat.update` (≥700ms between updates) to simulate streaming.
G10 **RTS result hygiene:** pass `include_bots: true` when searching seeded content (it's bot-authored, see G4); strip Slack formatting from queries; max 20 results/page; use `conversations.replies` to expand a hit's thread when the Archivist needs depth (counts against your ≤3 budget only for RTS calls, not replies).

---

## PHASES (each ends with acceptance criteria — do not proceed until green)

### PHASE 0 — Scaffold (Jul 2)
Monorepo (pnpm), Bolt app boots in Socket Mode, `/precedent help` replies, `app_home_opened` publishes a stub Home. Drizzle connects to Neon; `migrate.ts` applies schema below. Telemetry: pino logger with per-event correlation ids.
**Schema (packages/db/src/schema.ts):**
```sql
decisions(id text pk,              -- 'PRE-014'
  title text not null, statement text not null, rationale text,
  alternatives jsonb, dissent jsonb, scope text,
  status text not null default 'proposed',   -- proposed|ratified|superseded|expired
  decided_by text[], ratified_by text, supersedes_id text references decisions(id),
  superseded_by text, expires_hint text,
  evidence jsonb not null,                    -- [{permalink, channel_id, ts, quote}]
  embedding vector(EMBED_DIM),
  decided_at date,                            -- narrative date (G3)
  created_at timestamptz default now(), team_id text not null);
drift_events(id bigserial pk, decision_id text references decisions(id),
  message_permalink text, channel_id text, author text, claim text,
  confidence real, resolution text default 'open',   -- open|aligned|superseded|dismissed
  created_at timestamptz default now());
channel_enrollment(channel_id text pk, mode text default 'observe');  -- observe|manual_only
meta(key text pk, value text);                -- canvas_id, counters, etc.
```
✅ *Accept:* app runs locally; `/precedent help` works; `SELECT` against all tables succeeds.

### PHASE 1 — Canon service + manual capture (Jul 3)
`canon.ts`: `createProposed(obj)`, `ratify(id, userId)` (sets status+ratified_by, computes+stores embedding of `title + '. ' + statement + ' ' + rationale`), `supersede(oldId, newObj, userId)` (new ratified row, old→superseded, links both ways), `getWithLineage(id)`, `searchLocal(text, k=5)` (embed → cosine via pgvector `<=>`), `nextId()` (PRE-###).
Listeners: `reaction_added` where `reaction==='scales'` and message is in a thread → run Extractor on that thread; `/precedent log` inside a thread → same.
Extractor (`agents/extractor.ts`): fetch full thread via `conversations.replies`, map to `{author_name, text, permalink}`, call MODEL_REASON with **prompts/extractor.md** (below), parse strict JSON, `createProposed`, post **Ratify card** in-thread. Action handlers: Approve → `ratify` + replace card with confirmation + trigger Canvas sync; Edit → modal prefilled (title/statement/rationale editable) → save → ratify; Dismiss → delete proposed row + card note.
✅ *Accept:* ⚖️ on a real thread produces a correct card; Approve creates a ratified decision retrievable with lineage; embedding row present.

### PHASE 2 — Gatekeeper (Jul 4)
`listeners/messages.ts`: on every channel message → apply G4 filters → check enrollment → call Gatekeeper (**prompts/gatekeeper.md**, MODEL_GATE, temperature 0, max_tokens 60) with the message + up to 6 prior thread messages for context. On `decision_moment` (conf ≥ .8) → Extractor path. On `assertive_claim` (conf ≥ .7) → Sentinel path (Phase 3). Log every classification to telemetry with latency.
✅ *Accept:* posting a mini decision conversation in a test channel yields an unprompted Ratify card within ~8s; chit-chat yields nothing; classifier p95 latency <1.5s.

### PHASE 3 — Sentinel: drift defense (Jul 5) — **the product**
`agents/sentinel.ts`: embed claim → `searchLocal(claim, k=4)` filtered `status='ratified'` → if top cosine similarity < 0.45 stop (cheap gate) → else call MODEL_REASON with **prompts/sentinel.md** giving the claim + the k candidates → parse verdicts → if best verdict `contradicts` with confidence ≥ `DRIFT_THRESHOLD` → insert `drift_events` → `chat.postEphemeral` the **Drift card**. Buttons: *View ruling* (opens decision card modal w/ lineage + permalinks), *I'm aligned* (resolution=aligned, card thanks + auto-dismiss note), *Propose supersede* (modal: new statement + rationale prefilled from the claim → creates proposed decision with `supersedes_id`, posts Ratify card to the ruling's home channel; on approval `supersede()` runs). Debounce: max 1 drift card per user per channel per 2 minutes; never fire on messages that are themselves inside an active ratify/supersede thread.
Build **tests/eval-runner.ts** now: reads `contradiction.eval.jsonl` (format: `{"claim":"...","expected":"PRE-014"|null}`), runs the full sentinel path against a fixture canon, prints precision/recall and a pass/fail table. Author 30 cases: 12 true conflicts (≥6 with zero keyword overlap), 10 unrelated, 8 compliant-or-near-miss (e.g., "using Postgres for the new service" must NOT fire). Tune `DRIFT_THRESHOLD` until 12/12 conflicts caught, 0/18 false fires.
✅ *Accept:* eval 30/30; typing landmine L1 in the test channel fires the card in <5s p95, ephemeral, correctly cited.

### PHASE 4 — Archivist + RTS (Jul 6)
`listeners/assistant.ts` with Bolt Assistant (G9). On userMessage: (1) `setStatus`; (2) `searchLocal` over canon; (3) if the question needs conversational evidence, up to **3** `assistant.search.context` calls (G1/G2/G10) via `services/rts.ts` (which enforces the counter and Retry-After handling); (4) optionally one `conversations.replies` expansion; (5) compose with **prompts/archivist.md**; (6) stream/throttle-update the answer; (7) `setSuggestedPrompts` with 3 canon-aware follow-ups. `setTitle` from first question.
✅ *Accept:* "Why do we use Postgres for new services?" returns ruling + rationale + dissent + lineage + ≥2 working permalinks; RTS call counter never exceeds 3; works in keyword-only mode too.

### PHASE 5 — Registrar (Jul 7)
`services/canvas.ts`: ensure-or-create "📖 Decision Register" canvas (id in `meta`), regenerate full markdown on canon change (grouped by scope; each ruling: id, title, status badge, decided_at, ratified_by, one-line rationale, evidence links, lineage arrows). `blocks/appHome.ts`: header stats (ratified / pending / open drift), pending-ratification list with Approve buttons, recent drift events, enrollment toggles per channel (multi-select of channels bot is in), link to Canvas. `digest.ts`: `/precedent digest` posts the weekly summary to #decisions (cron optional — command is enough for demo). `/precedent backfill` (admin): ≤5 RTS question-queries over themes ("What has the team decided about databases?", pricing, process…) → cluster hits by thread → run Extractor on top 3–5 threads → post Ratify cards to #decisions.
✅ *Accept:* Approving a decision updates Canvas within 5s; App Home reflects live counts; backfill proposes ≥3 sensible rulings on the seeded world.

### PHASE 6 — MCP server (Jul 8)
`apps/mcp`: Streamable HTTP server, bearer auth (`MCP_BEARER_TOKEN`). Tools (zod-typed):
```
search_decisions({query, status?}) → [{id,title,statement,status,decided_at}]
get_decision({id}) → full object + lineage: {ancestors[], descendants[]}
check_conflict({proposed_action}) → runs the SAME sentinel path → {verdict:'clear'|'review'|'conflict', conflicts:[{id,title,statement,confidence,reason}]}
propose_decision({title,statement,rationale}) → creates proposed row + posts Ratify card to #decisions → {id, status:'proposed', note:'awaiting human ratification in Slack'}
```
Reuse `canon.ts`/`sentinel.ts` via the shared package — one brain, two mouths. Write `docs/JUDGE_ACCESS.md` MCP section with the exact Claude Desktop `mcpServers` JSON snippet.
✅ *Accept:* From Claude Desktop, the student-discount prompt triggers `check_conflict` surfacing PRE-011, and `propose_decision` makes a Ratify card appear in #decisions; approving it flips status to ratified and the MCP `get_decision` reflects it.

### PHASE 7 — Seed world (built Jul 4–5, FINAL run Jul 9)
`scripts/seed/`: `personas.ts` (35 personas: name, role, icon_url from generated avatars, voice notes), `arcs/*.ts` (each arc = ordered messages with channel, persona, text incl. narrative dates, optional thread structure), `run-seed.ts` (SEED_MODE=1 → join/invite bot to channels → post via `chat.postMessage` with `username`+`icon_url` (needs `chat:write.customize`) → 300–700ms jitter → collect permalinks via `chat.getPermalink` → write `seed-output.json`), `insert-canon.ts` (reads seed-output → inserts the 12 rulings from docs/WORLD.md with evidence permalinks, narrative `decided_at`, embeddings). Idempotent: a `--wipe` flag clears DB tables (never deletes Slack messages; re-runs go to a fresh workspace).
✅ *Accept:* fresh workspace → one command → world exists, 12 rulings queryable, all 6 landmines fire when typed by a human account.

### PHASE 8 — Hardening + polish (Jul 9–11)
Retries/timeouts audited on every external call; idempotency keys on ratify/supersede actions (double-click safe); empty states (App Home with zero decisions; Archivist with empty canon); onboarding DM on `member_joined_channel` for the bot ("Here's how Precedent works + link to Register"); error copy pass; `GET /healthz` for uptime monitor; README with 90-second local setup; screenshots; `pnpm test` green in CI (GitHub Actions, single job).
✅ *Accept:* the six quality gates in the Playbook §8 all pass; a teammate who has never run the repo gets it live locally in <15 minutes using only the README.

---

## INTERNAL LLM PROMPTS (create these files verbatim in /prompts; runtime loads them)

### prompts/gatekeeper.md  (system prompt; MODEL_GATE; temp 0; expect ONLY JSON)
```
You classify a single Slack message (with brief thread context) for a decision-tracking system.

Labels:
- "decision_moment": the message, in context, indicates a group has just converged on OR explicitly declared a choice about how the team/org will do something (agreement words, "let's go with", "decided", "we'll do X then", approvals concluding a debate).
- "assertive_claim": the author states an intent, plan, or matter-of-fact about how something IS or WILL BE done that could conflict with a standing policy (e.g., "I'll ship X tonight", "we're using Y for this", "let's book Z on Wednesday"). Questions, opinions, jokes without intent, and pure information sharing are NOT assertive_claims.
- "neither": everything else (greetings, questions, status chatter, links, banter).

Rules: prefer "neither" when unsure. A message can be decision_moment only if the DECISION is visible in the provided context, not merely discussion. Output strict JSON, nothing else:
{"label":"decision_moment"|"assertive_claim"|"neither","confidence":0.0-1.0}
```

### prompts/extractor.md  (system; MODEL_REASON; temp 0.2; strict JSON)
```
You convert a Slack thread into a structured organizational Decision Object. You receive messages as JSON: [{author, text, permalink}].

Extract ONLY what the thread supports. Never invent rationale, dissent, or alternatives. If the thread does not actually contain a converged decision, return {"is_decision": false}.

Output strict JSON:
{
 "is_decision": true,
 "title": "<≤8 words, noun-phrase>",
 "statement": "<ONE normative, enforceable sentence in present tense, e.g. 'All new services use Postgres.'>",
 "rationale": "<why, from the thread, ≤2 sentences>",
 "alternatives": [{"option":"...","why_rejected":"..."}],        // [] if none discussed
 "dissent": [{"author":"...","summary":"<their objection, neutral>"}],  // [] if none
 "decided_by": ["<author names who converged/approved>"],
 "scope": "engineering"|"product"|"design"|"growth"|"ops"|"org",
 "expires_hint": "<condition to revisit, or null>",
 "evidence": ["<permalink of the 1-4 most decision-carrying messages>"]
}
The statement must be checkable against future messages. Bad: "Team discussed databases." Good: "All new services use Postgres."
```

### prompts/sentinel.md  (system; MODEL_REASON; temp 0; strict JSON)
```
You are a precedent-compliance judge. Given ONE new Slack claim and up to 4 ratified organizational decisions, decide for each whether the claim CONTRADICTS it.

"contradicts" = if the claim's stated action happened, it would violate the decision's statement (directly or by clear implication). Semantic conflicts count even with zero shared words. 
"complies" = the claim actively follows the decision.
"unrelated" = no meaningful interaction. When uncertain between contradicts and unrelated, choose unrelated (false alarms erode trust).

Consider scope: a claim about a side project or hypothetical ("what if we…", "imagine we…") is NOT a contradiction. Questions are never contradictions.

Input: {"claim":"...", "candidates":[{"id","statement","rationale","scope"}]}
Output strict JSON:
{"results":[{"id":"PRE-014","verdict":"contradicts"|"complies"|"unrelated","confidence":0.0-1.0,
 "reason":"<≤20 words naming the specific tension>"}]}
```

### prompts/archivist.md  (system; MODEL_REASON; temp 0.3)
```
You are Precedent's Archivist: you answer questions about what this organization has decided, using ONLY the provided canon objects and Slack search snippets. Never use outside knowledge about the org; never invent decisions.

Answer shape (Slack mrkdwn, concise):
1. *The ruling* — cite the decision id and statement.
2. *Why* — rationale in one or two sentences.
3. *Dissent / alternatives* — if recorded, one line.
4. *Lineage* — if superseded/superseding, show PRE-a → PRE-b with dates.
5. *Sources* — bullet the evidence permalinks (and any RTS snippet permalinks used).
If the canon has nothing relevant: say so plainly, show the closest RTS snippets if any, and offer: "Want me to log this as a new decision? React ⚖️ on the deciding thread or use /precedent log."
Keep answers under 180 words unless asked for detail.
```

---

## BLOCK KIT TEMPLATES (implement as functions; these are the shapes)

**Ratify card (in-thread):** header "⚖️ Decision detected — ratify?" · section: *{title}* — {statement} · context: rationale line · fields: decided_by, scope, dissent-count · actions: [✅ Approve] [✏️ Edit] [✖️ Dismiss] · context footer: "Nothing enters canon without a human approval. · evidence: {n} linked messages".

**Drift card (ephemeral):** section: "⚖️ *Heads up — this may conflict with* *{PRE-014 — title}*" · context: "ratified {decided_at} by {ratified_by} · {approvals} approvals · confidence {NN}%" · quote block: decision statement · context: reason (from sentinel) · actions: [📖 View ruling] [🔁 Propose supersede] [👍 I'm aligned] · footer: "Only you can see this."

**Decision card (modal/message):** title/statement/rationale · alternatives rejected list · dissent list · lineage line (PRE-006 → *PRE-014*) · evidence permalinks · status badge.

---

## DEFINITION OF DONE (submission-ready)

☐ All phase acceptance criteria green ☐ eval 30/30 with screenshot ☐ six landmines fire 10/10 for a human tester ☐ MCP round-trip demoed from Claude Desktop ☐ Canvas + App Home live ☐ README + JUDGE_ACCESS.md complete ☐ deployed on paid-tier infra with /healthz monitored ☐ repo public, prompts visible, CI green ☐ zero RTS calls in message hot path (grep-verified) ☐ fresh-account walkthrough done by someone who didn't build it.

## DO NOT (final guardrails)

- Do not call RTS from the Gatekeeper/Sentinel path. - Do not auto-ratify anything. - Do not post drift cards publicly. - Do not attempt Slack timestamp backdating. - Do not add features outside the phases. - Do not hardcode secrets. - Do not let any handler exceed 3s before ack. - Do not ship a prompt file that isn't the versioned source of truth for what runs.
