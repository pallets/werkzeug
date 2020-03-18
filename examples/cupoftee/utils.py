import re


_sort_re = re.compile(r"\w+")


def unicodecmp(a, b):
    x, y = map(_sort_re.search, [a, b])
    x = (x.group() if x else a).lower()
    y = (y.group() if y else b).lower()
    return (x > y) - (x < y)
