from __future__ import annotations

from obtainium_serverside.models import AppDefinition
from obtainium_serverside.providers.fdroid import FDroidProvider


class StubHttpClient:
    def __init__(self, html: str) -> None:
        self.html = html
        self.requested_urls: list[str] = []

    def get_text(self, url: str) -> str:
        self.requested_urls.append(url)
        return self.html


def test_fdroid_provider_selects_latest_package_apk() -> None:
    html = """
    <html>
      <body>
        <h3>Versions</h3>
        <a href="/F-Droid.apk">DOWNLOAD F-DROID</a>
        <p>Version 1.0.55 (55) - Added on Apr 21, 2026</p>
        <a href="/repo/ws.xsoh.etar_55.apk">Download APK </a>
        <a href="/repo/ws.xsoh.etar_55.apk.asc">PGP Signature</a>
        <p>Version 1.0.54 (54) - Added on Apr 19, 2026</p>
        <a href="/repo/ws.xsoh.etar_54.apk">Download APK </a>
      </body>
    </html>
    """
    provider = FDroidProvider()
    app_definition = AppDefinition(
        app_id="ws.xsoh.etar",
        name="Etar",
        provider="fdroid",
        source_url="https://f-droid.org/packages/ws.xsoh.etar/",
    )

    release = provider.resolve_latest_release(app_definition, StubHttpClient(html))

    assert release.version == "1.0.55"
    assert release.download_url == "https://f-droid.org/repo/ws.xsoh.etar_55.apk"
    assert release.release_name == "Version 1.0.55 (55)"


def test_fdroid_provider_requires_versioned_download_entry() -> None:
    provider = FDroidProvider()
    app_definition = AppDefinition(
        app_id="ws.xsoh.etar",
        provider="fdroid",
        source_url="https://f-droid.org/packages/ws.xsoh.etar/",
    )

    try:
        provider.resolve_latest_release(
            app_definition,
            StubHttpClient('<html><body><a href="/F-Droid.apk">DOWNLOAD F-DROID</a></body></html>'),
        )
    except ValueError as exc:
        assert "could not find an F-Droid APK release" in str(exc)
    else:
        raise AssertionError("expected ValueError when no package APK entry is present")