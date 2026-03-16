from __future__ import annotations

from pathlib import Path

from obtainium_serverside.models import AppDefinition, InstalledApp, ResolvedRelease
from obtainium_serverside.planner import plan_updates, should_update


class StubHttpClient:
    def __init__(self) -> None:
        self.downloads: list[tuple[str, Path]] = []

    def get_text(self, url: str) -> str:
        return "unused"

    def download_file(self, url: str, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"apk")
        self.downloads.append((url, destination))
        return destination


class StubProvider:
    def __init__(self, release: ResolvedRelease) -> None:
        self.release = release

    def resolve_latest_release(
        self, app_definition: AppDefinition, http_client: StubHttpClient
    ) -> ResolvedRelease:
        return self.release


def test_should_update_for_missing_or_older_versions() -> None:
    assert should_update(latest_version="16.2.2", installed_version=None)
    assert should_update(latest_version="16.2.2", installed_version="16.2.1")
    assert not should_update(latest_version="16.2.2", installed_version="16.2.2")


def test_plan_updates_downloads_only_required_apps(monkeypatch, tmp_path: Path) -> None:
    release = ResolvedRelease(
        version="16.2.2",
        download_url="https://updatefiles.loxone.com/Android/Release/162215280.apk",
        release_name="Loxone App 16.2.2 for Android",
    )
    stub_provider = StubProvider(release)
    http_client = StubHttpClient()

    monkeypatch.setattr(
        "obtainium_serverside.planner.get_provider",
        lambda _provider_name: stub_provider,
    )

    result = plan_updates(
        [
            AppDefinition(
                app_id="com.loxone.kerberos",
                provider="loxone",
                source_url="https://www.loxone.com/enus/support/downloads/",
                name="Loxone App",
            )
        ],
        [InstalledApp(app_id="com.loxone.kerberos", version="16.2.1")],
        download_dir=tmp_path,
        http_client=http_client,
    )

    assert result.errors == []
    assert len(result.updates) == 1
    assert result.updates[0].latest_version == "16.2.2"
    assert result.updates[0].downloaded_apk_path is not None
    assert Path(result.updates[0].downloaded_apk_path).exists()
    assert (
        http_client.downloads[0][0]
        == "https://updatefiles.loxone.com/Android/Release/162215280.apk"
    )


def test_plan_updates_skips_up_to_date_apps(monkeypatch) -> None:
    release = ResolvedRelease(
        version="16.2.2",
        download_url="https://updatefiles.loxone.com/Android/Release/162215280.apk",
    )
    stub_provider = StubProvider(release)

    monkeypatch.setattr(
        "obtainium_serverside.planner.get_provider",
        lambda _provider_name: stub_provider,
    )

    result = plan_updates(
        [
            AppDefinition(
                app_id="com.loxone.kerberos",
                provider="loxone",
                source_url="https://www.loxone.com/enus/support/downloads/",
            )
        ],
        [InstalledApp(app_id="com.loxone.kerberos", version="16.2.2")],
        http_client=StubHttpClient(),
    )

    assert result.errors == []
    assert result.updates == []
