# Lumina Labs — demo world bible

Fictional ~40-person B2B SaaS (dev-tools analytics). Narrative spans **Apr 1 – Jun 28, 2026**.
Slack can't backdate messages (Gotcha G3), so narrative dates live *inside message text* and in
each ruling's `decided_at` DB field — the drift card cites the DB date.

## Channels
`#all-lumina-labs` (general) · `#eng-platform` · `#pricing` · `#growth` · `#decisions`
(Ratify cards from backfill/MCP land in #decisions.)

## Personas (posted via chat.postMessage username+icon_emoji customize; bot-authored → G4 filters skip them)
| Persona | Role | Voice | Icon |
|---|---|---|---|
| Priya Sharma | Staff Engineer | decisive, closes debates | 👩‍💻 |
| Devon Okafor | Ops lead (CFO-brained) | margins, risk, compliance | 📊 |
| Marco Reyes | Growth PM | moves fast, experiments | 🚀 |
| Sana Kim | Design Lead | craft, systems | 🎨 |
| Ling Chen | Backend Engineer | pragmatic | 🛠️ |
| Tomas Novak | Data Engineer | pipelines, correctness | 📈 |
| Aisha Bello | Support Lead | customer voice | 🎧 |

## Story arcs → rulings (each arc's key messages become the ruling's evidence permalinks)
| Arc | Channel | Ruling(s) | Beat |
|---|---|---|---|
| Database standard | #eng-platform | PRE-006 → **PRE-014** | MySQL creaks → debate → "all new services use Postgres", Devon's managed-Mongo dissent recorded |
| Billing incident | #eng-platform | PRE-013 | postmortem → feature flags mandatory for billing changes |
| EU residency | #eng-platform | PRE-017 | legal flags co-mingled EU events → Frankfurt-only ruling |
| Discount copy chaos | #pricing | PRE-003 | three conflicting blurbs → pricing page owns all discount copy |
| Edu discount pitch | #pricing | PRE-011 | Marco pitches 20% edu discount → frozen until Q4 pricing review |
| Colliding experiments | #growth | PRE-021 | contaminated control group → register A/B tests in #growth first |
| Meeting overload | #all-lumina-labs | PRE-016 | 7-meetings-day rant → no-meetings Wednesdays |
| Single-message rulings | various | PRE-012, PRE-015, PRE-018, PRE-020 | one decisive message each, for evidence coverage |

## The 6 drift landmines (type as a human in any observed channel)
L1 `for the notifications service let's just spin up MongoDB, faster for this shape of data` → PRE-014
L2 `I'll add a 15% off banner for students on the landing page this week` → PRE-011
L3 `pushing the billing retry fix straight to prod tonight, it's tiny` → PRE-013
L4 `let's book a design sync Wednesday 3pm` → PRE-016
L5 `we can just pipe EU events into the US cluster for now` → PRE-017
L6 `launching the onboarding A/B today, will post results Friday` → PRE-021

## Scale note (honest)
The original plan called for ~1,200 ambient messages. We seed **quality over volume**: every ruling
has a believable arc behind its evidence links; judges who click through land in a real conversation.
Re-running the seed posts duplicates (Slack messages can't be deleted by re-runs) — it's guarded by a
one-shot meta flag; use `--force` only into a fresh channel set.
