from __future__ import annotations

from obtainium_serverside.http import HttpClient


def test_http_client_adds_github_headers_with_explicit_token(monkeypatch) -> None:
    monkeypatch.delenv("DEPENDENCY_UPDATE_GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)

    headers = HttpClient(github_token="secret-token")._headers_for_url(
        "https://api.github.com/repos/example/project/releases"
    )

    assert headers["Accept"] == "application/vnd.github+json"
    assert headers["X-GitHub-Api-Version"] == "2022-11-28"
    assert headers["Authorization"] == "Bearer secret-token"


def test_http_client_adds_github_token_from_environment(monkeypatch) -> None:
    monkeypatch.delenv("DEPENDENCY_UPDATE_GITHUB_TOKEN", raising=False)
    monkeypatch.setenv("GITHUB_TOKEN", "env-token")
    monkeypatch.setenv("GH_TOKEN", "lower-priority-token")

    headers = HttpClient()._headers_for_url("https://api.github.com/repos/example/project/releases")

    assert headers["Authorization"] == "Bearer env-token"


def test_http_client_does_not_send_github_token_to_non_api_urls(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "env-token")

    headers = HttpClient()._headers_for_url(
        "https://github.com/example/project/releases/download/v1/app.apk"
    )

    assert "Authorization" not in headers
    assert "Accept" not in headers
    assert "X-GitHub-Api-Version" not in headers
