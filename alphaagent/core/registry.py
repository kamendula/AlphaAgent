"""A tiny, typed plugin registry.

Every extension point in AlphaAgent — data providers, pool sources, quant
filters, agent roles, collaboration policies, entry rules — is a plugin
registered here. Adding a capability is *one file + one line*::

    from alphaagent.data import providers

    @providers.register("myexchange")
    class MyExchangeProvider(DataProvider):
        ...

The registry is deliberately minimal: a name -> object mapping with a
decorator, duplicate protection, and helpful lookup errors. That is the whole
contract contributors need to learn.
"""

from __future__ import annotations

from typing import Callable, Generic, Iterator, TypeVar

T = TypeVar("T")


class Registry(Generic[T]):
    """A named collection of plugins of a single kind.

    Parameters
    ----------
    kind:
        Human-readable label used in error messages (e.g. ``"data-provider"``).
    """

    def __init__(self, kind: str) -> None:
        self.kind = kind
        self._items: dict[str, T] = {}

    def register(self, name: str) -> Callable[[T], T]:
        """Decorator that registers ``obj`` under ``name`` and returns it unchanged."""

        key = _normalize(name)

        def decorator(obj: T) -> T:
            if key in self._items:
                raise ValueError(
                    f"{self.kind} {name!r} is already registered "
                    f"(as {self._items[key]!r})"
                )
            self._items[key] = obj
            return obj

        return decorator

    def get(self, name: str) -> T:
        """Look up a plugin by name, with a suggestive error if it is missing."""

        key = _normalize(name)
        try:
            return self._items[key]
        except KeyError:
            available = ", ".join(sorted(self._items)) or "<none>"
            raise KeyError(
                f"unknown {self.kind} {name!r}; available: {available}"
            ) from None

    def names(self) -> list[str]:
        return sorted(self._items)

    def __contains__(self, name: str) -> bool:
        return _normalize(name) in self._items

    def __iter__(self) -> Iterator[str]:
        return iter(sorted(self._items))

    def __len__(self) -> int:
        return len(self._items)

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"Registry({self.kind!r}, {self.names()!r})"


def _normalize(name: str) -> str:
    return name.strip().lower()
