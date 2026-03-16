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
