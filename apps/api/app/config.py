from pydantic import BaseModel
import os


class Settings(BaseModel):
    platform_name: str = os.getenv("PLATFORM_NAME", "Sonic Calling")
    business_name: str = os.getenv("BUSINESS_NAME", "Sonic Calling Labs")
    disclosure_line: str = os.getenv(
        "DISCLOSURE_LINE",
        "Hi, this is the Sonic Calling AI assistant from Sonic Calling Labs on a recorded call.",
    )
    public_base_url: str = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8000")
    public_websocket_base: str = os.getenv("PUBLIC_WEBSOCKET_BASE", "ws://127.0.0.1:8000")
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    openai_realtime_model: str = os.getenv("OPENAI_REALTIME_MODEL", "gpt-realtime")
    openai_voice: str = os.getenv("OPENAI_REALTIME_VOICE", "marin")
    openai_input_sample_rate: int = int(os.getenv("OPENAI_INPUT_SAMPLE_RATE", "24000"))
    twilio_account_sid: str | None = os.getenv("TWILIO_ACCOUNT_SID")
    twilio_auth_token: str | None = os.getenv("TWILIO_AUTH_TOKEN")
    twilio_from_number: str | None = os.getenv("TWILIO_FROM_NUMBER")
    quiet_hours_start: int = int(os.getenv("QUIET_HOURS_START", "9"))
    quiet_hours_end: int = int(os.getenv("QUIET_HOURS_END", "20"))


settings = Settings()
