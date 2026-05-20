from __future__ import annotations

from .base import BaseProvider
from .fdroid import FDroidProvider
from .github import GitHubReleasesProvider
from .loxone import LoxoneProvider

PROVIDER_REGISTRY: dict[str, BaseProvider] = {
    "fdroid": FDroidProvider(),
    "github": GitHubReleasesProvider(),
    "loxone": LoxoneProvider(),
}


def get_provider(name: str) -> BaseProvider:
    try:
        return PROVIDER_REGISTRY[name]
    except KeyError as exc:
        raise ValueError(f"unknown provider: {name}") from exc
