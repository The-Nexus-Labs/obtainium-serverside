from __future__ import annotations

import os
import shutil
import urllib.request
from pathlib import Path
from typing import cast
from urllib.parse import urlparse

GITHUB_TOKEN_ENV_NAMES = (
    "DEPENDENCY_UPDATE_GITHUB_TOKEN",
    "GITHUB_TOKEN",
    "GH_TOKEN",
)

GITHUB_API_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


class HttpClient:
    def __init__(
        self,
        *,
        timeout: int = 30,
        user_agent: str = "obtainium-serverside/0.1",
        github_token: str | None = None,
    ) -> None:
        self.timeout = timeout
        self.user_agent = user_agent
        self.github_token = github_token

    def get_text(self, url: str) -> str:
        request = urllib.request.Request(url, headers=self._headers_for_url(url))
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            charset = response.headers.get_content_charset("utf-8")
            return cast(bytes, response.read()).decode(charset, errors="replace")

    def download_file(self, url: str, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(url, headers=self._headers_for_url(url))
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            with destination.open("wb") as handle:
                shutil.copyfileobj(response, handle)
        return destination

    def _headers_for_url(self, url: str) -> dict[str, str]:
        headers = {"User-Agent": self.user_agent}
        if _is_github_api_url(url):
            headers.update(GITHUB_API_HEADERS)
            token = self.github_token or _resolve_github_token_from_env()
            if token:
                headers["Authorization"] = f"Bearer {token}"
        return headers


def _is_github_api_url(url: str) -> bool:
    return urlparse(url).netloc.lower() == "api.github.com"


def _resolve_github_token_from_env() -> str | None:
    for env_name in GITHUB_TOKEN_ENV_NAMES:
        token = os.environ.get(env_name)
        if token:
            return token
    return None
