from __future__ import annotations

import base64
import json
import re
from html import unescape
from html.parser import HTMLParser
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urljoin

from obtainium_serverside.http import HttpClient
from obtainium_serverside.models import AppDefinition, ResolvedRelease

from .base import BaseProvider

HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
TRAILING_PARENTHETICAL_RE = re.compile(r"\s*\([^)]*\)\s*$")


class _LinkParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[dict[str, str]] = []
        self._base_url = base_url
        self._href: str | None = None
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        href = dict(attrs).get("href")
        if not href:
            return
        self._href = urljoin(self._base_url, href)
        self._parts = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or self._href is None:
            return
        text = " ".join(part.strip() for part in self._parts if part.strip()).strip()
        self.links.append({"href": self._href, "text": text})
        self._href = None
        self._parts = []


class _SectionParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.sections: list[dict[str, object]] = []
        self._base_url = base_url
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
            href = dict(attrs).get("href")
            if href:
                self._link_parts = []
                self._link_href = urljoin(self._base_url, href)

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


class _AttributePayloadParser(HTMLParser):
    def __init__(self, *, class_name: str, attr_name: str) -> None:
        super().__init__(convert_charrefs=True)
        self.payloads: list[str] = []
        self._class_name = class_name
        self._attr_name = attr_name

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)
        class_attr = attr_map.get("class") or ""
        if self._class_name and self._class_name not in class_attr.split():
            return

        payload = attr_map.get(self._attr_name)
        if payload:
            self.payloads.append(payload)


def version_matches(offered_version: str, pinned_version: str, *, strategy: str = "exact") -> bool:
    offered = offered_version.strip()
    pinned = pinned_version.strip()
    if offered == pinned:
        return True
    if strategy == "strip_trailing_parenthetical":
        offered = TRAILING_PARENTHETICAL_RE.sub("", offered).strip()
        pinned = TRAILING_PARENTHETICAL_RE.sub("", pinned).strip()
        return bool(offered) and offered == pinned
    return False


