"""Live integration tests for HTTP-distributed app releases.

These tests hit real upstream pages and APIs, then exercise ``HTTPProvider`` with
app-specific configuration. A genuine host/network outage skips with a clear reason,
but a loaded page/API that no longer parses fails loudly.

The Loxone pinning test independently decodes the live page instead of reusing
provider internals, so it still catches regressions in the structured download data.
"""

from __future__ import annotations

import base64
import json
import re
import urllib.error
from html import unescape

import pytest

from obtainium_serverside.http import HttpClient
from obtainium_serverside.models import AppDefinition
from obtainium_serverside.providers.http import HTTPProvider

JETBRAINS_RELEASES_URL = (
    "https://data.services.jetbrains.com/products/releases?code=TBA&type=release"
)
JETBRAINS_DOWNLOAD_HOST = "https://download.jetbrains.com/toolbox/"
LOXONE_DOWNLOADS_URL = "https://www.loxone.com/enus/support/downloads/"
LOXONE_DOWNLOAD_HOST = "https://updatefiles.loxone.com/"

pytestmark = pytest.mark.integration

_LOXONE_CONFIG_RE = re.compile(
    r'class="[^"]*loxone-software-download-root[^"]*"[^>]*data-config="([^"]+)"'
)


def _jetbrains_toolbox_app() -> AppDefinition:
    return AppDefinition(
        app_id="com.jetbrains.toolbox",
        name="JetBrains Toolbox",
        provider="http",
        source_url=JETBRAINS_RELEASES_URL,
        provider_config={
            "extractor": "json_entries",
            "entries_path": "TBA",
            "version_path": "build",
            "download_url_path": "downloads.linux.link",
            "release_name_template": "JetBrains Toolbox {version}",
            "file_extension": ".tar.gz",
        },
    )


def _loxone_http_config(
    *, platform: str = "android", file_extension: str = ".apk"
) -> dict[str, object]:
    platform_segment = "Android" if platform == "android" else platform.split("_", 1)[0]
    return {
        "extractor": "html_json_attribute",
        "html_class": "loxone-software-download-root",
        "html_attr": "data-config",
        "html_attr_encoding": "base64",
        "entries_path": "config",
        "filters": {"application": "app", "type": "release"},
        "prefer_false_path": "archived",
        "version_path": "version",
        "version_match_strategy": "strip_trailing_parenthetical",
        "download_url_path": "allVersions.groups.downloads.url",
        "download_url_regex": (
            rf"https://updatefiles\.loxone\.com/{platform_segment}/" rf"Release/.*{file_extension}$"
        ),
        "release_name_path": "title",
        "append_version_to_release_name": True,
        "file_extension": file_extension,
    }


def _loxone_android_app(version: str | None = None) -> AppDefinition:
    return AppDefinition(
        app_id="com.loxone.kerberos",
        name="Loxone App",
        provider="http",
        source_url=LOXONE_DOWNLOADS_URL,
        provider_config=_loxone_http_config(),
        version=version,
    )


def _loxone_linux_deb_app() -> AppDefinition:
    return AppDefinition(
        app_id="com.loxone.kerberos",
        name="Loxone App Linux deb",
        provider="http",
        source_url=LOXONE_DOWNLOADS_URL,
        provider_config=_loxone_http_config(platform="linux_x64", file_extension=".deb"),
    )


def _fetch_text(url: str, label: str) -> str:
    try:
        return HttpClient().get_text(url)
    except urllib.error.URLError as exc:  # pragma: no cover - depends on network
        pytest.skip(f"{label} is unreachable: {exc}")


@pytest.mark.parametrize(
    ("case_name", "source_url", "apps", "expectations"),
    [
        pytest.param(
            "JetBrains Toolbox",
            JETBRAINS_RELEASES_URL,
            [_jetbrains_toolbox_app()],
            [(JETBRAINS_DOWNLOAD_HOST, ".tar.gz")],
            id="jetbrains-toolbox",
        ),
        pytest.param(
            "Loxone App",
            LOXONE_DOWNLOADS_URL,
            [_loxone_android_app(), _loxone_linux_deb_app()],
            [(LOXONE_DOWNLOAD_HOST, ".apk"), (LOXONE_DOWNLOAD_HOST, ".deb")],
            id="loxone-app",
        ),
    ],
)
def test_live_http_latest_releases_resolve(
    case_name: str,
    source_url: str,
    apps: list[AppDefinition],
    expectations: list[tuple[str, str]],
) -> None:
    _fetch_text(source_url, case_name)
    provider = HTTPProvider()
    client = HttpClient()

    for app_definition, (download_host, file_extension) in zip(apps, expectations, strict=True):
        release = provider.resolve_release(app_definition, client)

        assert release.version
        assert release.download_url.startswith(download_host)
        assert release.download_url.lower().endswith(file_extension)
        assert release.file_extension == file_extension


def _offered_loxone_release_versions(html: str) -> list[str]:
    versions: list[str] = []
    for payload in _LOXONE_CONFIG_RE.findall(html):
        try:
            decoded = base64.b64decode(unescape(payload)).decode("utf-8")
            config = json.loads(decoded).get("config")
        except (ValueError, json.JSONDecodeError):
            continue
        if not isinstance(config, dict):
            continue
        if str(config.get("application", "")).strip().lower() != "app":
            continue
        if str(config.get("type", "")).strip().lower() != "release":
            continue
        version = str(config.get("version", "")).strip()
        if version:
            versions.append(version)
    return versions


def test_live_http_loxone_pins_an_archived_older_version() -> None:
    html = _fetch_text(LOXONE_DOWNLOADS_URL, "Loxone downloads page")
    versions = _offered_loxone_release_versions(html)
    assert versions, "live page exposed no app/release versions"

    provider = HTTPProvider()
    client = HttpClient()
    latest = provider.resolve_release(_loxone_android_app(), client)

    older_candidates = [version for version in versions if version != latest.version]
    if not older_candidates:
        pytest.skip("live page currently offers only the latest release")
    older = older_candidates[-1]

    pinned = provider.resolve_release(_loxone_android_app(older), client)

    assert pinned.version == older
    assert pinned.download_url.startswith(LOXONE_DOWNLOAD_HOST)
    assert pinned.download_url.lower().endswith(".apk")
    assert pinned.download_url != latest.download_url


def test_live_http_loxone_missing_pin_errors() -> None:
    _fetch_text(LOXONE_DOWNLOADS_URL, "Loxone downloads page")
    provider = HTTPProvider()

    with pytest.raises(ValueError, match="0.0.0-does-not-exist"):
        provider.resolve_release(_loxone_android_app("0.0.0-does-not-exist"), HttpClient())
