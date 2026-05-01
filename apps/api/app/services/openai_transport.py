from __future__ import annotations

from typing import Any

import httpx
import websockets

from ..config import settings


class OpenAIRealtimeTransport:
    def resolve_api_key(self, credentials: dict[str, Any] | None = None) -> str | None:
        return (credentials or {}).get("api_key") or settings.openai_api_key

    def resolve_model(self, credentials: dict[str, Any] | None = None) -> str:
        return (credentials or {}).get("model") or settings.openai_realtime_model

    def resolve_rest_base(self, credentials: dict[str, Any] | None = None) -> str:
        return (credentials or {}).get("endpoint") or settings.openai_realtime_rest_base

    def resolve_ws_base(self, credentials: dict[str, Any] | None = None) -> str:
        base = self.resolve_rest_base(credentials).rstrip("/")
        if base.endswith("/realtime"):
            return base.replace("https://", "wss://").replace("http://", "ws://")
        return settings.openai_realtime_ws_base

    @property
    def enabled(self) -> bool:
        return bool(self.resolve_api_key())

    def enabled_for(self, credentials: dict[str, Any] | None = None) -> bool:
        return bool(self.resolve_api_key(credentials))

    def build_websocket_url(self, credentials: dict[str, Any] | None = None) -> str:
        base = self.resolve_ws_base(credentials).rstrip("/")
        if "?" in base:
            return base
        return f"{base}?model={self.resolve_model(credentials)}"

    def build_headers(self, credentials: dict[str, Any] | None = None) -> dict[str, str]:
        api_key = self.resolve_api_key(credentials)
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required for live realtime transport.")
        return {
            "Authorization": f"Bearer {api_key}",
        }

    async def open_websocket(self, credentials: dict[str, Any] | None = None):
        return await websockets.connect(
            self.build_websocket_url(credentials),
            additional_headers=self.build_headers(credentials),
            max_size=None,
        )

    async def create_client_secret(
        self,
        session_config: dict[str, Any],
        credentials: dict[str, Any] | None = None,
        expires_after_seconds: int = 600,
    ) -> dict[str, Any]:
        api_key = self.resolve_api_key(credentials)
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required for realtime client secrets.")

        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                f"{self.resolve_rest_base(credentials).rstrip('/')}/client_secrets",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "expires_after": {
                        "anchor": "created_at",
                        "seconds": expires_after_seconds,
                    },
                    "session": session_config["session"],
                },
            )
            response.raise_for_status()
            return response.json()
