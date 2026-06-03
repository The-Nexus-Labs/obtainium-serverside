"""Live integration tests for the Loxone provider against the real downloads page.

These run as part of the normal suite (and on every CI run) so that a change to
Loxone's download page format fails loudly and can be fixed fast. They hit the
network; a genuine host/network outage skips with a clear reason rather than flaking,
but a page that loads yet no longer parses (the case we care about) fails.

They independently parse the live page (rather than reusing provider internals) so
they catch regressions in how the provider reads Loxone's structured download data,
including the per-version pinning across archived releases.
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
from obtainium_serverside.providers.loxone import LoxoneProvider

LOXONE_DOWNLOADS_URL = "https://www.loxone.com/enus/support/downloads/"
LOXONE_APK_HOST = "https://updatefiles.loxone.com/"

pytestmark = pytest.mark.integration

_CONFIG_RE = re.compile(
    r'class="[^"]*loxone-software-download-root[^"]*"[^>]*data-config="([^"]+)"'
)


def _app_definition(version: str | None = None) -> AppDefinition:
    return AppDefinition(
        app_id="com.loxone.kerberos",
        name="Loxone App",
        provider="loxone",
        source_url=LOXONE_DOWNLOADS_URL,
        provider_config={"channel": "release"},
        version=version,
    )


def _fetch_page() -> str:
    try:
        return HttpClient().get_text(LOXONE_DOWNLOADS_URL)
    except urllib.error.URLError as exc:  # pragma: no cover - depends on network
        pytest.skip(f"Loxone downloads page is unreachable: {exc}")


def _offered_release_versions(html: str) -> list[str]:
    """Independently decode the structured download configs and return the offered
    ``app``/``release`` versions, in document order (current release first)."""
    versions: list[str] = []
    for payload in _CONFIG_RE.findall(html):
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


def test_live_loxone_latest_release_resolves() -> None:
    _fetch_page()  # skip early with a clear reason if the page is unreachable
    release = LoxoneProvider().resolve_release(_app_definition(), HttpClient())

    assert release.version
    assert release.download_url.startswith(LOXONE_APK_HOST)
    assert release.download_url.lower().endswith(".apk")


def test_live_loxone_pins_an_archived_older_version() -> None:
    html = _fetch_page()
    versions = _offered_release_versions(html)
    assert versions, "live page exposed no app/release versions"

    provider = LoxoneProvider()
    client = HttpClient()
    latest = provider.resolve_release(_app_definition(), client)

    older_candidates = [version for version in versions if version != latest.version]
    if not older_candidates:
        pytest.skip("live page currently offers only the latest release")
    older = older_candidates[-1]

    pinned = provider.resolve_release(_app_definition(older), client)

    assert pinned.version == older
    assert pinned.download_url.startswith(LOXONE_APK_HOST)
    assert pinned.download_url.lower().endswith(".apk")
    assert pinned.download_url != latest.download_url


def test_live_loxone_missing_pin_errors() -> None:
    _fetch_page()
    provider = LoxoneProvider()

    with pytest.raises(ValueError, match="0.0.0-does-not-exist"):
        provider.resolve_release(_app_definition("0.0.0-does-not-exist"), HttpClient())
