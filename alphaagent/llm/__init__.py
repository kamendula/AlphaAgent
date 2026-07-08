"""LLM abstraction: a vendor-agnostic chat client behind a registry.

The demo path uses :class:`~alphaagent.llm.mock.MockLLM` — a deterministic,
offline stand-in — so the *agent* layer runs with zero keys and zero network,
just like the demo data provider. Real vendors are optional, lazily imported
plugins.
"""

from alphaagent.llm.base import LLMClient, llms

# Register built-ins (class definitions only; heavy imports stay lazy).
from alphaagent.llm import mock as _mock  # noqa: F401
from alphaagent.llm import openai_client as _openai  # noqa: F401
from alphaagent.llm import openrouter as _openrouter  # noqa: F401

__all__ = ["LLMClient", "llms"]
