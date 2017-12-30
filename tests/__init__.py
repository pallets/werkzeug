def strict_eq(x, y):
    """Equality test bypassing the implicit string conversion in
    Python 2."""
    __tracebackhide__ = True
    assert x == y, (x, y)
    assert issubclass(type(x), type(y)) or issubclass(type(y), type(x))
    if isinstance(x, dict) and isinstance(y, dict):
        x = sorted(x.items())
        y = sorted(y.items())
    elif isinstance(x, set) and isinstance(y, set):
        x = sorted(x)
        y = sorted(y)
    assert repr(x) == repr(y), (x, y)