class HTTPProvider(BaseProvider):
    def resolve_latest_release(
        self, app_definition: AppDefinition, http_client: HttpClient
    ) -> ResolvedRelease:
        configured_version = self._resolve_configured_version(app_definition, http_client)
        if configured_version is not None:
            artifact = self._resolve_configured_version_artifact(
                app_definition, http_client, configured_version
            )
            return artifact or ResolvedRelease(version=configured_version)

        candidates = self._fetch_candidates(app_definition, http_client)
        ordered_candidates = self._order_latest_candidates(app_definition, candidates)
        resolved = self._first_matching_release(app_definition, ordered_candidates)
        if resolved is not None:
            return resolved
        raise ValueError(f"could not find a matching HTTP release for {app_definition.app_id}")

    def resolve_pinned_release(
        self, app_definition: AppDefinition, http_client: HttpClient, version: str
    ) -> ResolvedRelease:
        if self._version_config(app_definition) is not None:
            pinned_version = version.strip()
            artifact = self._resolve_configured_version_artifact(
                app_definition, http_client, pinned_version
            )
            return artifact or ResolvedRelease(version=pinned_version)

        candidates = self._fetch_candidates(app_definition, http_client)
        resolved = self._first_matching_release(app_definition, candidates, pinned_version=version)
        if resolved is not None:
            return resolved
        raise ValueError(
            f"app {app_definition.app_id} pinned HTTP version {version.strip()} "
            f"was not found on {app_definition.source_url}"
        )

    def _resolve_configured_version(
        self, app_definition: AppDefinition, http_client: HttpClient
    ) -> str | None:
        config = self._version_config(app_definition)
        if config is None:
            return None

        source_url = str(config.get("source_url", app_definition.source_url)).strip()
        if not source_url:
            raise ValueError(f"app {app_definition.app_id} http version.source_url is required")

        extractor = str(config.get("extractor", "")).strip()
        if not extractor:
            raise ValueError(f"app {app_definition.app_id} http version.extractor is required")

        payload = http_client.get_text(source_url)
        if extractor == "json_path":
            return self._version_from_json_path(app_definition, payload, config)
        if extractor == "regex":
            return self._version_from_regex(app_definition, payload, config)

        raise ValueError(
            f"app {app_definition.app_id} has unsupported http version extractor: {extractor}"
        )

    def _version_from_json_path(
        self, app_definition: AppDefinition, payload: str, config: dict[str, object]
    ) -> str:
        path = str(config.get("path", "")).strip()
        if not path:
            raise ValueError(f"app {app_definition.app_id} http version.path is required")
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"app {app_definition.app_id} version source returned invalid JSON"
            ) from exc

        version = _first_path_value(decoded, path)
        if version is None:
            raise ValueError(f"app {app_definition.app_id} http version.path {path} was not found")
        resolved = str(version).strip()
        if not resolved:
            raise ValueError(f"app {app_definition.app_id} http version.path {path} was empty")
        return resolved

    def _version_from_regex(
        self, app_definition: AppDefinition, payload: str, config: dict[str, object]
    ) -> str:
        pattern = str(config.get("pattern", "")).strip()
        if not pattern:
            raise ValueError(f"app {app_definition.app_id} http version.pattern is required")
        regex = _compile_regex(app_definition, "version.pattern", pattern)
        match = regex.search(payload)
        if match is None:
            raise ValueError(f"app {app_definition.app_id} http version.pattern did not match")
        version = _extract_regex_value(match)
        if not version:
            raise ValueError(f"app {app_definition.app_id} http version.pattern matched empty")
        return version

    def _resolve_configured_version_artifact(
        self, app_definition: AppDefinition, http_client: HttpClient, version: str
    ) -> ResolvedRelease | None:
        static_download_url = str(app_definition.provider_config.get("download_url", "")).strip()
        if static_download_url:
            download_url = urljoin(app_definition.source_url, static_download_url)
            return ResolvedRelease(
                version=version,
                download_url=download_url,
                file_extension=self._file_extension(app_definition, download_url),
            )

        if not self._has_artifact_config(app_definition):
            return None

        candidates = self._fetch_candidates(app_definition, http_client)
        resolved = self._first_matching_release(app_definition, candidates, pinned_version=version)
        if resolved is None:
            raise ValueError(
                f"could not find a matching HTTP artifact for {app_definition.app_id} "
                f"version {version}"
            )
        return ResolvedRelease(
            version=version,
            download_url=resolved.download_url,
            release_name=resolved.release_name,
            file_extension=resolved.file_extension,
        )

    @staticmethod
    def _version_config(app_definition: AppDefinition) -> dict[str, object] | None:
        config = app_definition.provider_config.get("version")
        if config is None:
            return None
        if not isinstance(config, dict):
            raise ValueError(f"app {app_definition.app_id} http version must be an object")
        return dict(config)

    @staticmethod
    def _has_artifact_config(app_definition: AppDefinition) -> bool:
        artifact_keys = {
            "extractor",
            "entries_path",
            "download_url_path",
            "download_url_regex",
            "filters",
            "filters_regex",
            "exclude_regex",
            "prefer_false_path",
            "version_path",
            "version_regex",
            "release_name_path",
            "release_name_template",
            "append_version_to_release_name",
        }
        return any(key in app_definition.provider_config for key in artifact_keys)

    def _fetch_candidates(
        self, app_definition: AppDefinition, http_client: HttpClient
    ) -> list[object]:
        payload = http_client.get_text(app_definition.source_url)
        extractor = str(app_definition.provider_config.get("extractor", "html_links")).strip()

        if extractor == "json_entries":
            return self._entries_from_json_payload(app_definition, payload)
        if extractor == "html_json_attribute":
            return self._entries_from_html_json_attribute(app_definition, payload)
        if extractor == "html_sections":
            section_parser = _SectionParser(app_definition.source_url)
            section_parser.feed(payload)
            section_parser.close()
            return list(section_parser.sections)
        if extractor == "html_links":
            link_parser = _LinkParser(app_definition.source_url)
            link_parser.feed(payload)
            link_parser.close()
            return list(link_parser.links)

        raise ValueError(f"app {app_definition.app_id} has unsupported http extractor: {extractor}")

    def _entries_from_json_payload(
        self, app_definition: AppDefinition, payload: str
    ) -> list[object]:
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValueError(f"app {app_definition.app_id} returned invalid JSON") from exc
        return self._entries_from_object(app_definition, decoded)

    def _entries_from_html_json_attribute(
        self, app_definition: AppDefinition, payload: str
    ) -> list[object]:
        class_name = str(app_definition.provider_config.get("html_class", "")).strip()
        attr_name = str(app_definition.provider_config.get("html_attr", "data-config")).strip()
        encoding = str(app_definition.provider_config.get("html_attr_encoding", "base64")).strip()
        parser = _AttributePayloadParser(class_name=class_name, attr_name=attr_name)
        parser.feed(payload)
        parser.close()

        entries: list[object] = []
        for raw_payload in parser.payloads:
            try:
                decoded_payload = unescape(raw_payload)
                if encoding == "base64":
                    decoded_payload = base64.b64decode(decoded_payload).decode("utf-8")
                parsed = json.loads(decoded_payload)
            except (ValueError, json.JSONDecodeError):
                continue
            entries.extend(self._entries_from_object(app_definition, parsed))
        return entries

    def _entries_from_object(self, app_definition: AppDefinition, obj: object) -> list[object]:
        entries_path = str(app_definition.provider_config.get("entries_path", "")).strip()
        values = _path_values(obj, entries_path) if entries_path else [obj]
        entries: list[object] = []
        for value in values:
            if isinstance(value, list):
                entries.extend(value)
            else:
                entries.append(value)
        return entries

    def _order_latest_candidates(
        self, app_definition: AppDefinition, candidates: list[object]
    ) -> list[object]:
        prefer_false_path = str(app_definition.provider_config.get("prefer_false_path", "")).strip()
        if not prefer_false_path:
            return candidates
        return sorted(
            candidates, key=lambda candidate: bool(_first_path_value(candidate, prefer_false_path))
        )

    def _first_matching_release(
        self,
        app_definition: AppDefinition,
        candidates: list[object],
        *,
        pinned_version: str | None = None,
    ) -> ResolvedRelease | None:
        for candidate in candidates:
            if not self._candidate_matches_filters(app_definition, candidate):
                continue

            version = self._extract_version(app_definition, candidate)
            if not version:
                continue
            if pinned_version is not None and not version_matches(
                version,
                pinned_version,
                strategy=str(
                    app_definition.provider_config.get("version_match_strategy", "exact")
                ).strip(),
            ):
                continue

            download_url = self._extract_download_url(app_definition, candidate)
            if not download_url:
                continue

            file_extension = self._file_extension(app_definition, download_url)
            return ResolvedRelease(
                version=version,
                download_url=download_url,
                release_name=self._extract_release_name(app_definition, candidate, version),
                file_extension=file_extension,
            )
        return None

    def _candidate_matches_filters(self, app_definition: AppDefinition, candidate: object) -> bool:
        filters = app_definition.provider_config.get("filters") or {}
        if not isinstance(filters, dict):
            raise ValueError(f"app {app_definition.app_id} http filters must be an object")
        for path, expected in filters.items():
            values = [str(value).strip().lower() for value in _path_values(candidate, str(path))]
            if str(expected).strip().lower() not in values:
                return False

        regex_filters = app_definition.provider_config.get("filters_regex") or {}
        if not isinstance(regex_filters, dict):
            raise ValueError(f"app {app_definition.app_id} http filters_regex must be an object")
        for path, pattern in regex_filters.items():
            regex = _compile_regex(app_definition, "filters_regex", str(pattern))
            if not any(regex.search(str(value)) for value in _path_values(candidate, str(path))):
                return False

        exclude_regex = app_definition.provider_config.get("exclude_regex") or {}
        if not isinstance(exclude_regex, dict):
            raise ValueError(f"app {app_definition.app_id} http exclude_regex must be an object")
        for path, pattern in exclude_regex.items():
            regex = _compile_regex(app_definition, "exclude_regex", str(pattern))
            if any(regex.search(str(value)) for value in _path_values(candidate, str(path))):
                return False

        return True

    def _extract_version(self, app_definition: AppDefinition, candidate: object) -> str | None:
        version_path = str(app_definition.provider_config.get("version_path", "")).strip()
        values = _path_values(candidate, version_path) if version_path else _all_strings(candidate)
        version_regex = str(app_definition.provider_config.get("version_regex", "")).strip()

        if version_regex:
            regex = _compile_regex(app_definition, "version_regex", version_regex)
            for value in values:
                match = regex.search(str(value))
                if match is None:
                    continue
                version = _extract_regex_value(match)
                if version:
                    return version
            return None

        for value in values:
            version = str(value).strip()
            if version:
                return version
        return None

    def _extract_download_url(self, app_definition: AppDefinition, candidate: object) -> str | None:
        url_path = str(app_definition.provider_config.get("download_url_path", "")).strip()
        values = _path_values(candidate, url_path) if url_path else _all_strings(candidate)
        url_regex = str(app_definition.provider_config.get("download_url_regex", "")).strip()

        if url_regex:
            regex = _compile_regex(app_definition, "download_url_regex", url_regex)
            for value in values:
                text = str(value).strip()
                match = regex.search(text)
                if match is None:
                    continue
                return match.groupdict().get("url") or text
            return None

        for value in values:
            text = str(value).strip()
            if text.startswith(("http://", "https://")):
                return text
        return None

    def _extract_release_name(
        self, app_definition: AppDefinition, candidate: object, version: str
    ) -> str | None:
        template = app_definition.provider_config.get("release_name_template")
        if isinstance(template, str) and template.strip():
            template_values = _string_values_by_key(candidate)
            template_values["version"] = version
            return template.format(**template_values)

        release_name_path = str(app_definition.provider_config.get("release_name_path", "")).strip()
        if release_name_path:
            raw = _first_path_value(candidate, release_name_path)
            if raw is not None:
                release_name = str(raw).strip()
                if release_name and app_definition.provider_config.get(
                    "append_version_to_release_name"
                ):
                    if version not in release_name:
                        release_name = f"{release_name} {version}".strip()
                return release_name or None
        return None

    @staticmethod
    def _file_extension(app_definition: AppDefinition, download_url: str) -> str:
        configured = str(app_definition.provider_config.get("file_extension", "")).strip()
        if configured:
            return configured if configured.startswith(".") else f".{configured}"
        return PurePosixPath(download_url).suffix or ".apk"


