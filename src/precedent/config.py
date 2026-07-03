"""Central settings, loaded from environment / .env (never hardcode secrets)."""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # protected_namespaces=() lets us use MODEL_* fields without pydantic's `model_` warning.
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", protected_namespaces=()
    )

    # Slack
    slack_bot_token: str = ""
    slack_app_token: str = ""
    slack_signing_secret: str = ""

    # LLM provider (groq | anthropic | gemini). model_* are provider-specific IDs.
    llm_provider: str = "groq"
    anthropic_api_key: str = ""
    groq_api_key: str = ""
    gemini_api_key: str = ""
    model_gate: str = "llama-3.1-8b-instant"       # fast classifier (Gatekeeper)
    model_reason: str = "llama-3.3-70b-versatile"  # reasoning (Extractor/Sentinel/Archivist)

    # Embeddings (voyage-3=1024 dim, or openai text-embedding-3-small=1536 dim)
    voyage_api_key: str = ""
    openai_api_key: str = ""
    embed_model: str = "voyage-3"
    embed_dim: int = 1024

    # Database
    database_url: str = ""

    # MCP
    mcp_bearer_token: str = ""
    mcp_port: int = 8000
    decisions_channel: str = ""  # channel id where propose_decision posts Ratify cards

    # Runtime
    port: int = 3000
    mode: str = "socket"  # socket | http
    drift_threshold: float = 0.78
    seed_mode: int = 0
    team_id: str = "lumina-labs"

    def require(self, *names: str) -> None:
        """Fail loudly if a required secret is missing — no silent empty-string calls."""
        missing = [n for n in names if not getattr(self, n, "")]
        if missing:
            raise RuntimeError(
                f"Missing required settings: {', '.join(missing)}. "
                "Populate them in your .env (see .env.example)."
            )


settings = Settings()
