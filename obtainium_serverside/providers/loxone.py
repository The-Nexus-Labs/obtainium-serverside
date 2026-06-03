from __future__ import annotations

import base64
import json
import re
from html import unescape
from html.parser import HTMLParser
from typing import Any

from obtainium_serverside.http import HttpClient
from obtainium_serverside.models import AppDefinition, ResolvedRelease

from .base import BaseProvider

HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
VERSION_RE = re.compile(r"Loxone App\s+(.+?)\s+for Android(?:\s+-.*)?$", re.IGNORECASE)
STRUCTURED_DOWNLOAD_CLASS = "loxone-software-download-root"


class _StructuredConfigParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.payloads: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "div":
            return

        attr_map = dict(attrs)
        class_name = attr_map.get("class") or ""
        if STRUCTURED_DOWNLOAD_CLASS not in class_name.split():
            return

        payload = attr_map.get("data-config")
        if payload:
            self.payloads.append(payload)


class _SectionParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.sections: list[dict[str, object]] = []
        self._current_heading: str | None = None
        self._current_links: list[dict[str, str]] = []
        self._heading_parts: list[str] = []
        self._link_parts: list[str] = []
        self._link_href: str | None = None
        self._inside_heading = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in HEADING_TAGS:
            self._flush_section()
            self._heading_parts = []
            self._inside_heading = True
            return
        if tag == "a":
            self._link_parts = []
            self._link_href = dict(attrs).get("href")

    def handle_data(self, data: str) -> None:
        if self._inside_heading:
            self._heading_parts.append(data)
        if self._link_href is not None:
            self._link_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in HEADING_TAGS:
            heading = " ".join(part.strip() for part in self._heading_parts if part.strip()).strip()
            self._current_heading = heading or self._current_heading
            self._heading_parts = []
            self._inside_heading = False
            return
        if tag == "a" and self._link_href is not None:
            text = " ".join(part.strip() for part in self._link_parts if part.strip()).strip()
            if text and self._link_href:
                self._current_links.append({"text": text, "href": self._link_href})
            self._link_parts = []
            self._link_href = None

    def close(self) -> None:
        super().close()
        self._flush_section()

    def _flush_section(self) -> None:
        if self._current_heading:
            self.sections.append(
                {"heading": self._current_heading, "links": list(self._current_links)}
            )
        self._current_heading = None
        self._current_links = []


