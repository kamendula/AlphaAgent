"""The LLMClient contract and its registry."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from alphaagent.core.registry import Registry

llms: Registry[type["LLMClient"]] = Registry("llm")


class LLMClient(ABC):
    """A minimal chat interface: system + user text in, text out.

    Deliberately tiny so any vendor (or a mock) can implement it. Agents ask for
    JSON in the prompt and parse the reply, keeping this surface vendor-neutral.
    """

    def __init__(self, **config: Any) -> None:
        self.config = config

    @abstractmethod
    def chat(self, system: str, user: str) -> str:
        """Return the assistant's reply to ``system``/``user`` as raw text."""
