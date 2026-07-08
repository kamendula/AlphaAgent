"""Collaboration policies. Each module registers itself on import."""

from alphaagent.agents.policies import panel as _panel  # noqa: F401
from alphaagent.agents.policies import vote as _vote  # noqa: F401
from alphaagent.agents.policies import llm_judge as _llm_judge  # noqa: F401
from alphaagent.agents.policies import debate as _debate  # noqa: F401
