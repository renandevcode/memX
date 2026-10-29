"""Minimal asynchronous storage boundary used by the application services."""

from collections.abc import Mapping
from contextlib import AbstractAsyncContextManager
from typing import Any, Protocol


class Session(Protocol):
    async def __aenter__(self) -> "Session": ...

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None: ...

    def begin(self) -> AbstractAsyncContextManager[Any]: ...

    async def execute(self, query: str, params: Mapping[str, Any] | None = None) -> Any: ...


class Store(Protocol):
    def session_factory(self) -> Session: ...

    async def dispose(self) -> None: ...


def text(query: str) -> str:
    """Keep SQL templates independent of a particular driver's query object."""
    return query
