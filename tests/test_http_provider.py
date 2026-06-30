from __future__ import annotations

import base64
import json

import pytest

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


class UrlPayloadHttpClient:
    def __init__(self, payloads: dict[str, str | dict[str, object]]) -> None:
        self.payloads = payloads
        self.requested_urls: list[str] = []

    def get_text(self, url: str) -> str:
        self.requested_urls.append(url)
        payload = self.payloads[url]
        if isinstance(payload, str):
            return payload
        return json.dumps(payload)


def _build_loxone_structured_html(*configs: dict[str, object]) -> str:
    blocks: list[str] = []
    for index, config in enumerate(configs, start=1):
        payload = base64.b64encode(json.dumps({"config": config, "lng": "en"}).encode()).decode()
        blocks.append(
            f'<div id="loxone-software-download-{index}" '
            f'class="loxone-software-download-root" data-config="{payload}"></div>'
        )
    return "<html><body>" + "".join(blocks) + "</body></html>"


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


def _loxone_android_config(version: str, apk_url: str, *, archived: bool) -> dict[str, object]:
    return {
        "application": "app",
        "type": "release",
        "title": f"LOXONE App {version}",
        "version": version,
        "archived": archived,
        "allVersions": [
            {
                "label": "Mobile",
                "groups": [
                    {
                        "label": "Android",
                        "platform": "android",
                        "downloads": [
                            {
                                "label": "Download",
                                "url": (
                                    "https://play.google.com/store/apps/details"
                                    "?id=com.loxone.kerberos"
                                ),
                            },
                            {"label": "Download", "url": apk_url},
                        ],
                    }
                ],
            }
        ],
    }


def _loxone_linux_config(version: str, appimage_url: str, deb_url: str) -> dict[str, object]:
    return {
        "application": "app",
        "type": "release",
        "title": f"LOXONE App {version}",
        "version": version,
        "archived": False,
        "allVersions": [
            {
                "label": "Desktop",
                "groups": [
                    {
                        "label": "Linux x64",
                        "platform": "linux_x64",
                        "downloads": [
                            {"label": "Download", "url": appimage_url},
                            {"label": "Download", "url": deb_url},
                        ],
                    }
                ],
            }
        ],
    }


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


def test_http_provider_resolves_loxone_android_apk_from_structured_page_data() -> None:
    html = _build_loxone_structured_html(
        _loxone_android_config(
            "17.1.1 (16704)",
            "https://updatefiles.loxone.com/Android/Release/171116704.apk",
            archived=False,
        ),
        _loxone_android_config(
            "17.1.0 (16241)",
            "https://updatefiles.loxone.com/Android/Release/171016241.apk",
            archived=True,
        ),
    )
    provider = HTTPProvider()
    app_definition = AppDefinition(
        app_id="com.loxone.kerberos",
        name="Loxone App",
        provider="http",
        source_url="https://www.loxone.com/enus/support/downloads/",
        provider_config=_loxone_http_config(),
    )

    release = provider.resolve_latest_release(app_definition, StubHttpClient(html))

    assert release.version == "17.1.1 (16704)"
    assert release.download_url == "https://updatefiles.loxone.com/Android/Release/171116704.apk"
    assert release.release_name == "LOXONE App 17.1.1 (16704)"
    assert release.file_extension == ".apk"


def test_http_provider_resolves_loxone_pinned_archived_android_version() -> None:
    html = _build_loxone_structured_html(
        _loxone_android_config(
            "17.1.1 (16704)",
            "https://updatefiles.loxone.com/Android/Release/171116704.apk",
            archived=False,
        ),
        _loxone_android_config(
            "17.1.0 (16241)",
            "https://updatefiles.loxone.com/Android/Release/171016241.apk",
            archived=True,
        ),
    )
    provider = HTTPProvider()
    app_definition = AppDefinition(
        app_id="com.loxone.kerberos",
        provider="http",
        source_url="https://www.loxone.com/enus/support/downloads/",
        provider_config=_loxone_http_config(),
        version="17.1.0",
    )

    release = provider.resolve_release(app_definition, StubHttpClient(html))

    assert release.version == "17.1.0 (16241)"
    assert release.download_url == "https://updatefiles.loxone.com/Android/Release/171016241.apk"


def test_http_provider_resolves_loxone_linux_deb_from_structured_page_data() -> None:
    html = _build_loxone_structured_html(
        _loxone_linux_config(
            "17.1.1 (16704)",
            "https://updatefiles.loxone.com/linux/Release/171116704-x86_64.AppImage",
            "https://updatefiles.loxone.com/linux/Release/171116704-amd64.deb",
        ),
    )
    provider = HTTPProvider()
    app_definition = AppDefinition(
        app_id="com.loxone.kerberos",
        provider="http",
        source_url="https://www.loxone.com/enus/support/downloads/",
        provider_config=_loxone_http_config(platform="linux_x64", file_extension=".deb"),
    )

    release = provider.resolve_latest_release(app_definition, StubHttpClient(html))

    assert release.version == "17.1.1 (16704)"
    assert release.download_url == (
        "https://updatefiles.loxone.com/linux/Release/171116704-amd64.deb"
    )
    assert release.file_extension == ".deb"


