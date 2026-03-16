from __future__ import annotations

import shutil
import urllib.request
from pathlib import Path
from typing import cast


class HttpClient:
    def __init__(self, *, timeout: int = 30, user_agent: str = "obtainium-serverside/0.1") -> None:
        self.timeout = timeout
        self.user_agent = user_agent

    def get_text(self, url: str) -> str:
        request = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            charset = response.headers.get_content_charset("utf-8")
            return cast(bytes, response.read()).decode(charset, errors="replace")

    def download_file(self, url: str, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            with destination.open("wb") as handle:
                shutil.copyfileobj(response, handle)
        return destination
