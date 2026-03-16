from __future__ import annotations

import json

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
