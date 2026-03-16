from __future__ import annotations

from obtainium_serverside.models import AppDefinition
from obtainium_serverside.providers.loxone import LoxoneProvider


class StubHttpClient:
    def __init__(self, html: str) -> None:
        self.html = html

    def get_text(self, url: str) -> str:
        return self.html


def test_loxone_provider_selects_release_android_apk() -> None:
    html = """
    <html>
      <body>
        <h3>Loxone App 16.2.2 - Playstore</h3>
        <a href="https://play.google.com/store/apps/details?id=com.loxone.kerberos">Android Device</a>
        <h3>Loxone App 16.2.2 for Android</h3>
        <a href="https://updatefiles.loxone.com/Android/Release/162215280.apk">Download</a>
        <a href="https://play.google.com/store/apps/details?id=com.loxone.kerberos">Play Store</a>
        <h3>Loxone App 16.3.0 (14988) for Android - Public Beta</h3>
        <a href="https://updatefiles.loxone.com/Android/Beta/163014988.apk">Download</a>
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


def test_loxone_provider_supports_beta_channel() -> None:
    html = """
    <html>
      <body>
        <h3>Loxone App 16.2.2 for Android</h3>
        <a href="https://updatefiles.loxone.com/Android/Release/162215280.apk">Download</a>
        <h3>Loxone App 16.3.0 (14988) for Android - Public Beta</h3>
        <a href="https://updatefiles.loxone.com/Android/Beta/163014988.apk">Download</a>
      </body>
    </html>
    """
    provider = LoxoneProvider()
    app_definition = AppDefinition(
        app_id="com.loxone.kerberos",
        name="Loxone App",
        provider="loxone",
        source_url="https://www.loxone.com/enus/support/downloads/",
        provider_config={"channel": "beta"},
    )

    release = provider.resolve_latest_release(app_definition, StubHttpClient(html))

    assert release.version == "16.3.0 (14988)"
    assert release.download_url == "https://updatefiles.loxone.com/Android/Beta/163014988.apk"
