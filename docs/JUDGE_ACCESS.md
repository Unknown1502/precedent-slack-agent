# Precedent — Judge Access

**Precedent — institutional memory, enforced.** Capture team decisions into a cited, human-ratified
canon; defend that canon in real time against drift with private nudges; expose it over MCP so other
AI agents consult it before acting.

## Workspace
- Sandbox: **Lumina Labs** (invite link provided in the Devpost submission).
- The bot **@precedent** is installed and observing: **#all-lumina-labs, #eng-platform, #pricing,
  #growth, #decisions** (run `/precedent enroll` in any channel to add more).
- Canon is pre-seeded with **12 rulings** (PRE-003 … PRE-021), incl. lineage **PRE-006 → PRE-014** —
  and every ruling's evidence links to **real seeded conversations** (see `docs/WORLD.md`): click
  any evidence link on a decision card and you land in the actual debate, e.g. the #eng-platform
  Postgres thread where Devon's managed-Mongo dissent was recorded.
- Bonus: try `@precedent backfill` in #growth — it mines the channel's history for un-captured
  decisions and proposes Ratify cards (archaeology-lite; RTS-assisted when available).

## 60-second tour
1. Open **#all-lumina-labs** and type a landmine (below) → an ephemeral **⚖️ drift card** appears
   *only to you*, citing the conflicting ruling. Click **📖 View ruling** to see rationale,
   dissent, lineage, and sources.
2. Open the bot's **Home** tab → live dashboard (Ratified / Pending / Open drift) + the Register link.
3. Open the **⚖️ Decision Register** canvas → the full case law, grouped by scope.
4. Open the **assistant split-view** (message the app) and ask *"Why do we use Postgres for new
   services?"* → a streamed, cited answer with the PRE-006→PRE-014 lineage and Devon's dissent.
5. Capture: react **:scales:** on any decision message → a **Ratify card** → **Approve** → it enters
   canon and the Register updates.

## Try it yourself — the 6 drift landmines
Type any of these in **#all-lumina-labs** (as a human — bot messages are ignored):

| # | Message | Fires |
|---|---|---|
| L1 | `for the notifications service let's just spin up MongoDB, faster for this shape of data` | PRE-014 (zero keyword overlap) |
| L2 | `I'll add a 15% off banner for students on the landing page this week` | PRE-011 |
| L3 | `pushing the billing retry fix straight to prod tonight, it's tiny` | PRE-013 |
| L4 | `let's book a design sync Wednesday 3pm` | PRE-016 |
| L5 | `we can just pipe EU events into the US cluster for now` | PRE-017 |
| L6 | `launching the onboarding A/B today, will post results Friday` | PRE-021 |

## MCP quickstart (governance loop)
The Precedent MCP server is **live** over Streamable HTTP with 4 tools: `search_decisions`,
`get_decision`, `check_conflict`, `propose_decision`. Public URL:

    https://daring-rejoicing-production-01d2.up.railway.app/mcp

Add to Claude Desktop's `claude_desktop_config.json` (macOS/Linux — bare `npx`):
```json
{
  "mcpServers": {
    "precedent": {
      "command": "npx",
      "args": [
        "mcp-remote",
        "https://daring-rejoicing-production-01d2.up.railway.app/mcp",
        "--header",
        "Authorization: Bearer prod-mcp-fc4649b9f0b0aabe2ddb21aadd165998"
      ]
    }
  }
}
```
On **Windows**, wrap with `cmd /c` (bare `npx` fails on the "C:\Program Files\nodejs" path):
`"command": "cmd", "args": ["/c", "npx", "mcp-remote", "…/mcp", "--header", "Authorization: Bearer …"]`

Then ask Claude Desktop: *"Draft a plan to launch a student discount."* → it calls **`check_conflict`**
→ surfaces **PRE-011** → adjusts the plan → **`propose_decision`** → a **Ratify card appears in Slack**
(#all-lumina-labs) for a human to approve. Approve it, and `get_decision` reflects the ratified ruling.

Health check (no auth): `curl https://daring-rejoicing-production-01d2.up.railway.app/healthz` →
`{"status":"ok","service":"precedent-mcp"}`. Unauthenticated tool calls return **401**.

## Notes
- The drift hot path uses **local pgvector only** — never the RTS API (rate-limit safe).
- Nothing enters canon as `ratified` without a **human Approve** in Slack.
- Contact for issues during judging: _(handle in Devpost submission)_.
