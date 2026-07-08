"""Entry-rule tests, driven entirely by the offline demo provider."""

from alphaagent.core.models import AssetType, EntrySignal
from alphaagent.data.router import SymbolRouter
from alphaagent.entry import entry_rules

_VALID_ACTIONS = {"buy", "wait", "pass"}


def _router() -> SymbolRouter:
    return SymbolRouter(
        preference={AssetType.EQUITY: ["demo"], AssetType.CRYPTO: ["demo"]}, fallback=False
    )


def test_builtin_rules_are_registered():
    names = set(entry_rules.names())
    assert {"breakout", "pullback"} <= names


def test_rules_return_valid_entry_signal():
    router = _router()
    for rule_name in ("breakout", "pullback"):
        rule = entry_rules.get(rule_name)()
        for symbol in ("NVDA", "AMZN"):
            sig = rule.signal(symbol, router)
            assert isinstance(sig, EntrySignal)
            assert sig.symbol == symbol
            assert sig.action in _VALID_ACTIONS
            assert sig.rationale  # every decision explains itself
            if sig.action == "buy":
                # A buy must be sizable: a trigger and a stop below it.
                assert sig.trigger_price is not None
                assert sig.stop_hint is not None
                assert sig.stop_hint < sig.trigger_price


def test_rule_respects_as_of_history():
    # An early as_of with little history should degrade gracefully to pass/wait,
    # never crash.
    from datetime import date

    router = _router()
    rule = entry_rules.get("breakout")()
    sig = rule.signal("NVDA", router, as_of=date(2024, 1, 15))
    assert sig.action in _VALID_ACTIONS


def test_rules_accept_config_overrides():
    router = _router()
    rule = entry_rules.get("breakout")(lookback=5, vol_mult=1.0, atr_mult=1.5)
    sig = rule.signal("AMZN", router)
    assert isinstance(sig, EntrySignal)
    assert sig.action in _VALID_ACTIONS
