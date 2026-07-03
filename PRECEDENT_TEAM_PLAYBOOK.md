# PRECEDENT — TEAM PLAYBOOK (v2, Team of 4)
### The single source of truth for the next 11 days. If it's not in here, we don't build it.

**Product:** Precedent — *Institutional memory, enforced.*
**Hackathon:** Slack Agent Builder Challenge (Devpost) · **Track: New Slack Agent**
**Hard deadline:** July 13, 2026, 5:00 PM PDT = **July 14, 5:30 AM IST** · **Our deadline: July 12, 11:59 PM IST**
**Prize target:** Track 1st ($8k + Dreamforce). Realistic floor: Most Innovative / Best Technological Implementation ($2k each).
**Judge emails to grant sandbox access:** slackhack@salesforce.com · testing@devpost.com

---

## 1. THE PRODUCT ON ONE PAGE (memorize this — everyone must be able to say it)

**One-liner:** Precedent is a Slack-native agent that turns your team's conversations into a living, cited canon of decisions — then defends that canon in real time against human drift, and exposes it over MCP as the rulebook every other AI agent consults before acting.

**The wow (0:18 of the video):** a teammate types *"let's just spin up MongoDB for the notifications service"* → an ephemeral ⚖️ card appears under their message: **"This may conflict with PRE-014 'Postgres for all new services' — ratified May 3 by @priya, 4 approvals → [View ruling] [Propose supersede] [I'm aligned]."** Zero shared keywords. Private. Before the drift ships.

**Three pillars (= three demo beats):**
1. **Remember** — autonomous extraction of decisions from threads into structured, human-ratified Decision Objects with rationale, alternatives rejected, dissent, evidence permalinks, and supersede lineage (decisions as case law).
2. **Defend** — real-time semantic drift detection: new messages are checked against the canon; conflicts trigger a private, cited nudge with a one-click supersede flow.
3. **Govern** — a Precedent MCP server (`search_decisions`, `get_decision`, `check_conflict`, `propose_decision`) so Claude/Cursor/any MCP agent consults the org's decisions before acting — and can *propose* decisions that humans ratify back in Slack.

**Positioning sentence for judges:** "Decision Tracker (Marketplace) logs decisions *manually*. Slackbot summarizes them *after the fact*. Precedent captures them autonomously, **enforces them in the moment**, and makes them **machine-readable for every agent you deploy**. Slack built the agent OS; Precedent is its constitution."

**Required-tech mapping (all three, each load-bearing):**
- **RTS API** → Archivist Q&A evidence + archaeology backfill (semantic recall; cite permalinks; ≤3 calls/inquiry; never in the per-message hot path).
- **Slack AI capabilities** → assistant split-view thread, streaming, setStatus/setSuggestedPrompts/setTitle, Block Kit ratify/drift cards, Canvas Decision Register, App Home dashboard.
- **MCP** → we *ship a server*; governance loop = agent proposes → humans ratify in Slack.

---

## 2. SCOPE — FROZEN

