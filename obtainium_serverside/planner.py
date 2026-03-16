from __future__ import annotations

import re
from pathlib import Path

from .http import HttpClient
from .models import AppDefinition, InstalledApp, PlannedUpdate, PlanningError, PlanningResult
from .providers import get_provider

NUMERIC_VERSION_RE = re.compile(r"\d+")
SAFE_FILE_CHARS_RE = re.compile(r"[^A-Za-z0-9._-]+")


def should_update(*, latest_version: str, installed_version: str | None) -> bool:
    if installed_version in (None, ""):
        return True

    assert installed_version is not None
    current_version = installed_version

    latest_parts = tuple(int(part) for part in NUMERIC_VERSION_RE.findall(latest_version))
    installed_parts = tuple(int(part) for part in NUMERIC_VERSION_RE.findall(current_version))

    if latest_parts and installed_parts and latest_parts != installed_parts:
        max_length = max(len(latest_parts), len(installed_parts))
        padded_latest = latest_parts + (0,) * (max_length - len(latest_parts))
        padded_installed = installed_parts + (0,) * (max_length - len(installed_parts))
        return padded_latest > padded_installed

    return latest_version.strip() != current_version.strip()


def build_download_path(download_dir: Path, *, app_id: str, version: str, extension: str) -> Path:
    sanitized_app_id = SAFE_FILE_CHARS_RE.sub("-", app_id).strip("-") or "app"
    sanitized_version = SAFE_FILE_CHARS_RE.sub("-", version).strip("-") or "latest"
    normalized_extension = extension if extension.startswith(".") else f".{extension}"
    return download_dir / f"{sanitized_app_id}-{sanitized_version}{normalized_extension}"


def plan_updates(
    app_definitions: list[AppDefinition],
    installed_apps: list[InstalledApp],
    *,
    download_dir: Path | None = None,
    http_client: HttpClient | None = None,
) -> PlanningResult:
    resolved_download_dir = download_dir.resolve() if download_dir is not None else None
    if resolved_download_dir is not None:
        resolved_download_dir.mkdir(parents=True, exist_ok=True)

    client = http_client or HttpClient()
    installed_by_id = {app.app_id: app for app in installed_apps}
    updates: list[PlannedUpdate] = []
    errors: list[PlanningError] = []

    for app_definition in app_definitions:
        installed_app = installed_by_id.get(app_definition.app_id)
        try:
            provider = get_provider(app_definition.provider)
            resolved_release = provider.resolve_latest_release(app_definition, client)
            if not should_update(
                latest_version=resolved_release.version,
                installed_version=installed_app.version if installed_app else None,
            ):
                continue

            downloaded_apk_path: str | None = None
            if resolved_download_dir is not None:
                destination = build_download_path(
                    resolved_download_dir,
                    app_id=app_definition.app_id,
                    version=resolved_release.version,
                    extension=resolved_release.file_extension,
                )
                client.download_file(resolved_release.download_url, destination)
                downloaded_apk_path = str(destination)

            updates.append(
                PlannedUpdate(
                    app_id=app_definition.app_id,
                    provider=app_definition.provider,
                    source_url=app_definition.source_url,
                    name=app_definition.name,
                    installed_version=installed_app.version if installed_app else None,
                    latest_version=resolved_release.version,
                    download_url=resolved_release.download_url,
                    downloaded_apk_path=downloaded_apk_path,
                    release_name=resolved_release.release_name,
                )
            )
        except Exception as exc:
            errors.append(PlanningError(app_id=app_definition.app_id, message=str(exc)))

    return PlanningResult(updates=updates, errors=errors)
