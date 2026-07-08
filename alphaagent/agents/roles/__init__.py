"""Built-in analyst roles. Each module registers itself on import."""

from alphaagent.agents.roles import fundamental as _fundamental  # noqa: F401
from alphaagent.agents.roles import risk as _risk  # noqa: F401
from alphaagent.agents.roles import sentiment as _sentiment  # noqa: F401
from alphaagent.agents.roles import technical as _technical  # noqa: F401