def _compile_regex(app_definition: AppDefinition, key: str, pattern: str) -> re.Pattern[str]:
    try:
        return re.compile(pattern, re.IGNORECASE)
    except re.error as exc:
        raise ValueError(f"app {app_definition.app_id} has invalid http {key}: {exc}") from exc


def _extract_regex_value(match: re.Match[str]) -> str:
    value = match.groupdict().get("version")
    if value is None:
        value = match.group(1) if match.groups() else match.group(0)
    return value.strip()


def _path_values(obj: object, path: str) -> list[object]:
    values = [obj]
    for segment in [part for part in path.split(".") if part]:
        next_values: list[object] = []
        for value in values:
            if isinstance(value, dict) and segment in value:
                next_values.append(value[segment])
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict) and segment in item:
                        next_values.append(item[segment])
        values = _flatten_lists(next_values)
        if not values:
            break
    return values


def _first_path_value(obj: object, path: str) -> object | None:
    values = _path_values(obj, path)
    return values[0] if values else None


def _flatten_lists(values: list[object]) -> list[object]:
    flattened: list[object] = []
    for value in values:
        if isinstance(value, list):
            flattened.extend(value)
        else:
            flattened.append(value)
    return flattened


def _all_strings(obj: object) -> list[str]:
    if isinstance(obj, str):
        return [obj]
    if isinstance(obj, dict):
        strings: list[str] = []
        for value in obj.values():
            strings.extend(_all_strings(value))
        return strings
    if isinstance(obj, list):
        strings = []
        for value in obj:
            strings.extend(_all_strings(value))
        return strings
    return []


def _string_values_by_key(obj: object) -> dict[str, str]:
    values: dict[str, str] = {}
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(value, (str, int, float, bool)):
                values[str(key)] = str(value)
    return values
