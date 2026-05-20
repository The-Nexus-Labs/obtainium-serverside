from __future__ import annotations

import re
from html.parser import HTMLParser
from urllib.parse import urljoin

from obtainium_serverside.http import HttpClient
from obtainium_serverside.models import AppDefinition, ResolvedRelease

from .base import BaseProvider

VERSION_LINE_RE = re.compile(
    r"(?:^|\s)Version\s+(?P<version>[^()]+?)\s+\((?P<version_code>\d+)\)\s+(?:suggested\s+)?(?:-\s+)?Added on\s+"
)


class _FDroidVersionsParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.version_entries: list[dict[str, str]] = []
        self._current_href: str | None = None
        self._current_link_parts: list[str] = []
        self._text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        self._current_href = dict(attrs).get("href")
        self._current_link_parts = []

    def handle_data(self, data: str) -> None:
        if self._current_href is not None:
            self._current_link_parts.append(data)
        self._text_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or self._current_href is None:
            return

        link_text = " ".join(part.strip() for part in self._current_link_parts if part.strip()).strip()
        href = self._current_href.strip()
        text_snapshot = " ".join(part.strip() for part in self._text_parts if part.strip())
        version_match = VERSION_LINE_RE.search(text_snapshot)
        if (
            version_match is not None
            and link_text.lower().startswith("download apk")
            and href.lower().endswith(".apk")
        ):
            self.version_entries.append(
                {
                    "version": version_match.group("version").strip(),
                    "version_code": version_match.group("version_code").strip(),
                    "download_url": href,
                }
            )

        self._current_href = None
        self._current_link_parts = []


class FDroidProvider(BaseProvider):
    def resolve_latest_release(
        self, app_definition: AppDefinition, http_client: HttpClient
    ) -> ResolvedRelease:
        html = http_client.get_text(app_definition.source_url)
        parser = _FDroidVersionsParser()
        parser.feed(html)
        parser.close()

        if not parser.version_entries:
            raise ValueError(
                f"could not find an F-Droid APK release on {app_definition.source_url}"
            )

        latest_entry = parser.version_entries[0]
        version = latest_entry["version"]
        version_code = latest_entry["version_code"]

        return ResolvedRelease(
            version=version,
            download_url=urljoin(app_definition.source_url, latest_entry["download_url"]),
            release_name=f"Version {version} ({version_code})",
            file_extension=".apk",
        )