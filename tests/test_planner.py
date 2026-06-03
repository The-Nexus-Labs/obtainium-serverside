from __future__ import annotations

from pathlib import Path

from obtainium_serverside.models import AppDefinition, InstalledApp, ResolvedRelease
from obtainium_serverside.planner import plan_updates, should_apply_pinned, should_update
from obtainium_serverside.providers.base import BaseProvider


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


class StubProvider(BaseProvider):
    def __init__(self, release: ResolvedRelease) -> None:
        self.release = release

    def resolve_latest_release(
        self, app_definition: AppDefinition, http_client: StubHttpClient
    ) -> ResolvedRelease:
        return self.release

    def resolve_pinned_release(
        self, app_definition: AppDefinition, http_client: StubHttpClient, version: str
    ) -> ResolvedRelease:
        return self.release


class LatestOnlyProvider(BaseProvider):
    """Mirrors a provider that has not implemented version pinning yet."""

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


def test_should_apply_pinned_covers_hold_upgrade_and_downgrade() -> None:
    assert should_apply_pinned(target_version="2.4.3", installed_version=None)
    assert should_apply_pinned(target_version="2.4.3", installed_version="")
    assert not should_apply_pinned(target_version="2.4.3", installed_version="2.4.3")
    assert should_apply_pinned(target_version="2.4.3", installed_version="2.4.2")
    # downgrade: installed is newer than the pin
    assert should_apply_pinned(target_version="2.4.3", installed_version="2.5.0")


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


def _plan_pinned(
    monkeypatch, *, pinned_version: str, installed_version: str | None, tmp_path: Path | None = None
):
    release = ResolvedRelease(
        version=pinned_version,
        download_url=f"https://github.com/bitfireAT/icsx5/releases/download/v{pinned_version}/icsx5.apk",
        release_name=f"v{pinned_version}",
    )
    monkeypatch.setattr(
        "obtainium_serverside.planner.get_provider",
        lambda _provider_name: StubProvider(release),
    )
    return plan_updates(
        [
            AppDefinition(
                app_id="at.bitfire.icsdroid",
                provider="github",
                source_url="https://github.com/bitfireAT/icsx5/releases",
                name="ICSx5",
                version=pinned_version,
            )
        ],
        [InstalledApp(app_id="at.bitfire.icsdroid", version=installed_version)],
        download_dir=tmp_path,
        http_client=StubHttpClient(),
    )


def test_plan_updates_pinned_equal_installed_is_skipped(monkeypatch) -> None:
    result = _plan_pinned(monkeypatch, pinned_version="2.4.3", installed_version="2.4.3")

    assert result.errors == []
    assert result.updates == []


def test_plan_updates_pinned_newer_than_installed_updates(monkeypatch) -> None:
    result = _plan_pinned(monkeypatch, pinned_version="2.4.3", installed_version="2.4.1")

    assert result.errors == []
    assert len(result.updates) == 1
    assert result.updates[0].pinned is True
    assert result.updates[0].latest_version == "2.4.3"
    assert result.updates[0].to_dict()["pinned"] is True


def test_plan_updates_pinned_older_than_installed_downgrades(monkeypatch) -> None:
    result = _plan_pinned(monkeypatch, pinned_version="2.4.3", installed_version="2.6.0")

    assert result.errors == []
    assert len(result.updates) == 1
    assert result.updates[0].pinned is True
    assert result.updates[0].installed_version == "2.6.0"
    assert result.updates[0].latest_version == "2.4.3"


def test_plan_updates_without_version_keeps_latest_behavior(monkeypatch) -> None:
    release = ResolvedRelease(
        version="16.2.1",
        download_url="https://updatefiles.loxone.com/Android/Release/162115280.apk",
    )
    monkeypatch.setattr(
        "obtainium_serverside.planner.get_provider",
        lambda _provider_name: StubProvider(release),
    )

    # Installed is newer than the resolved latest: latest-only mode must not downgrade.
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


def test_plan_updates_pin_on_provider_without_support_errors(monkeypatch) -> None:
    release = ResolvedRelease(
        version="2.4.3",
        download_url="https://example.com/app.apk",
    )
    monkeypatch.setattr(
        "obtainium_serverside.planner.get_provider",
        lambda _provider_name: LatestOnlyProvider(release),
    )

    result = plan_updates(
        [
            AppDefinition(
                app_id="at.bitfire.icsdroid",
                provider="github",
                source_url="https://github.com/bitfireAT/icsx5/releases",
                version="2.4.3",
            )
        ],
        [InstalledApp(app_id="at.bitfire.icsdroid", version="2.4.1")],
        http_client=StubHttpClient(),
    )

    assert result.updates == []
    assert len(result.errors) == 1
    assert "does not support version pinning" in result.errors[0].message
