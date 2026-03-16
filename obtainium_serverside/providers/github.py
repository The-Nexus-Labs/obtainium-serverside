from __future__ import annotations

import json
import re
from pathlib import PurePosixPath
from urllib.parse import urlparse

from obtainium_serverside.http import HttpClient
from obtainium_serverside.models import AppDefinition, ResolvedRelease

from .base import BaseProvider

DEFAULT_ASSET_REGEX = r".*\.apk$"
DEFAULT_VERSION_REGEX = r"^v?(?P<version>.+)$"
VALID_VERSION_SOURCES = {"auto", "tag_name", "name"}
CHANNEL_ALIASES = {
    "release": "stable",
    "stable": "stable",
    "beta": "prerelease",
    "prerelease": "prerelease",
    "any": "any",
}


class GitHubReleasesProvider(BaseProvider):
    def resolve_latest_release(
        self, app_definition: AppDefinition, http_client: HttpClient
    ) -> ResolvedRelease:
        repository = self._extract_repository(app_definition.source_url)
        asset_pattern = self._compile_pattern(
            app_definition,
            key="asset_regex",
            default=DEFAULT_ASSET_REGEX,
        )
        version_pattern = self._compile_pattern(
            app_definition,
            key="version_regex",
            default=DEFAULT_VERSION_REGEX,
        )
        version_source = (
            str(app_definition.provider_config.get("version_source", "auto")).strip().lower()
        )
        if version_source not in VALID_VERSION_SOURCES:
            raise ValueError(
                f"app {app_definition.app_id} has unsupported github version_source: {version_source}"
            )

        channel = self._normalize_channel(app_definition)
        api_url = f"https://api.github.com/repos/{repository}/releases?per_page=20"
        releases = json.loads(http_client.get_text(api_url))
        if not isinstance(releases, list):
            raise ValueError(f"unexpected GitHub API response for {repository}")

        for release in releases:
            if not isinstance(release, dict):
                continue
            if release.get("draft"):
                continue
            if not self._release_matches_channel(release, channel=channel):
                continue

            assets = release.get("assets")
            if not isinstance(assets, list):
                continue

            version = self._extract_version(
                app_definition,
                release,
                version_pattern=version_pattern,
                version_source=version_source,
            )

            for asset in assets:
                if not isinstance(asset, dict):
                    continue
                asset_name = str(asset.get("name", "")).strip()
                download_url = str(asset.get("browser_download_url", "")).strip()
                if not asset_name or not download_url:
                    continue
                if not asset_pattern.search(asset_name):
                    continue
                return ResolvedRelease(
                    version=version,
                    download_url=download_url,
                    release_name=str(release.get("name") or release.get("tag_name") or "").strip()
                    or None,
                    file_extension=PurePosixPath(asset_name).suffix or ".apk",
                )

        raise ValueError(
            f"could not find a matching GitHub release asset for {app_definition.app_id} in {repository}"
        )

    @staticmethod
    def _extract_repository(source_url: str) -> str:
        parsed = urlparse(source_url)
        if parsed.netloc not in {"github.com", "www.github.com"}:
            raise ValueError(f"unsupported GitHub source URL: {source_url}")

        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) < 2:
            raise ValueError(f"could not determine GitHub repository from {source_url}")
        return f"{parts[0]}/{parts[1]}"

    @staticmethod
    def _compile_pattern(
        app_definition: AppDefinition, *, key: str, default: str
    ) -> re.Pattern[str]:
        value = str(app_definition.provider_config.get(key, default)).strip()
        try:
            return re.compile(value)
        except re.error as exc:
            raise ValueError(
                f"app {app_definition.app_id} has invalid github {key}: {exc}"
            ) from exc

    @staticmethod
    def _normalize_channel(app_definition: AppDefinition) -> str:
        raw_channel = str(app_definition.provider_config.get("channel", "stable")).strip().lower()
        try:
            return CHANNEL_ALIASES[raw_channel]
        except KeyError as exc:
            raise ValueError(
                f"app {app_definition.app_id} has unsupported github channel: {raw_channel}"
            ) from exc

    @staticmethod
    def _release_matches_channel(release: dict[str, object], *, channel: str) -> bool:
        prerelease = bool(release.get("prerelease"))
        if channel == "stable":
            return not prerelease
        if channel == "prerelease":
            return prerelease
        return True

    @staticmethod
    def _extract_version(
        app_definition: AppDefinition,
        release: dict[str, object],
        *,
        version_pattern: re.Pattern[str],
        version_source: str,
    ) -> str:
        candidates: list[tuple[str, str]] = []
        if version_source == "auto":
            candidates = [
                ("tag_name", str(release.get("tag_name", "")).strip()),
                ("name", str(release.get("name", "")).strip()),
            ]
        else:
            candidates = [(version_source, str(release.get(version_source, "")).strip())]

        for _source_name, value in candidates:
            if not value:
                continue
            match = version_pattern.search(value)
            if match is None:
                continue
            extracted = match.groupdict().get("version")
            if extracted is None:
                extracted = match.group(1) if match.groups() else match.group(0)
            extracted = extracted.strip()
            if extracted:
                return extracted

        release_name = (
            str(release.get("name") or release.get("tag_name") or "").strip() or "<unknown release>"
        )
        raise ValueError(
            f"app {app_definition.app_id} could not extract a version from {release_name}"
        )
