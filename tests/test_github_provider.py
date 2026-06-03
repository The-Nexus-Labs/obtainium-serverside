from __future__ import annotations

import json
import re

from obtainium_serverside.models import AppDefinition
from obtainium_serverside.providers.github import GitHubReleasesProvider


class StubHttpClient:
    def __init__(self, payload: list[dict[str, object]]) -> None:
        self.payload = payload
        self.requested_urls: list[str] = []

    def get_text(self, url: str) -> str:
        self.requested_urls.append(url)
        return json.dumps(self.payload)


def test_github_provider_selects_latest_stable_apk_release() -> None:
    provider = GitHubReleasesProvider()
    app_definition = AppDefinition(
        app_id="chat.simplex.app",
        name="SimpleX Chat",
        provider="github",
        source_url="https://github.com/simplex-chat/simplex-chat/releases",
        provider_config={
            "asset_regex": r"^simplex-aarch64\.apk$",
            "version_regex": r"^v?(.+)$",
        },
    )
    http_client = StubHttpClient(
        [
            {
                "tag_name": "v6.5.0-beta.5",
                "name": "v6.5.0-beta.5",
                "draft": False,
                "prerelease": True,
                "assets": [
                    {
                        "name": "simplex-aarch64.apk",
                        "browser_download_url": "https://github.com/simplex-chat/simplex-chat/releases/download/v6.5.0-beta.5/simplex-aarch64.apk",
                    }
                ],
            },
            {
                "tag_name": "v6.4.10",
                "name": "v6.4.10",
                "draft": False,
                "prerelease": False,
                "assets": [
                    {
                        "name": "simplex-aarch64.apk",
                        "browser_download_url": "https://github.com/simplex-chat/simplex-chat/releases/download/v6.4.10/simplex-aarch64.apk",
                    }
                ],
            },
        ]
    )

    release = provider.resolve_latest_release(app_definition, http_client)

    assert release.version == "6.4.10"
    assert release.download_url.endswith("/v6.4.10/simplex-aarch64.apk")
    assert http_client.requested_urls == [
        "https://api.github.com/repos/simplex-chat/simplex-chat/releases?per_page=20"
    ]


def test_github_provider_can_select_prereleases() -> None:
    provider = GitHubReleasesProvider()
    app_definition = AppDefinition(
        app_id="chat.simplex.app",
        provider="github",
        source_url="https://github.com/simplex-chat/simplex-chat",
        provider_config={
            "channel": "beta",
            "asset_regex": r"^simplex-aarch64\.apk$",
            "version_regex": r"^v?(.+)$",
        },
    )
    http_client = StubHttpClient(
        [
            {
                "tag_name": "v6.5.0-beta.5",
                "name": "v6.5.0-beta.5",
                "draft": False,
                "prerelease": True,
                "assets": [
                    {
                        "name": "simplex-aarch64.apk",
                        "browser_download_url": "https://github.com/simplex-chat/simplex-chat/releases/download/v6.5.0-beta.5/simplex-aarch64.apk",
                    }
                ],
            },
            {
                "tag_name": "v6.4.10",
                "name": "v6.4.10",
                "draft": False,
                "prerelease": False,
                "assets": [
                    {
                        "name": "simplex-aarch64.apk",
                        "browser_download_url": "https://github.com/simplex-chat/simplex-chat/releases/download/v6.4.10/simplex-aarch64.apk",
                    }
                ],
            },
        ]
    )

    release = provider.resolve_latest_release(app_definition, http_client)

    assert release.version == "6.5.0-beta.5"
    assert release.download_url.endswith("/v6.5.0-beta.5/simplex-aarch64.apk")


def test_github_provider_supports_custom_version_regex_and_name_source() -> None:
    provider = GitHubReleasesProvider()
    app_definition = AppDefinition(
        app_id="org.example.app",
        provider="github",
        source_url="https://github.com/example/mobile-app/releases/latest",
        provider_config={
            "asset_regex": r"^example-release\.apk$",
            "version_source": "name",
            "version_regex": r"Android build (?P<version>\d+\.\d+\.\d+)",
        },
    )
    http_client = StubHttpClient(
        [
            {
                "tag_name": "android-build-2026-03-15",
                "name": "Android build 3.14.15",
                "draft": False,
                "prerelease": False,
                "assets": [
                    {
                        "name": "example-release.apk",
                        "browser_download_url": "https://github.com/example/mobile-app/releases/download/android-build-2026-03-15/example-release.apk",
                    }
                ],
            }
        ]
    )

    release = provider.resolve_latest_release(app_definition, http_client)

    assert release.version == "3.14.15"
    assert release.release_name == "Android build 3.14.15"


def _release(tag: str, *, prerelease: bool = False) -> dict[str, object]:
    return {
        "tag_name": tag,
        "name": tag,
        "draft": False,
        "prerelease": prerelease,
        "assets": [
            {
                "name": "icsx5.apk",
                "browser_download_url": (
                    f"https://github.com/bitfireAT/icsx5/releases/download/{tag}/icsx5.apk"
                ),
            }
        ],
    }


class PagedStubHttpClient:
    def __init__(self, pages: dict[int, list[dict[str, object]]]) -> None:
        self.pages = pages
        self.requested_urls: list[str] = []

    def get_text(self, url: str) -> str:
        self.requested_urls.append(url)
        page = 1
        match = re.search(r"[?&]page=(\d+)", url)
        if match:
            page = int(match.group(1))
        return json.dumps(self.pages.get(page, []))


def test_github_provider_resolves_pinned_version_across_pages() -> None:
    provider = GitHubReleasesProvider()
    app_definition = AppDefinition(
        app_id="at.bitfire.icsdroid",
        provider="github",
        source_url="https://github.com/bitfireAT/icsx5/releases",
        provider_config={
            "asset_regex": r"^icsx5\.apk$",
            "version_regex": r"^v?(?P<version>.+)$",
        },
        version="2.4.3",
    )
    http_client = PagedStubHttpClient(
        {
            1: [_release("v2.6.0"), _release("v2.5.0")],
            2: [_release("v2.4.4"), _release("v2.4.3"), _release("v2.4.2")],
        }
    )

    release = provider.resolve_release(app_definition, http_client)

    assert release.version == "2.4.3"
    assert release.download_url.endswith("/v2.4.3/icsx5.apk")
    # The pin lives on the second page, so pagination must have advanced past page 1.
    assert any("page=2" in url for url in http_client.requested_urls)
    assert all("per_page=100" in url for url in http_client.requested_urls)


def test_github_provider_errors_when_pinned_version_missing() -> None:
    provider = GitHubReleasesProvider()
    app_definition = AppDefinition(
        app_id="at.bitfire.icsdroid",
        provider="github",
        source_url="https://github.com/bitfireAT/icsx5/releases",
        provider_config={"asset_regex": r"^icsx5\.apk$"},
        version="9.9.9",
    )
    http_client = PagedStubHttpClient({1: [_release("v2.6.0"), _release("v2.5.0")]})

    try:
        provider.resolve_release(app_definition, http_client)
    except ValueError as exc:
        assert "9.9.9" in str(exc)
        assert "not found" in str(exc)
    else:
        raise AssertionError("expected ValueError when the pinned version is absent")
