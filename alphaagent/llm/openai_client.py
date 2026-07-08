"""OpenAI-compatible chat client (optional, lazily imported).

Works with OpenAI and any OpenAI-compatible endpoint (set ``base_url``). Install
with ``pip install openai`` and set ``OPENAI_API_KEY`` (or put it in ``.env``).

Config::

    [agents]
    llm = "openai"
    model = "gpt-4o-mini"
"""

from __future__ import annotations

import os

from alphaagent.llm.base import LLMClient, llms


@llms.register("openai")
class OpenAIClient(LLMClient):
    def __init__(self, model: str | None = None, base_url: str | None = None, **config):
        super().__init__(**config)
        self.model = model or "gpt-4o-mini"
        self.base_url = base_url
        self._client = None

    def _ensure_client(self):
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:  # pragma: no cover - env-dependent
                raise RuntimeError(
                    "openai is not installed; run `pip install openai` "
                    "or use the offline 'mock' LLM"
                ) from exc
            if not os.environ.get("OPENAI_API_KEY"):
                raise RuntimeError("OPENAI_API_KEY is not set (env or .env)")
            self._client = OpenAI(base_url=self.base_url)
        return self._client

    def chat(self, system: str, user: str) -> str:  # pragma: no cover - network
        client = self._ensure_client()
        resp = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
        )
        return resp.choices[0].message.content or ""
