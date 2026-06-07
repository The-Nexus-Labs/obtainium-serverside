from __future__ import annotations

import re
from dataclasses import replace

from obtainium_serverside.http import HttpClient
from obtainium_serverside.models import AppDefinition, ResolvedRelease

from .base import BaseProvider
from .http import HTTPProvider


class LoxoneProvider(BaseProvider):
    def __init__(self) -> None:
        self._http_provider = HTTPProvider()

    def resolve_latest_release(
        self, app_definition: AppDefinition, http_client: HttpClient
    ) -> ResolvedRelease:
        return self._resolve(app_definition, http_client)

    def resolve_pinned_release(
        self, app_definition: AppDefinition, http_client: HttpClient, version: str
    ) -> ResolvedRelease:
        return self._resolve(replace(app_definition, version=version), http_client)

    def _resolve(self, app_definition: AppDefinition, http_client: HttpClient) -> ResolvedRelease:
        try:
            return self._http_provider.resolve_release(
                self._with_structured_config(app_definition), http_client
            )
        except ValueError:
            platform = (
                str(app_definition.provider_config.get("platform", "android")).strip().lower()
            )
            if platform != "android":
                raise
            return self._http_provider.resolve_release(
                self._with_legacy_section_config(app_definition), http_client
            )

    @staticmethod
    def _with_structured_config(app_definition: AppDefinition) -> AppDefinition:
        channel = str(app_definition.provider_config.get("channel", "release")).strip().lower()
        platform = str(app_definition.provider_config.get("platform", "android")).strip().lower()
        file_extension = _normalized_extension(
            str(app_definition.provider_config.get("file_extension", ".apk"))
        )
        platform_segment = "Android" if platform == "android" else platform.split("_", 1)[0]
        channel_segment = "Beta" if channel == "beta" else "Release"
        download_url_regex = (
            r"https://updatefiles\.loxone\.com/"
            rf"{re.escape(platform_segment)}/{channel_segment}/.*{re.escape(file_extension)}$"
        )

        return replace(
            app_definition,
            provider_config={
                **app_definition.provider_config,
                "extractor": "html_json_attribute",
                "html_class": "loxone-software-download-root",
                "html_attr": "data-config",
                "html_attr_encoding": "base64",
                "entries_path": "config",
                "filters": {"application": "app", "type": channel},
                "prefer_false_path": "archived",
                "version_path": "version",
                "version_match_strategy": "strip_trailing_parenthetical",
                "download_url_path": "allVersions.groups.downloads.url",
                "download_url_regex": download_url_regex,
                "release_name_path": "title",
                "append_version_to_release_name": True,
                "file_extension": file_extension,
            },
        )

    @staticmethod
    def _with_legacy_section_config(app_definition: AppDefinition) -> AppDefinition:
        channel = str(app_definition.provider_config.get("channel", "release")).strip().lower()
        channel_segment = "Beta" if channel == "beta" else "Release"
        heading_pattern = r"Loxone App\s+.+?\s+for Android"
        if channel == "beta":
            heading_pattern = r"Loxone App\s+.+?\s+Public Beta.*for Android"

        return replace(
            app_definition,
            provider_config={
                **app_definition.provider_config,
                "extractor": "html_sections",
                "filters_regex": {"heading": heading_pattern},
                "exclude_regex": {"heading": "playstore"},
                "version_path": "heading",
                "version_regex": r"Loxone App\s+(.+?)\s+for Android(?:\s+-.*)?$",
                "version_match_strategy": "strip_trailing_parenthetical",
                "download_url_path": "links.href",
                "download_url_regex": (
                    r"https://updatefiles\.loxone\.com/Android/" rf"{channel_segment}/.*\.apk$"
                ),
                "release_name_path": "heading",
                "file_extension": ".apk",
            },
        )


def _normalized_extension(raw_extension: str) -> str:
    extension = raw_extension.strip().lower()
    return extension if extension.startswith(".") else f".{extension}"
