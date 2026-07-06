# Deploy — Railway (app + MCP) + Neon (Postgres/pgvector)

> **STATUS: DEPLOYED (Jul 6) and verified.**
> - Slack worker: Railway service `precedent-slack-agent` (Socket Mode; drift card verified from cloud).
> - MCP server: Railway service `daring-rejoicing` →
>   `https://daring-rejoicing-production-01d2.up.railway.app` (healthz OK · no-auth 401 · 4 tools
>   verified from a real MCP client against Neon).
> - DB: Neon, full-fidelity copy of the demo canon. Railway auto-deploys on push to `main`.
>
> **Gotchas that actually bit us — check these first when something 502s/crash-loops:**
> 1. Railway **stages** variable/settings edits — nothing applies until you click the purple
>    **Apply changes / Deploy** button. "Deployment successful" can mean *build* success while the
>    app crash-loops for missing env.
> 2. Each service needs its **Custom Start Command** actually applied; otherwise it runs the image
>    default (`precedent.slack.app`) and becomes a **duplicate Slack worker** that splits events.
> 3. The MCP SDK's DNS-rebinding protection returns **421 Misdirected Request** behind a proxy
>    host — handled in `mcp/server.py` (protection off unless `MCP_ALLOWED_HOSTS` is set; bearer
>    auth remains the access control).
> 4. Never run a local `python -m precedent.slack.app` while the Railway worker is up — two Socket
>    Mode connections split events and it looks like the bot randomly ignores messages.

Target: infra stays alive through judging (Jul 14 – Aug 6). Two Railway services from one repo/image,
one Neon database. Slack side needs **no public URL** (Socket Mode); MCP needs public HTTPS.

## 0. Prereqs (accounts)
- GitHub repo (push this project; Railway deploys from it)
- https://neon.tech — free tier, has pgvector
- https://railway.app — Hobby plan (~$5/mo; keep paid through Aug 6 per playbook)

## 1. Neon
1. Create project `precedent` (region: anything US/EU).
2. Copy the connection string (`postgresql://…neon.tech/neondb?sslmode=require`).
3. That string is `DATABASE_URL` for both services and for local migrate/seed below.

## 2. Migrate + seed the production DB (run locally, pointed at Neon)
```bash
# temporarily set DATABASE_URL to the Neon URL in .env, then:
python -m precedent.db.migrate
python scripts/seed/insert_canon.py            # 12 rulings
python scripts/seed/seed_world.py --force      # only if pointing at a FRESH workspace/channels;
                                               # otherwise carry over evidence via seed-output.json
# switch .env DATABASE_URL back to local when done
```
Note: the demo evidence permalinks live in the *Lumina Labs* workspace — seeding canon into Neon
keeps them (they're stored on the rulings), no re-posting needed.

## 3. Railway
1. New Project → **Deploy from GitHub repo** → pick this repo. It detects the `Dockerfile`.
2. Service A — `precedent-slack` (worker):
   - Start command: *(default)* `python -m precedent.slack.app`
   - No public networking needed.
3. Service B — `precedent-mcp`: duplicate the service from the same repo/image,
   - Start command: `python -m precedent.mcp.server`
   - Enable **Public Networking** → note the generated `https://….up.railway.app` URL.
   - Railway injects `PORT`; set `MCP_PORT=${PORT}` (or set MCP_PORT to the same value).
4. Shared env vars (both services — Railway "Shared Variables" works):
   ```
   SLACK_BOT_TOKEN  SLACK_APP_TOKEN  SLACK_SIGNING_SECRET
   GROQ_API_KEY  VOYAGE_API_KEY
   LLM_PROVIDER=groq  EMBED_MODEL=voyage-3.5  EMBED_DIM=1024
   MODEL_GATE=llama-3.1-8b-instant  MODEL_REASON=llama-3.3-70b-versatile
   DATABASE_URL=<neon url>
   MCP_BEARER_TOKEN=<fresh random secret — do NOT reuse the dev one>
   DECISIONS_CHANNEL=<#decisions channel id>
   TEAM_ID=lumina-labs  DRIFT_THRESHOLD=0.78  SEED_MODE=0
   ```
5. Smoke: `curl https://<mcp-url>/healthz` → `{"status":"ok"}`; unauthenticated `/mcp` POST → 401.

## 4. Point judges' Claude Desktop at prod
`claude_desktop_config.json` (Windows needs the `cmd /c` wrapper — bare `npx` breaks on
"C:\Program Files" path splitting):
```json
{
  "mcpServers": {
    "precedent": {
      "command": "cmd",
      "args": ["/c", "npx", "mcp-remote", "https://<mcp-url>/mcp",
               "--header", "Authorization: Bearer <MCP_BEARER_TOKEN>"]
    }
  }
}
```
(macOS/Linux: `"command": "npx", "args": ["mcp-remote", …]`.)

## 5. Cutover checklist
- [ ] Stop the local Slack worker (two Socket Mode workers = duplicate handling).
- [ ] Local `.env` back to the Docker DB; prod runs Neon.
- [ ] Type L1 in #eng-platform → drift card fires from the *Railway* worker (check Railway logs).
- [ ] MCP round-trip from Claude Desktop against the public URL.
- [ ] Uptime monitor (e.g. UptimeRobot, free) on `https://<mcp-url>/healthz` through Aug 6.
