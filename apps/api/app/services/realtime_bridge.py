from __future__ import annotations

import json
from typing import Any

from ..config import settings


class TwilioRealtimeBridge:
    def build_stream_url(self, session_id: str) -> str:
        base = settings.public_websocket_base.rstrip("/")
        if base.startswith("http://"):
            base = "ws://" + base.removeprefix("http://")
        elif base.startswith("https://"):
            base = "wss://" + base.removeprefix("https://")
        return f"{base}/twilio/media-stream/{session_id}"

    def normalize_twilio_message(self, raw_message: str) -> dict[str, Any]:
        payload = json.loads(raw_message)
        event = payload.get("event", "unknown")
        return {
            "event": event,
            "streamSid": payload.get("streamSid"),
            "sequenceNumber": payload.get("sequenceNumber"),
            "media": payload.get("media"),
        }

    def build_openai_runtime_notes(self) -> dict[str, str]:
        return {
            "provider": "openai",
            "model": settings.openai_realtime_model,
            "voice": settings.openai_voice,
            "bridge_mode": "twilio-media-stream-to-openai-realtime",
        }
