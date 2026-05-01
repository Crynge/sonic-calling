from __future__ import annotations

import os

from pydantic import BaseModel


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


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
    openai_realtime_ws_base: str = os.getenv("OPENAI_REALTIME_WS_BASE", "wss://api.openai.com/v1/realtime")
    openai_realtime_rest_base: str = os.getenv("OPENAI_REALTIME_REST_BASE", "https://api.openai.com/v1/realtime")
    openai_voice: str = os.getenv("OPENAI_REALTIME_VOICE", "marin")
    openai_input_audio_format: str = os.getenv("OPENAI_INPUT_AUDIO_FORMAT", "g711_ulaw")
    openai_output_audio_format: str = os.getenv("OPENAI_OUTPUT_AUDIO_FORMAT", "g711_ulaw")
    openai_input_sample_rate: int = int(os.getenv("OPENAI_INPUT_SAMPLE_RATE", "8000"))
    openai_output_speed: float = float(os.getenv("OPENAI_OUTPUT_SPEED", "1.0"))
    openai_max_output_tokens: int = int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "700"))
    openai_transcription_model: str = os.getenv("OPENAI_TRANSCRIPTION_MODEL", "gpt-4o-mini-transcribe")
    openai_transcription_language: str = os.getenv("OPENAI_TRANSCRIPTION_LANGUAGE", "en")
    openai_input_noise_reduction: str = os.getenv("OPENAI_INPUT_NOISE_REDUCTION", "near_field")
    openai_turn_detection_mode: str = os.getenv("OPENAI_TURN_DETECTION_MODE", "server_vad")
    openai_turn_create_response: bool = _env_bool("OPENAI_TURN_CREATE_RESPONSE", True)
    openai_turn_interrupt_response: bool = _env_bool("OPENAI_TURN_INTERRUPT_RESPONSE", True)
    openai_idle_timeout_ms: int = int(os.getenv("OPENAI_IDLE_TIMEOUT_MS", "8000"))
    openai_vad_prefix_padding_ms: int = int(os.getenv("OPENAI_VAD_PREFIX_PADDING_MS", "300"))
    openai_vad_silence_duration_ms: int = int(os.getenv("OPENAI_VAD_SILENCE_DURATION_MS", "500"))
    openai_vad_threshold: float = float(os.getenv("OPENAI_VAD_THRESHOLD", "0.5"))
    openai_semantic_eagerness: str = os.getenv("OPENAI_SEMANTIC_EAGERNESS", "medium")
    openai_tracing_mode: str = os.getenv("OPENAI_TRACING_MODE", "auto")

    twilio_account_sid: str | None = os.getenv("TWILIO_ACCOUNT_SID")
    twilio_auth_token: str | None = os.getenv("TWILIO_AUTH_TOKEN")
    twilio_from_number: str | None = os.getenv("TWILIO_FROM_NUMBER")
    twilio_say_voice: str = os.getenv("TWILIO_SAY_VOICE", "Polly.Joanna")

    quiet_hours_start: int = int(os.getenv("QUIET_HOURS_START", "9"))
    quiet_hours_end: int = int(os.getenv("QUIET_HOURS_END", "20"))


settings = Settings()
