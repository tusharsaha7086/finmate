"""
Application settings loaded from environment variables / .env file.

Uses pydantic-settings to validate and type-cast all config values.
Any variable defined here can be overridden by setting the corresponding
upper-case environment variable (e.g. DATABASE_URL, GOOGLE_API_KEY, …).
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # PostgreSQL connection string (used by both SQLModel and Agno session store)
    database_url: str = "postgresql://user:password@localhost:5432/finmate"

    # Google Gemini (kept for easy model switching)
    google_api_key: str = ""
    gemini_model_id: str = "gemini-2.0-flash"

    # OpenAI / OpenAI-compatible proxy
    openai_api_key: str = "sk-placeholder"
    openai_model_id: str = "gpt-4o"
    openai_base_url: str = "https://ai-proxy.synehq.com/v1"

    # Twilio credentials (used for webhook signature validation if enabled)
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = "+14155238886"  # WhatsApp sandbox default


settings = Settings()
