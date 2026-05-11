from __future__ import annotations

import typing as t

from .accept import Accept as Accept
from .accept import LanguageAccept as LanguageAccept
from .accept import MIMEAccept as MIMEAccept
from .auth import Authorization as Authorization
from .auth import WWWAuthenticate as WWWAuthenticate
from .cache_control import RequestCacheControl as RequestCacheControl
from .cache_control import ResponseCacheControl as ResponseCacheControl
from .csp import ContentSecurityPolicy as ContentSecurityPolicy
from .etag import ETags as ETags
from .file_storage import FileMultiDict as FileMultiDict
from .file_storage import FileStorage as FileStorage
from .headers import EnvironHeaders as EnvironHeaders
from .headers import Headers as Headers
from .mixins import ImmutableDictMixin as ImmutableDictMixin
from .mixins import ImmutableHeadersMixin as ImmutableHeadersMixin
from .mixins import ImmutableMultiDictMixin as ImmutableMultiDictMixin
from .mixins import UpdateDictMixin as UpdateDictMixin
from .range import ContentRange as ContentRange
from .range import IfRange as IfRange
from .range import Range as Range
from .structures import CallbackDict as CallbackDict
from .structures import CombinedMultiDict as CombinedMultiDict
from .structures import HeaderSet as HeaderSet
from .structures import ImmutableDict as ImmutableDict
from .structures import ImmutableMultiDict as ImmutableMultiDict
from .structures import ImmutableTypeConversionDict as ImmutableTypeConversionDict
from .structures import iter_multi_items as iter_multi_items
from .structures import MultiDict as MultiDict
from .structures import TypeConversionDict as TypeConversionDict


def __getattr__(name: str) -> t.Any:
    if name == "CharsetAccept":
        import warnings

        from .accept import _CharsetAccept

        warnings.warn(
            "The 'CharsetAccept' class is deprecated and will be removed in"
            " Werkzeug 3.3. The 'Accept-Charset' header is not sent by"
            " browsers, and UTF-8 is assumed.",
            DeprecationWarning,
            stacklevel=2,
        )
        return _CharsetAccept

    from . import mixins
    from . import structures

    alts = {
        "ImmutableListMixin": (mixins, "collections.abc.Sequence"),
        "ImmutableList": (structures, "collections.abc.Sequence"),
    }

    if name in alts:
        import warnings

        mod, alt = alts[name]
        warnings.warn(
            f"The '{name}' class is deprecated and will be removed in"
            f" Werkzeug 3.3. Use '{alt}' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return getattr(mod, f"_{name}")

    raise AttributeError(name)
