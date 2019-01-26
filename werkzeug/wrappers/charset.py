import codecs

from ..http import parse_options_header
from ..utils import cached_property


class DynamicCharsetRequestMixin(object):
    """Take the charset attribute from the the ``Content-Type`` header.
    Overrides the default behavior of hard-coding UTF-8. This is used
    when decoding the data in the response body.

    .. warning::
        It may be dangerous to decode with a user-supplied charset
        without validation in Python. Be absolutely sure you understand
        the security implications of this before using it.

        See :meth:`is_safe_charset`.
    """

    #: The default charset that is assumed if the content type header
    #: is missing or does not contain a charset parameter.
    #:
    #: ..versionchanged:: 0.15
    #:     Set to "utf-8" rather than "latin1", which matches
    #:     :class:`~werkzeug.wrappers.BaseRequest`.
    default_charset = "utf-8"

    #: Use this charset for URL decoding rather than :attr:`charset`,
    #: since that now refers to the data's charset, not the URL's.
    #:
    #: ..versionchanged:: 0.15
    #:     Set to "utf-8" rather than keeping the base
    #:     :attr:`~werkzeug.wrappers.BaseRequest.url_charset` behavior.
    url_charset = "utf-8"

    def unknown_charset(self, charset):
        """Called if a charset was provided but :meth:`is_safe_charset`
        returned ``False``.

        :param charset: The unsafe charset.
        :return: The replacement charset.

        .. versionchanged:: 0.15
            Returns "utf-8" rather than "latin1", matching
            :attr:`default_charset`.
        """
        return "utf-8"

    @cached_property
    def charset(self):
        """The charset from the content type."""
        charset = self.mimetype_params.get("charset")

        if charset:
            if self.is_safe_charset(charset):
                return charset

            return self.unknown_charset(charset)

        return self.default_charset

    def is_safe_charset(self, charset):
        """Whether the given charset is safe to use for decoding request
        data.

        .. warning::
            Due to the way Python implements codecs, the only 100% safe
            implementation is checking against a whitelist you maintain.

        By default this calls :func:`codecs.lookup` then checks
        ``_is_text_encoding`` on the returned info. This will exclude
        charsets such as "zip" that should not be used to decode
        untrusted data. However, this check may still be unsafe if other
        libraries you use register binary codecs and don't set that
        internal attribute correctly.

        .. versionadded:: 0.15
            Previously, :attr:`charset` only checked that the charset
            was known, not that it was a text charset.
        """
        try:
            info = codecs.lookup(charset)
        except LookupError:
            return False

        return info._is_text_encoding


class DynamicCharsetResponseMixin(object):
    """Allow setting the charset for a response after creating it.
    Setting a new charset updates the ``Content-Type`` header.

    If the response already has data set, it is not re-encoded. Text
    data can be set with the new charset using
    :meth:`~werkzeug.wrappers.BaseResponse.set_data`.

    This might be useful in some cases, but it's more efficient to
    pass the data and charset when creating the response.
    """

    #: The default charset that is assumed if the content type header
    #: is missing or does not contain a charset parameter.
    default_charset = "utf-8"

    @property
    def charset(self):
        """The charset for the response. It's stored as a parameter of
        the ``Content-Type`` header.
        """
        header = self.headers.get("content-type")

        if header:
            charset = parse_options_header(header)[1].get("charset")

            if charset:
                return charset

        return self.default_charset

    @charset.setter
    def charset(self, charset):
        header = self.headers.get("content-type")
        ct, options = parse_options_header(header)

        if not ct:
            raise TypeError("Cannot set charset if Content-Type header is missing.")

        options["charset"] = charset
        self.headers.set("content-type", ct, **options)
