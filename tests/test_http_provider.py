from __future__ import annotations

import json

from obtainium_serverside.models import AppDefinition
from obtainium_serverside.providers import get_provider
from obtainium_serverside.providers.http import HTTPProvider


class StubHttpClient:
    def __init__(self, payload: str | dict[str, object]) -> None:
        self.payload = payload
        self.requested_urls: list[str] = []

    def get_text(self, url: str) -> str:
        self.requested_urls.append(url)
        if isinstance(self.payload, str):
            return self.payload
        return json.dumps(self.payload)


def test_http_provider_scrapes_versioned_download_link_from_html() -> None:
    html = """
    <html>
      <body>
        <a href="/downloads/example-app-2.1.0.AppImage">Download current</a>
        <a href="/downloads/example-app-2.0.0.AppImage">Download previous</a>
      </body>
    </html>
    """
    provider = HTTPProvider()
    app_definition = AppDefinition(
        app_id="org.example.app",
        provider="http",
        source_url="https://example.com/releases/",
        provider_config={
            "download_url_path": "href",
            "download_url_regex": r"example-app-(?P<version>\d+\.\d+\.\d+)\.AppImage$",
            "version_path": "href",
            "version_regex": r"example-app-(?P<version>\d+\.\d+\.\d+)\.AppImage$",
            "file_extension": ".AppImage",
        },
    )

    release = provider.resolve_latest_release(app_definition, StubHttpClient(html))

    assert release.version == "2.1.0"
    assert release.download_url == "https://example.com/downloads/example-app-2.1.0.AppImage"
    assert release.file_extension == ".AppImage"


def test_http_provider_resolves_jetbrains_toolbox_from_release_json() -> None:
    payload = {
        "TBA": [
            {
                "version": "3.5",
                "build": "3.5.0.84344",
                "downloads": {
                    "linux": {
                        "link": (
                            "https://download.jetbrains.com/toolbox/"
                            "jetbrains-toolbox-3.5.0.84344.tar.gz"
                        )
                    }
                },
            }
        ]
    }
    provider = HTTPProvider()
    app_definition = AppDefinition(
        app_id="com.jetbrains.toolbox",
        name="JetBrains Toolbox",
        provider="http",
        source_url="https://data.services.jetbrains.com/products/releases?code=TBA&type=release",
        provider_config={
            "extractor": "json_entries",
            "entries_path": "TBA",
            "version_path": "build",
            "download_url_path": "downloads.linux.link",
            "release_name_template": "JetBrains Toolbox {version}",
            "file_extension": ".tar.gz",
        },
    )

    release = provider.resolve_latest_release(app_definition, StubHttpClient(payload))

    assert release.version == "3.5.0.84344"
    assert release.release_name == "JetBrains Toolbox 3.5.0.84344"
    assert release.download_url.endswith("jetbrains-toolbox-3.5.0.84344.tar.gz")
    assert release.file_extension == ".tar.gz"


def test_http_provider_resolves_pinned_version_from_json_entries() -> None:
    payload = {
        "TBA": [
            {
                "build": "3.5.0.84344",
                "downloads": {
                    "linux": {
                        "link": (
                            "https://download.jetbrains.com/toolbox/"
                            "jetbrains-toolbox-3.5.0.84344.tar.gz"
                        )
                    }
                },
            },
            {
                "build": "3.4.3.81140",
                "downloads": {
                    "linux": {
                        "link": (
                            "https://download.jetbrains.com/toolbox/"
                            "jetbrains-toolbox-3.4.3.81140.tar.gz"
                        )
                    }
                },
            },
        ]
    }
    provider = HTTPProvider()
    app_definition = AppDefinition(
        app_id="com.jetbrains.toolbox",
        provider="http",
        source_url="https://data.services.jetbrains.com/products/releases?code=TBA&type=release",
        provider_config={
            "extractor": "json_entries",
            "entries_path": "TBA",
            "version_path": "build",
            "download_url_path": "downloads.linux.link",
            "file_extension": ".tar.gz",
        },
        version="3.4.3.81140",
    )

    release = provider.resolve_release(app_definition, StubHttpClient(payload))

    assert release.version == "3.4.3.81140"
    assert release.download_url.endswith("jetbrains-toolbox-3.4.3.81140.tar.gz")


def test_http_provider_is_registered() -> None:
    assert isinstance(get_provider("http"), HTTPProvider)
