"""OpenRouter chat client (stdlib-only, no SDK required).

OpenRouter exposes an OpenAI-compatible API for many models (including free
ones). This client uses the standard library (``urllib`` + ``json``) so it adds
no install burden — it only needs network + an API key at runtime.

Set the key via environment / ``.env`` (either name works)::

    OPENROUTER_API_KEY=sk-or-...
    # or the lowercase variant some setups use:
    open_router_api_key=sk-or-...

Config::

    [agents]
    llm = "openrouter"
    model = "tencent/hy3:free"     # any OpenRouter model id
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from alphaagent.llm.base import LLMClient, llms

_KEY_ENV_CANDIDATES = ("OPENROUTER_API_KEY", "open_router_api_key")
_DEFAULT_MODEL = "tencent/hy3:free"


def _api_key() -> str | None:
    for name in _KEY_ENV_CANDIDATES:
        val = os.environ.get(name)
        if val:
            return val.strip()
    return None


@llms.register("openrouter")
class OpenRouterClient(LLMClient):
    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        reasoning: bool = False,
        timeout: float = 60.0,
        **config,
    ) -> None:
        super().__init__(**config)
        self.model = model or _DEFAULT_MODEL
        self.base_url = (base_url or "https://openrouter.ai/api/v1").rstrip("/")
        self.reasoning = reasoning
        self.timeout = timeout

    def chat(self, system: str, user: str) -> str:
        key = _api_key()
        if not key:
            raise RuntimeError(
                "OpenRouter API key not set; export OPENROUTER_API_KEY "
                "(or open_router_api_key), or use the offline 'mock' LLM"
            )

        payload: dict = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
        }
        if self.reasoning:
            payload["reasoning"] = {"enabled": True}

        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:  # pragma: no cover - network
            body = exc.read().decode(errors="replace")[:300]
            raise RuntimeError(f"OpenRouter HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:  # pragma: no cover - network
            raise RuntimeError(f"OpenRouter request failed: {exc.reason}") from exc

        return data["choices"][0]["message"].get("content") or ""
