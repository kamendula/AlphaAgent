import pytest

from alphaagent.core.registry import Registry


def test_register_and_get():
    reg: Registry[type] = Registry("thing")

    @reg.register("Foo")
    class Foo:
        pass

    assert "foo" in reg           # case-insensitive
    assert reg.get("FOO") is Foo  # normalized lookup
    assert reg.names() == ["foo"]


def test_duplicate_registration_raises():
    reg: Registry[type] = Registry("thing")

    @reg.register("dup")
    class A:
        pass

    with pytest.raises(ValueError):
        @reg.register("dup")
        class B:
            pass


def test_unknown_lookup_lists_available():
    reg: Registry[type] = Registry("thing")

    @reg.register("known")
    class K:
        pass

    with pytest.raises(KeyError) as exc:
        reg.get("missing")
    assert "known" in str(exc.value)
