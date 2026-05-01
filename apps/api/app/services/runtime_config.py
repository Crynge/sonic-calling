from __future__ import annotations

import uuid
from typing import Any

from ..config import settings
from ..schemas import (
    ProviderName,
    ProviderProfile,
    ProviderProfileInput,
    ProviderSurface,
)


def _mask_secret(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}{'*' * max(4, len(value) - 8)}{value[-4:]}"


class RuntimeConfigStore:
    def __init__(self) -> None:
        self._profiles: dict[str, dict[str, Any]] = {}
        self._active_profiles: dict[ProviderSurface, str | None] = {
            ProviderSurface.REALTIME: None,
            ProviderSurface.TELEPHONY: None,
            ProviderSurface.TOOLING: None,
            ProviderSurface.ANALYTICS: None,
        }
        self._seed_defaults()

    def _seed_defaults(self) -> None:
        self._profiles["provider-openai-managed"] = {
            "profile_id": "provider-openai-managed",
            "name": "Platform OpenAI Realtime",
            "provider": ProviderName.OPENAI,
            "surface": ProviderSurface.REALTIME,
            "active": True,
            "auth_source": "environment",
            "api_key": settings.openai_api_key,
            "model": settings.openai_realtime_model,
            "endpoint": settings.openai_realtime_rest_base,
            "notes": "Default platform-managed OpenAI Realtime profile.",
            "metadata": {
                "voice": settings.openai_voice,
                "transport": "websocket + client_secret",
            },
        }
        self._profiles["provider-twilio-managed"] = {
            "profile_id": "provider-twilio-managed",
            "name": "Platform Twilio Voice",
            "provider": ProviderName.TWILIO,
            "surface": ProviderSurface.TELEPHONY,
            "active": True,
            "auth_source": "environment",
            "account_sid": settings.twilio_account_sid,
            "auth_token": settings.twilio_auth_token,
            "from_number": settings.twilio_from_number,
            "endpoint": settings.public_base_url,
            "notes": "Default platform-managed Twilio voice edge.",
            "metadata": {
                "media_streams": "bidirectional",
                "audio_format": settings.openai_input_audio_format,
            },
        }
        self._profiles["provider-gemini-tooling-demo"] = {
            "profile_id": "provider-gemini-tooling-demo",
            "name": "Gemini Sidecar Planner",
            "provider": ProviderName.GEMINI,
            "surface": ProviderSurface.TOOLING,
            "active": False,
            "auth_source": "unset",
            "api_key": None,
            "model": "gemini-2.5-flash",
            "endpoint": "https://generativelanguage.googleapis.com",
            "notes": "Optional sidecar profile for post-call summarization or lead scoring workflows.",
            "metadata": {
                "role": "post_call_reasoning",
            },
        }
        self._active_profiles[ProviderSurface.REALTIME] = "provider-openai-managed"
        self._active_profiles[ProviderSurface.TELEPHONY] = "provider-twilio-managed"
        self._active_profiles[ProviderSurface.TOOLING] = "provider-gemini-tooling-demo"

    def _readiness_for(self, raw: dict[str, Any]) -> tuple[bool, list[str]]:
        provider: ProviderName = raw["provider"]
        surface: ProviderSurface = raw["surface"]
        notes: list[str] = []
        ready = True

        if surface == ProviderSurface.REALTIME:
            if provider != ProviderName.OPENAI:
                ready = False
                notes.append("Live Twilio voice bridging currently requires an OpenAI Realtime profile.")
            if not raw.get("api_key"):
                ready = False
                notes.append("Missing API key for Realtime session creation and client-secret minting.")
        elif surface == ProviderSurface.TELEPHONY:
            if provider != ProviderName.TWILIO:
                ready = False
                notes.append("Telephony surfaces currently assume Twilio Voice credentials.")
            if not raw.get("account_sid"):
                ready = False
                notes.append("Missing Twilio account SID.")
            if not raw.get("auth_token"):
                ready = False
                notes.append("Missing Twilio auth token.")
            if not raw.get("from_number"):
                ready = False
                notes.append("Missing Twilio from number.")
        else:
            if not raw.get("api_key") and not raw.get("endpoint"):
                ready = False
                notes.append("Provide an API key or endpoint before using this integration as a sidecar provider.")

        if ready:
            notes.append("Ready for use.")
        return ready, notes

    def _build_view(self, raw: dict[str, Any]) -> ProviderProfile:
        ready, readiness_notes = self._readiness_for(raw)
        masked_secret = _mask_secret(raw.get("api_key") or raw.get("auth_token"))
        account_label = raw.get("account_sid") or raw.get("from_number")
        return ProviderProfile(
            profile_id=raw["profile_id"],
            name=raw["name"],
            provider=raw["provider"],
            surface=raw["surface"],
            active=self._active_profiles.get(raw["surface"]) == raw["profile_id"],
            ready=ready,
            auth_source=raw.get("auth_source", "unset"),
            masked_secret=masked_secret,
            account_label=account_label,
            model=raw.get("model"),
            endpoint=raw.get("endpoint"),
            notes=raw.get("notes", ""),
            readiness_notes=readiness_notes,
            metadata=raw.get("metadata", {}),
        )

    def list_provider_profiles(self) -> list[ProviderProfile]:
        return sorted(
            (self._build_view(raw) for raw in self._profiles.values()),
            key=lambda profile: (profile.surface.value, profile.name),
        )

    def get_provider_profile(self, profile_id: str) -> ProviderProfile:
        return self._build_view(self._profiles[profile_id])

    def create_provider_profile(self, request: ProviderProfileInput) -> ProviderProfile:
        profile_id = f"profile-{uuid.uuid4().hex[:10]}"
        self._profiles[profile_id] = {
            "profile_id": profile_id,
            "name": request.name,
            "provider": request.provider,
            "surface": request.surface,
            "active": False,
            "auth_source": "vault",
            "api_key": request.api_key,
            "account_sid": request.account_sid,
            "auth_token": request.auth_token,
            "from_number": request.from_number,
            "model": request.model,
            "endpoint": request.endpoint,
            "notes": request.notes,
            "metadata": request.metadata,
        }
        return self.get_provider_profile(profile_id)

    def select_active_profile(self, surface: ProviderSurface, profile_id: str) -> ProviderProfile:
        raw = self._profiles[profile_id]
        if raw["surface"] != surface:
            raise ValueError(f"Profile {profile_id} does not belong to the {surface.value} surface.")
        self._active_profiles[surface] = profile_id
        return self.get_provider_profile(profile_id)

    def get_active_profile_id(self, surface: ProviderSurface) -> str | None:
        return self._active_profiles.get(surface)

    def resolve_provider_profile(self, surface: ProviderSurface, profile_id: str | None = None) -> ProviderProfile | None:
        resolved = profile_id or self._active_profiles.get(surface)
        if not resolved:
            return None
        return self.get_provider_profile(resolved)

    def resolve_credentials(self, surface: ProviderSurface, profile_id: str | None = None) -> dict[str, Any]:
        resolved = profile_id or self._active_profiles.get(surface)
        if not resolved:
            return {}
        return dict(self._profiles[resolved])

    def get_profile_payload(self, profile_id: str) -> dict[str, Any]:
        return dict(self._profiles[profile_id])
