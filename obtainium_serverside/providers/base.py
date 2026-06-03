from __future__ import annotations

from abc import ABC, abstractmethod

from obtainium_serverside.http import HttpClient
from obtainium_serverside.models import AppDefinition, ResolvedRelease


class BaseProvider(ABC):
    @abstractmethod
    def resolve_latest_release(
        self, app_definition: AppDefinition, http_client: HttpClient
    ) -> ResolvedRelease:
        raise NotImplementedError

    def resolve_release(
        self, app_definition: AppDefinition, http_client: HttpClient
    ) -> ResolvedRelease:
        """Resolve the release to install: the pinned version if one is declared,
        otherwise the latest upstream release."""
        if not app_definition.version:
            return self.resolve_latest_release(app_definition, http_client)
        return self.resolve_pinned_release(app_definition, http_client, app_definition.version)

    def resolve_pinned_release(
        self, app_definition: AppDefinition, http_client: HttpClient, version: str
    ) -> ResolvedRelease:
        raise ValueError(f"provider {app_definition.provider} does not support version pinning")
