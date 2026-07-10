from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _merge_mappings(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge mappings, with override values taking precedence."""
    merged = dict(base)
    for key, value in override.items():
        existing = merged.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            merged[key] = _merge_mappings(existing, value)
        else:
            merged[key] = value
    return merged


@dataclass(frozen=True)
class AppDefinition:
    app_id: str
    provider: str
    source_url: str
    name: str | None = None
    provider_config: dict[str, Any] = field(default_factory=dict)
    version: str | None = None
    variant: str | None = None
    variants: dict[str, dict[str, Any]] = field(default_factory=dict)

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
        variants_payload = payload.get("variants") or {}
        if not isinstance(variants_payload, dict):
            raise ValueError(f"app {app_id} variants must be an object")
        variants: dict[str, dict[str, Any]] = {}
        for raw_name, raw_config in variants_payload.items():
            variant_name = str(raw_name).strip()
            if not variant_name:
                raise ValueError(f"app {app_id} variant names must not be empty")
            if not isinstance(raw_config, dict):
                raise ValueError(f"app {app_id} variant {variant_name} must be an object")
            variants[variant_name] = dict(raw_config)

        raw_variant = payload.get("variant")
        variant = None if raw_variant in (None, "") else str(raw_variant).strip()
        if variant and variant not in variants:
            available = ", ".join(sorted(variants)) or "none"
            raise ValueError(
                f"app {app_id} requested unknown variant {variant!r}; available variants: {available}"
            )
        if not variant and len(variants) > 1:
            available = ", ".join(sorted(variants))
            raise ValueError(
                f"app {app_id} has ambiguous artifact variants ({available}); select one with variant"
            )
        if not variant and len(variants) == 1:
            variant = next(iter(variants))

        resolved_provider_config = dict(provider_config)
        if variant:
            resolved_provider_config = _merge_mappings(resolved_provider_config, variants[variant])
        version = payload.get("version")
        return cls(
            app_id=app_id,
            provider=provider,
            source_url=source_url,
            name=str(name).strip() if name is not None else None,
            provider_config=resolved_provider_config,
            version=None if version in (None, "") else str(version).strip() or None,
            variant=variant,
            variants=variants,
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
    download_url: str | None = None
    release_name: str | None = None
    file_extension: str = ".apk"


@dataclass(frozen=True)
class PlannedUpdate:
    app_id: str
    provider: str
    source_url: str
    latest_version: str
    installed_version: str | None
    download_url: str | None
    downloaded_artifact_path: str | None
    name: str | None = None
    release_name: str | None = None
    pinned: bool = False

    @property
    def downloaded_apk_path(self) -> str | None:
        """Deprecated compatibility alias for downloaded_artifact_path."""
        return self.downloaded_artifact_path

    def to_dict(self) -> dict[str, Any]:
        return {
            "app_id": self.app_id,
            "provider": self.provider,
            "source_url": self.source_url,
            "name": self.name,
            "installed_version": self.installed_version,
            "latest_version": self.latest_version,
            "download_url": self.download_url,
            "downloaded_artifact_path": self.downloaded_artifact_path,
            "downloaded_apk_path": self.downloaded_artifact_path,
            "release_name": self.release_name,
            "pinned": self.pinned,
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
