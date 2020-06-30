"""
Types which Werkzeug uses.

Do not depend on these externally
"""
from typing import Any
from typing import Dict
from typing import TypeVar
from typing import Union

BytesOrStr = Union[bytes, str]
# A value which can be encoded using Unicode.
UnicodeEncodable = Union[bytes, str, int]

# a generic type parameter used in many functions
T = TypeVar("T")
# a number (either floating point or an integer)
Number = TypeVar("Number", int, float)

# A WSGI environment
# TODO: At some point it may be possible to replace this with a
# `TypedDict` from the `typing` module. At present (21.06.2020)
# this isn't possible because `TypedDict` is only available on
# Python 3.8+
WSGIEnvironment = Dict[str, Any]
