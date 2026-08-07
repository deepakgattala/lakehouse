from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any

class MetadataProvider(ABC):
    provider_key: str

    @abstractmethod
    def capability_snapshot(self) -> dict[str, Any]: ...

    @abstractmethod
    def inventory(self, included_schemas: list[str] | None = None) -> dict[str, list[dict[str, Any]]]: ...

    @abstractmethod
    def close(self) -> None: ...