**IN (all must work in the judge sandbox):**
F1 Manual capture: `/precedent log` in a thread + ⚖️ reaction → Extractor → Ratify card → canon.
F2 Autonomous capture: Gatekeeper watches enrolled channels → detects decision moments → Ratify card.
F3 Drift defense: Sentinel checks assertive claims vs canon (local pgvector) → ephemeral drift card → [View ruling]/[Propose supersede]/[I'm aligned]; supersede writes lineage.
F4 Archivist: assistant split-view Q&A ("Why do we use Postgres?") → canon + RTS semantic search → streamed, permalink-cited answer; suggested prompts; status line.
F5 Registrar: Canvas "Decision Register" auto-synced; App Home dashboard (Active / Pending / Drift events); Monday digest message.
F6 MCP server: 4 tools live over Streamable HTTP; demoed from Claude Desktop incl. propose→ratify round trip.
F7 Archaeology-lite: on demand (`/precedent backfill`), run bounded RTS queries over seeded history → propose 3–5 rulings. (Scaled-down, honest version of "mined 90 days".)
F8 Seed world: "Lumina Labs" — ~10 channels, ~35 personas, ~1,200–1,500 messages, 12 pre-loaded canon rulings, 6 drift landmines judges can trigger themselves.
F9 Tests: 30-case contradiction eval set green; extraction fixtures; screenshot for the video.

**OUT (forbidden before Jul 12 — reply "roadmap" to anyone who suggests these):** GitHub/Jira/Linear integrations, offboarding handover, Slack Connect, multi-workspace/org-ready, web dashboard, Workflow Builder step, Slackbot-MCP-Client hookup beyond a 2-hour timeboxed attempt on Jul 8, notifications settings UI beyond per-channel on/off.

---

## 3. TEAM OF 4 — ROLES & INTERFACES

> Pick the Dictator on day 1 (default: Person A). Dictator breaks ties in <5 minutes; no design meetings >15 min.

**Person A — Pipeline Owner (strongest backend/LLM person).** Owns: canon store (Neon Postgres + pgvector + drizzle), Gatekeeper, Extractor, Sentinel, embeddings, the four internal LLM prompts, threshold tuning, eval set. *Interface out:* `canon.ts` service API (create/ratify/supersede/searchLocal/getWithLineage) + typed events (`decision.pending`, `drift.detected`).
**Person B — Slack Surfaces Owner.** Owns: Bolt listeners, Block Kit (ratify card, drift card, decision card, App Home), assistant thread (Assistant middleware: threadStarted/userMessage, setStatus/SuggestedPrompts/Title, streaming or throttled chat.update), Canvas sync, slash commands, ephemeral flows, RTS client (`rts.ts` incl. action_token handling). *Interface in:* consumes A's events; renders; calls back `ratify()/supersede()`.
**Person C — Infra + MCP + Seed Owner.** Owns: deploy (Railway/Fly + HTTP mode), env/secrets, MCP server (@modelcontextprotocol/sdk, 4 tools, bearer auth), Claude Desktop config + recording rig, seed script (posts via chat.postMessage+customize → collects permalinks via chat.getPermalink → direct-inserts 12 canon rulings with narrative dates), uptime monitor through Aug 6.
**Person D — Demo Producer (NOT the junior role).** Owns: Lumina Labs story bible (writes every seeded message arc + the 6 landmines with A/C), video (script §6, shoot, edit, captions), architecture diagram (Excalidraw, from Playbook §4), Devpost text, JUDGE_ACCESS.md, fresh-account QA every evening from Jul 8, mock-judging on Jul 11.

**Daily rhythm:** 15-min standup (what shipped / blocked / today), IST evening integration checkpoint where the *current vertical slice is demoed live* — if it can't be demoed, it didn't ship.

---

## 4. ARCHITECTURE (Person D redraws this prettily for submission)

```
 Slack Workspace ──events──▶ Bolt App (Node 20, Socket Mode dev / HTTP prod)
   channels/threads              │
   assistant split-view          ├─ Gatekeeper (claude-haiku-4-5): every message in enrolled
   App Home / Canvas             │    channels → decision_moment | assertive_claim | neither
   Block Kit cards               │
                                 ├─ Extractor (claude-sonnet-4-6): thread → Decision Object
                                 │    → Ratify card (human ✓ required) → CANON
                                 │
                                 ├─ Sentinel (sonnet): claim → embed → pgvector top-k vs CANON
                                 │    → contradiction judgment → ephemeral drift card
                                 │    → supersede flow writes lineage
                                 │
                                 ├─ Archivist (sonnet): assistant thread Q&A
                                 │    → CANON lookup + RTS assistant.search.context (semantic,
                                 │      action_token, ≤3 calls) + conversations.replies
                                 │    → streamed cited answer (permalinks)
                                 │
                                 └─ Registrar (worker): Canvas Register sync · App Home · digest

 CANON: Neon Postgres + pgvector (decisions, lineage, drift_events, enrollment)
 MCP Server (Streamable HTTP): search_decisions · get_decision · check_conflict · propose_decision
   ◀── Claude Desktop / Cursor / any MCP client   propose_decision ──▶ Ratify card in Slack
 Hot-path rule: drift checks NEVER call RTS (rate limits) — local vectors only.
```

Full schema, scopes, events, prompts, Block Kit JSON, and phase-by-phase build instructions live in **PRECEDENT_BUILD_PROMPT.md** — that file is the engineering spec; this file is the operation.

---

## 5. DAY-BY-DAY MATRIX (end of each day = live demo at checkpoint)

| Day (IST) | A — Pipeline | B — Surfaces | C — Infra/MCP/Seed | D — Demo |
|---|---|---|---|---|
| **Jul 2** | Repo + drizzle schema up on Neon | Bolt scaffold (`slack create agent` or manual), Socket Mode hello, app manifest with all scopes/events | Sandbox provisioned; **request AI-Search-enabled sandbox in hackathon channel NOW**; Railway project; envs | Devpost registration; story bible outline; watch 3 past winning videos |
| Jul 3 | `canon.ts` (create/ratify/getWithLineage); Extractor v1 (thread→object) | ⚖️ reaction + `/precedent log` listeners; Ratify card; decision card | Deploy pipeline (HTTP mode) works end-to-end in cloud | Write 12 decision arcs + 6 landmines (docs/WORLD.md) |
| Jul 4 | Gatekeeper on message events (bot/subtype filtering, enrolled channels only); label logging | App Home v1 (enroll toggle, counts); wire `decision.pending`→card | Seed script v1: personas, channels, poster w/ customize, permalink collection | Landmine copy finalized with A (must be zero-keyword-overlap vs rulings) |
| **Jul 5** | **Sentinel**: embed→top-k→judgment; threshold v1; eval set v1 (30 cases) running | **Ephemeral drift card** + I'm aligned / Supersede modal → lineage | Seed run #1 into staging channels; direct-insert 12 rulings w/ narrative dates | Script scene 1–2 storyboard; test the wow live |
| Jul 6 | Tune threshold to 0 false-fires on eval + seeded world | Archivist: Assistant middleware, streaming/updates, suggested prompts, status; RTS client w/ action_token | MCP server skeleton + `search_decisions`/`get_decision` live | Scene 3 storyboard; App Home copy pass |
| Jul 7 | Archaeology-lite (`/precedent backfill`, ≤5 RTS calls, proposes rulings) | Canvas Register create+sync; digest post | `check_conflict` + `propose_decision` (→ Ratify card round-trip) | Dry-run demo #1, note every rough edge |
| **Jul 8** | Bugfix from dry-run; log/telemetry pass | Polish all Block Kit in Block Kit Builder; empty states; error copy | Claude Desktop wired; record MCP segment safety take; (2h timebox: Slackbot MCP client — drop if flaky) | Fresh-account QA #1; JUDGE_ACCESS.md draft |
| Jul 9 | Hardening: retries, idempotent actions, RTS Retry-After path | Final UX pass; onboarding DM on member_joined | **Seed run FINAL into the judge workspace → freeze world**; uptime monitor | Fresh-account QA #2; architecture diagram final |
| **Jul 10** | Support video (live drift takes ×10 — must fire 10/10) | Support video | Support video; verify judge invites work | **VIDEO DAY**: shoot + edit + captions + upload |
| Jul 11 | Code freeze 12:00 IST. Fix only P0s from mock-judging |〃 | 〃 | **Mock-judge**: 3 outsiders, 5 min each, real rubric; Devpost text final |
| **Jul 12** | — | — | Final smoke from fresh account; invites re-verified | **SUBMIT by 23:59 IST.** Nobody touches code after. |
| Jul 13–Aug 6 | on-call rotation: daily 5-min uptime + drift-card check | | keep Neon/Railway paid & alive | monitor Devpost comments/questions |

**Fallback triggers (Dictator calls these, no debate):** behind by Jul 6 EOD → cut F7 archaeology + digest. Behind by Jul 8 EOD → cut App Home to a static dashboard and demo Archivist canon-only (RTS still shown in backfill). The drift card (F3) and MCP loop (F6) are never cut — they are the submission.

---

## 6. DEMO WORLD BIBLE — "Lumina Labs" (Person D owns; A/C consume)

Fictional 40-person B2B SaaS (dev-tools analytics). Channels: #general #announcements #eng-platform #eng-product #architecture #product #growth #pricing #design #decisions. ~35 named personas with consistent voices (Priya — staff eng, decisive; Marco — growth PM, moves fast; Devon — CFO-brained ops; Sana — design lead; etc.). Story spans a narrative "Apr 1 – Jun 28" (see timestamp note in Build Prompt §Gotchas — narrative dates live in message text + DB fields, not Slack ts).

**The 12 canon rulings (seed-inserted, status=ratified, with evidence permalinks):** PRE-003 pricing page owns all discount copy · PRE-006 MySQL default (superseded) · **PRE-011 no new discount tiers until Q4 pricing review** · PRE-012 all customer-facing errors go through copy review · PRE-013 feature flags required for any backend change touching billing · **PRE-014 Postgres for all new services (supersedes PRE-006; dissent: Devon preferred managed Mongo)** · PRE-015 design tokens only, no raw hex in components · PRE-016 no meetings Wednesdays · PRE-017 EU data residency for analytics pipeline · PRE-018 changelog entry required per release · PRE-020 support SLA first-response 4h · PRE-021 all A/B tests registered in #growth before launch.

**The 6 drift landmines (messages a judge can type; each must fire the card):**
L1 *"for the notifications service let's just spin up MongoDB, faster for this shape of data"* → PRE-014 (the video's wow; zero keyword overlap).
L2 *"I'll add a 15% off banner for students on the landing page this week"* → PRE-011 + PRE-003.
L3 *"pushing the billing retry fix straight to prod tonight, it's tiny"* → PRE-013.
L4 *"let's book a design sync Wednesday 3pm"* → PRE-016 (the funny one — humanizes the demo).
L5 *"we can just pipe EU events into the US cluster for now"* → PRE-017 (the scary/compliance one).
L6 *"launching the onboarding A/B today, will post results Friday"* → PRE-021.
Each landmine's exact text goes in JUDGE_ACCESS.md under "Try it yourself."

---

## 7. THE 3-MINUTE VIDEO (locked script — deviations need Dictator sign-off)

0:00–0:18 **Pain cold-open.** Slack search on screen. VO: "Six months ago, this team spent three weeks deciding their database standard. Watch someone undo it in one message." Cut: teammate types L1, sends.
0:18–0:40 **The wow.** Ephemeral ⚖️ card appears. VO: "Precedent read the *meaning* — zero shared keywords — recalled the ruling, and intervened privately, before the drift shipped. Not search. Institutional memory with an immune system."
0:40–1:05 **Case law.** View ruling → decision card: rationale, alternatives rejected, **dissent recorded**, permalinks, lineage PRE-006→PRE-014. Flash Canvas Register. VO: "Who, why, what was rejected, who disagreed — cited to the exact messages."
1:05–1:35 **Capture + Archivist.** Organic thread → Ratify card → one click → PRE-022 enters canon, Canvas updates. Split-view: "Why don't we discount annual plans?" → streamed cited answer, status line "consulting the case law…". VO: "Capture is autonomous; *canon* is human-ratified. Grounded by Slack's Real-Time Search API, always cited."
1:35–2:20 **Headline: AI governance.** Claude Desktop + Precedent MCP. "Draft a plan to launch a student discount." → `check_conflict` → PRE-011 surfaced → plan adjusts → `propose_decision` → **Ratify card appears in Slack**. VO: "You're deploying fleets of agents. Slack orchestrates them. Precedent is the constitution they all obey — humans hold ratification."
2:20–2:45 **Depth flash.** Architecture diagram · App Home · backfill proposing rulings · **eval suite green** · caption: "hot path = local vectors; RTS ≤3 calls/inquiry."
2:45–3:00 **Close.** Logo. "Precedent — institutional memory, enforced. RTS + Slack AI surfaces + MCP. Try the drift card yourself in the judge sandbox."
Production: real screen recording, human VO, captions on, no copyrighted music, every scene pre-blocked, drift takes recorded until 10/10 confidence.

---

## 8. SUBMISSION KIT

**Devpost text skeleton (Person D fills):** ① Hook = the L1 story in 3 sentences. ② What it does = 3 pillars. ③ "Try it yourself" = landmine instructions. ④ How we built it = architecture + rate-limit design sentence + eval suite. ⑤ Required-tech table (§1). ⑥ Honest comparison table incl. Decision Tracker (own the incumbent — the rubric asks "does the concept exist; how much does it improve?"). ⑦ Challenges (semantic thresholding, action_token flow, seeding a believable world). ⑧ What's next (roadmap: Jira/GitHub links, expiry reviews, org-ready).

**JUDGE_ACCESS.md template:** sandbox invite link + what judge accounts can do · 60-second tour (open #eng-platform → type L1 → watch the card → click View ruling → open the Canvas → open split-view and ask "Why do we use Postgres?") · MCP quickstart (Claude Desktop config JSON + the student-discount prompt) · all 6 landmines · contact handle for issues during judging.

**Checklist before submit:** ☐ track = New Slack Agent ☐ video <3:00, public ☐ architecture PNG ☐ sandbox URL ☐ both judge emails invited & verified from a fresh account ☐ repo public w/ README + tests ☐ JUDGE_ACCESS.md linked ☐ text uses required-tech + comparison tables ☐ everything English ☐ infra on paid tier through Aug 6.

**Quality gates (all six pass or we're not done):** 20-second problem test · judge-triggered wow ≤60s and 10/10 reliable · "feels like a product" (onboarding, empty states, tests visible) · rubric explicitly answered incl. named incumbent · mock-judge ≥8.5/10 per criterion · zero-friction fresh-account run.

---

## 9. RISK REGISTER

| Risk | Likelihood | Mitigation |
|---|---|---|
| AI-Search sandbox not granted → RTS semantic mode off | Med | Ask **today** in hackathon channel; fallback: keyword RTS still satisfies requirement + demo phrasing includes keywords; drift never depended on RTS |
| Sentinel false-fires in front of a judge | Med | Threshold tuned on eval + frozen world; landmines rehearsed 10/10; confidence shown on card |
| Slack API surprises (action_token expiry, event filtering, canvas quirks) | Med | Gotchas pre-listed in Build Prompt; B reads them before coding each surface |
| Anthropic/LLM latency in live judge test | Low-Med | Haiku gate keeps hot path fast; Sentinel target <4s p95; card copy says "Precedent is thinking…" never blocks channel |
| Scope creep on day 7 | High | §2 freeze + Dictator; the word is "roadmap" |
| Devpost/video form gremlins on deadline day | Med | Submit Jul 12; Jul 13 untouched buffer |
| Sandbox breaks during Jul 14–Aug 6 judging | Med | Paid infra, daily 5-min on-call check, alerting on / endpoint |

---

## 10. OPERATING RULES

One Dictator. Standup 15 min, checkpoint demo nightly. Trunk-based: short branches, PR <300 lines, A reviews pipeline PRs, B reviews surface PRs, C reviews infra, D reviews copy. Conventional commits. `main` deploys to staging on merge; judge workspace only touched by C. Secrets never in git. All prompt text lives in `/prompts/*.md` (versioned — judges reading the repo should see the craft). Every feature lands with its demo line in DEMO_SCRIPT.md or it isn't a feature. After Jul 12: read-only.

**Companion file:** `PRECEDENT_BUILD_PROMPT.md` — paste it into Claude Code / Cursor as the project brief and build phase-by-phase. This playbook tells the team *what and when*; that file tells the machines *exactly how*.
