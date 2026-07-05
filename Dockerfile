# Precedent — one image, two services (start command decides which):
#   Slack worker (Socket Mode):  python -m precedent.slack.app
#   MCP server (Streamable HTTP): python -m precedent.mcp.server
FROM python:3.11-slim

WORKDIR /app

# Editable install keeps src/ in place so runtime paths (prompts/, db/ddl.sql) resolve
# exactly like local dev: llm.py walks parents to /app/prompts.
COPY pyproject.toml README.md ./
COPY src ./src
COPY prompts ./prompts
COPY scripts ./scripts
RUN pip install --no-cache-dir -e .[mcp]

ENV PYTHONUNBUFFERED=1

# Default = Slack worker; the MCP service overrides the start command.
CMD ["python", "-m", "precedent.slack.app"]