def test_http_provider_resolves_version_only_from_configured_json_path() -> None:
    provider = HTTPProvider()
    app_definition = AppDefinition(
        app_id="org.tlauncher.tlauncher",
        provider="http",
        source_url="https://tlauncher.org/",
        provider_config={
            "version": {
                "extractor": "json_path",
                "source_url": (
                    "https://repo.tlauncher.org/tlauncher-sources/prod/release/"
                    "tlauncher/appConfig.json"
                ),
                "path": "appVersion",
            }
        },
    )
    http_client = UrlPayloadHttpClient(
        {
            (
                "https://repo.tlauncher.org/tlauncher-sources/prod/release/"
                "tlauncher/appConfig.json"
            ): {"appVersion": "2.9319"}
        }
    )

    release = provider.resolve_latest_release(app_definition, http_client)

    assert release.version == "2.9319"
    assert release.download_url is None
    assert http_client.requested_urls == [
        "https://repo.tlauncher.org/tlauncher-sources/prod/release/" "tlauncher/appConfig.json"
    ]


def test_http_provider_resolves_version_only_from_configured_regex() -> None:
    provider = HTTPProvider()
    app_definition = AppDefinition(
        app_id="org.example.app",
        provider="http",
        source_url="https://example.com/",
        provider_config={
            "version": {
                "extractor": "regex",
                "source_url": "https://example.com/releases",
                "pattern": r"Version (?P<version>\d+\.\d+\.\d+)",
            }
        },
    )

    release = provider.resolve_latest_release(
        app_definition,
        UrlPayloadHttpClient({"https://example.com/releases": "<h1>Version 1.2.3</h1>"}),
    )

    assert release.version == "1.2.3"
    assert release.download_url is None


def test_http_provider_configured_regex_uses_first_unnamed_capture_group() -> None:
    provider = HTTPProvider()
    app_definition = AppDefinition(
        app_id="org.example.app",
        provider="http",
        source_url="https://example.com/",
        provider_config={
            "version": {
                "extractor": "regex",
                "source_url": "https://example.com/releases",
                "pattern": r"Version (\d+\.\d+\.\d+)",
            }
        },
    )

    release = provider.resolve_latest_release(
        app_definition,
        UrlPayloadHttpClient({"https://example.com/releases": "<h1>Version 1.2.3</h1>"}),
    )

    assert release.version == "1.2.3"


def test_http_provider_configured_regex_no_match_errors_clearly() -> None:
    provider = HTTPProvider()
    app_definition = AppDefinition(
        app_id="org.example.app",
        provider="http",
        source_url="https://example.com/",
        provider_config={
            "version": {
                "extractor": "regex",
                "source_url": "https://example.com/releases",
                "pattern": r"Version (?P<version>\d+\.\d+\.\d+)",
            }
        },
    )

    with pytest.raises(ValueError, match="http version.pattern did not match"):
        provider.resolve_latest_release(
            app_definition,
            UrlPayloadHttpClient({"https://example.com/releases": "<h1>No version</h1>"}),
        )


def test_http_provider_configured_version_can_use_static_download_url() -> None:
    provider = HTTPProvider()
    app_definition = AppDefinition(
        app_id="org.tlauncher.tlauncher",
        provider="http",
        source_url="https://tlauncher.org/",
        provider_config={
            "version": {
                "extractor": "json_path",
                "source_url": "https://example.com/appConfig.json",
                "path": "appVersion",
            },
            "download_url": "https://tlauncher.org/installer-linux",
            "file_extension": ".sh",
        },
    )

    release = provider.resolve_latest_release(
        app_definition,
        UrlPayloadHttpClient({"https://example.com/appConfig.json": {"appVersion": "2.9319"}}),
    )

    assert release.version == "2.9319"
    assert release.download_url == "https://tlauncher.org/installer-linux"
    assert release.file_extension == ".sh"


def test_http_provider_configured_version_can_resolve_existing_artifact_config() -> None:
    html = """
    <html>
      <body>
        <a href="/downloads/example-app-1.2.3.AppImage">Download current</a>
      </body>
    </html>
    """
    provider = HTTPProvider()
    app_definition = AppDefinition(
        app_id="org.example.app",
        provider="http",
        source_url="https://example.com/releases/",
        provider_config={
            "version": {
                "extractor": "regex",
                "source_url": "https://example.com/latest",
                "pattern": r"Version (?P<version>\d+\.\d+\.\d+)",
            },
            "download_url_path": "href",
            "download_url_regex": r"example-app-(?P<version>\d+\.\d+\.\d+)\.AppImage$",
            "version_path": "href",
            "version_regex": r"example-app-(?P<version>\d+\.\d+\.\d+)\.AppImage$",
            "file_extension": ".AppImage",
        },
    )

    release = provider.resolve_latest_release(
        app_definition,
        UrlPayloadHttpClient(
            {
                "https://example.com/latest": "Version 1.2.3",
                "https://example.com/releases/": html,
            }
        ),
    )

    assert release.version == "1.2.3"
    assert release.download_url == "https://example.com/downloads/example-app-1.2.3.AppImage"
    assert release.file_extension == ".AppImage"


def test_http_provider_is_registered() -> None:
    assert isinstance(get_provider("http"), HTTPProvider)
