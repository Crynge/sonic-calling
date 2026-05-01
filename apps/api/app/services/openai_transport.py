from __future__ import annotations

from typing import Any

import httpx
import websockets

from ..config import settings


class OpenAIRealtimeTransport:
    @property
    def enabled(self) -> bool:
        return bool(settings.openai_api_key)

    def build_websocket_url(self) -> str:
        base = settings.openai_realtime_ws_base.rstrip("/")
        if "?" in base:
            return base
        return f"{base}?model={settings.openai_realtime_model}"

    def build_headers(self) -> dict[str, str]:
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required for live realtime transport.")
        return {
            "Authorization": f"Bearer {settings.openai_api_key}",
        }

    async def open_websocket(self):
        return await websockets.connect(
            self.build_websocket_url(),
            additional_headers=self.build_headers(),
            max_size=None,
        )

    async def create_client_secret(self, session_config: dict[str, Any]) -> dict[str, Any]:
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required for realtime client secrets.")

        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                f"{settings.openai_realtime_rest_base.rstrip('/')}/client_secrets",
                headers={
                    "Authorization": f"Bearer {settings.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json={"session": session_config["session"]},
            )
            response.raise_for_status()
            return response.json()