class LoxoneProvider(BaseProvider):
    def resolve_latest_release(
        self, app_definition: AppDefinition, http_client: HttpClient
    ) -> ResolvedRelease:
        channel = str(app_definition.provider_config.get("channel", "release")).strip().lower()
        html = http_client.get_text(app_definition.source_url)

        structured_release = self._resolve_from_structured_downloads(html, channel=channel)
        if structured_release is not None:
            return structured_release

        release = self._resolve_from_sections(html, channel=channel)
        if release is not None:
            return release

        raise ValueError(
            f"could not find a Loxone Android {channel} APK on {app_definition.source_url}"
        )

    def resolve_pinned_release(
        self, app_definition: AppDefinition, http_client: HttpClient, version: str
    ) -> ResolvedRelease:
        channel = str(app_definition.provider_config.get("channel", "release")).strip().lower()
        html = http_client.get_text(app_definition.source_url)
        target = version.strip()

        structured_release = self._resolve_from_structured_downloads(
            html, channel=channel, pinned_version=target
        )
        if structured_release is not None:
            return structured_release

        release = self._resolve_from_sections(html, channel=channel, pinned_version=target)
        if release is not None:
            return release

        raise ValueError(
            f"app {app_definition.app_id} pinned Loxone {channel} version {target} is not "
            f"offered on {app_definition.source_url}"
        )

    def _resolve_from_structured_downloads(
        self, html: str, *, channel: str, pinned_version: str | None = None
    ) -> ResolvedRelease | None:
        parser = _StructuredConfigParser()
        parser.feed(html)
        parser.close()

        structured_configs = self._decode_structured_configs(parser.payloads)
        preferred_configs = [config for config in structured_configs if not config.get("archived")]
        fallback_configs = [config for config in structured_configs if config.get("archived")]

        for config in [*preferred_configs, *fallback_configs]:
            if str(config.get("application", "")).strip().lower() != "app":
                continue
            if str(config.get("type", "")).strip().lower() != channel:
                continue

            version = str(config.get("version", "")).strip()
            if not version:
                continue
            if pinned_version is not None and not self._version_matches(version, pinned_version):
                continue

            download_url = self._find_android_apk_url(config.get("allVersions"))
            if download_url is None:
                continue

            title = str(config.get("title", "")).strip() or "Loxone App"
            release_name = title if version in title else f"{title} {version}".strip()
            return ResolvedRelease(
                version=version,
                download_url=download_url,
                release_name=release_name,
                file_extension=".apk",
            )

        return None

    def _resolve_from_sections(
        self, html: str, *, channel: str, pinned_version: str | None = None
    ) -> ResolvedRelease | None:
        parser = _SectionParser()
        parser.feed(html)
        parser.close()

        for section in parser.sections:
            heading = str(section.get("heading", "")).strip()
            if not self._heading_matches_channel(heading, channel=channel):
                continue

            version_match = VERSION_RE.search(heading)
            if version_match is None:
                continue

            version = version_match.group(1).strip()
            if pinned_version is not None and not self._version_matches(version, pinned_version):
                continue

            links = section.get("links")
            if not isinstance(links, list):
                continue

            for link in links:
                if not isinstance(link, dict):
                    continue
                text = str(link.get("text", "")).strip().lower()
                href = str(link.get("href", "")).strip()
                if text == "download" and href.lower().endswith(".apk"):
                    return ResolvedRelease(
                        version=version,
                        download_url=href,
                        release_name=heading,
                        file_extension=".apk",
                    )

        return None

    @staticmethod
    def _version_matches(offered_version: str, pinned_version: str) -> bool:
        offered = offered_version.strip()
        pinned = pinned_version.strip()
        if offered == pinned:
            return True
        # Loxone often suffixes a build code, e.g. "17.1.0 (16241)"; match the leading
        # version against the pin so a pin of "17.1.0" resolves that release.
        offered_lead = offered.split("(", 1)[0].strip()
        return bool(offered_lead) and offered_lead == pinned

    @staticmethod
    def _decode_structured_configs(payloads: list[str]) -> list[dict[str, Any]]:
        configs: list[dict[str, Any]] = []
        for payload in payloads:
            try:
                decoded = base64.b64decode(unescape(payload)).decode("utf-8")
                parsed = json.loads(decoded)
            except (ValueError, json.JSONDecodeError):
                continue

            if not isinstance(parsed, dict):
                continue

            config = parsed.get("config")
            if isinstance(config, dict):
                configs.append(config)

        return configs

    @staticmethod
    def _find_android_apk_url(all_versions: object) -> str | None:
        if not isinstance(all_versions, list):
            return None

        for version_group in all_versions:
            if not isinstance(version_group, dict):
                continue

            groups = version_group.get("groups")
            if not isinstance(groups, list):
                continue

            for group in groups:
                if not isinstance(group, dict):
                    continue
                if str(group.get("platform", "")).strip().lower() != "android":
                    continue

                downloads = group.get("downloads")
                if not isinstance(downloads, list):
                    continue

                for download in downloads:
                    if not isinstance(download, dict):
                        continue
                    url = str(download.get("url", "")).strip()
                    if url.lower().endswith(".apk"):
                        return url

        return None

    @staticmethod
    def _heading_matches_channel(heading: str, *, channel: str) -> bool:
        normalized = heading.lower()
        if "loxone app" not in normalized or "for android" not in normalized:
            return False
        if "playstore" in normalized:
            return False
        if channel == "beta":
            return "public beta" in normalized
        return "public beta" not in normalized
