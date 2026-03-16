from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AppDefinition:
    app_id: str
    provider: str
    source_url: str
    name: str | None = None
    provider_config: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AppDefinition":
        app_id = str(payload.get("app_id", "")).strip()
        provider = str(payload.get("provider", "")).strip()
        source_url = str(payload.get("source_url", "")).strip()
        if not app_id:
            raise ValueError("app definition is missing app_id")
        if not provider:
            raise ValueError(f"app {app_id} is missing provider")
        if not source_url:
            raise ValueError(f"app {app_id} is missing source_url")
        name = payload.get("name")
        provider_config = payload.get("provider_config") or {}
        if not isinstance(provider_config, dict):
            raise ValueError(f"app {app_id} provider_config must be an object")
        return cls(
            app_id=app_id,
            provider=provider,
            source_url=source_url,
            name=str(name).strip() if name is not None else None,
            provider_config=dict(provider_config),
        )


@dataclass(frozen=True)
class InstalledApp:
    app_id: str
    version: str | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "InstalledApp":
        app_id = str(payload.get("app_id", "")).strip()
        if not app_id:
            raise ValueError("installed app entry is missing app_id")
        version = payload.get("version")
        return cls(app_id=app_id, version=None if version in (None, "") else str(version).strip())


@dataclass(frozen=True)
class ResolvedRelease:
    version: str
    download_url: str
    release_name: str | None = None
    file_extension: str = ".apk"


@dataclass(frozen=True)
class PlannedUpdate:
    app_id: str
    provider: str
    source_url: str
    latest_version: str
    installed_version: str | None
    download_url: str
    downloaded_apk_path: str | None
    name: str | None = None
    release_name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "app_id": self.app_id,
            "provider": self.provider,
            "source_url": self.source_url,
            "name": self.name,
            "installed_version": self.installed_version,
            "latest_version": self.latest_version,
            "download_url": self.download_url,
            "downloaded_apk_path": self.downloaded_apk_path,
            "release_name": self.release_name,
        }


@dataclass(frozen=True)
class PlanningError:
    app_id: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"app_id": self.app_id, "message": self.message}


@dataclass(frozen=True)
class PlanningResult:
    updates: list[PlannedUpdate]
    errors: list[PlanningError]

    def to_dict(self) -> dict[str, Any]:
        return {
            "updates": [update.to_dict() for update in self.updates],
            "errors": [error.to_dict() for error in self.errors],
        }
