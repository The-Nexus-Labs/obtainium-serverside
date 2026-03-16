from __future__ import annotations

import re
from html.parser import HTMLParser

from obtainium_serverside.http import HttpClient
from obtainium_serverside.models import AppDefinition, ResolvedRelease

from .base import BaseProvider

HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
VERSION_RE = re.compile(r"Loxone App\s+(.+?)\s+for Android(?:\s+-.*)?$", re.IGNORECASE)


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
                        version=version_match.group(1).strip(),
                        download_url=href,
                        release_name=heading,
                        file_extension=".apk",
                    )

        raise ValueError(
            f"could not find a Loxone Android {channel} APK on {app_definition.source_url}"
        )

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
