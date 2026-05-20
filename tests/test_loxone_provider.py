from __future__ import annotations

import base64
import json

from obtainium_serverside.models import AppDefinition
from obtainium_serverside.providers.loxone import LoxoneProvider


class StubHttpClient:
    def __init__(self, html: str) -> None:
        self.html = html

    def get_text(self, url: str) -> str:
        return self.html


def _build_structured_html(*configs: dict[str, object]) -> str:
    blocks: list[str] = []
    for index, config in enumerate(configs, start=1):
        payload = base64.b64encode(json.dumps({"config": config, "lng": "en"}).encode()).decode()
        blocks.append(
            f'<div id="loxone-software-download-{index}" class="loxone-software-download-root" data-config="{payload}"></div>'
        )
    return "<html><body>" + "".join(blocks) + "</body></html>"


def test_loxone_provider_selects_release_android_apk_from_structured_page_data() -> None:
    html = _build_structured_html(
        {
            "application": "app",
            "type": "release",
            "title": "LOXONE App",
            "version": "17.1.1 (16704)",
            "archived": False,
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
                                    "url": "https://play.google.com/store/apps/details?id=com.loxone.kerberos",
                                },
                                {
                                    "label": "Download",
                                    "url": "https://updatefiles.loxone.com/Android/Release/171116704.apk",
                                },
                            ],
                        }
                    ],
                }
            ],
        },
        {
            "application": "app",
            "type": "beta",
            "title": "LOXONE App 17.0.1 (15948) Public Beta",
            "version": "17.0.1 (15948)",
            "archived": False,
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
                                    "url": "https://updatefiles.loxone.com/Android/Beta/170115948.apk",
                                }
                            ],
                        }
                    ],
                }
            ],
        },
    )
    provider = LoxoneProvider()
    app_definition = AppDefinition(
        app_id="com.loxone.kerberos",
        name="Loxone App",
        provider="loxone",
        source_url="https://www.loxone.com/enus/support/downloads/",
    )

    release = provider.resolve_latest_release(app_definition, StubHttpClient(html))

    assert release.version == "17.1.1 (16704)"
    assert release.download_url == "https://updatefiles.loxone.com/Android/Release/171116704.apk"
    assert release.release_name == "LOXONE App 17.1.1 (16704)"


def test_loxone_provider_supports_beta_channel_from_structured_page_data() -> None:
    html = _build_structured_html(
        {
            "application": "app",
            "type": "release",
            "title": "LOXONE App",
            "version": "17.1.1 (16704)",
            "archived": False,
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
                                    "url": "https://updatefiles.loxone.com/Android/Release/171116704.apk",
                                }
                            ],
                        }
                    ],
                }
            ],
        },
        {
            "application": "app",
            "type": "beta",
            "title": "LOXONE App 17.0.1 (15948) Public Beta",
            "version": "17.0.1 (15948)",
            "archived": False,
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
                                    "url": "https://play.google.com/apps/testing/com.loxone.kerberos",
                                },
                                {
                                    "label": "Download",
                                    "url": "https://updatefiles.loxone.com/Android/Beta/170115948.apk",
                                },
                            ],
                        }
                    ],
                }
            ],
        },
    )
    provider = LoxoneProvider()
    app_definition = AppDefinition(
        app_id="com.loxone.kerberos",
        name="Loxone App",
        provider="loxone",
        source_url="https://www.loxone.com/enus/support/downloads/",
        provider_config={"channel": "beta"},
    )

    release = provider.resolve_latest_release(app_definition, StubHttpClient(html))

    assert release.version == "17.0.1 (15948)"
    assert release.download_url == "https://updatefiles.loxone.com/Android/Beta/170115948.apk"
    assert release.release_name == "LOXONE App 17.0.1 (15948) Public Beta"


def test_loxone_provider_falls_back_to_legacy_heading_parser() -> None:
    html = """
    <html>
      <body>
        <h3>Loxone App 16.2.2 - Playstore</h3>
        <a href="https://play.google.com/store/apps/details?id=com.loxone.kerberos">Android Device</a>
        <h3>Loxone App 16.2.2 for Android</h3>
        <a href="https://updatefiles.loxone.com/Android/Release/162215280.apk">Download</a>
        <a href="https://play.google.com/store/apps/details?id=com.loxone.kerberos">Play Store</a>
      </body>
    </html>
    """
    provider = LoxoneProvider()
    app_definition = AppDefinition(
        app_id="com.loxone.kerberos",
        name="Loxone App",
        provider="loxone",
        source_url="https://www.loxone.com/enus/support/downloads/",
    )

    release = provider.resolve_latest_release(app_definition, StubHttpClient(html))

    assert release.version == "16.2.2"
    assert release.download_url == "https://updatefiles.loxone.com/Android/Release/162215280.apk"
