import codecs

from werkzeug.http import parse_options_header, dump_options_header
from werkzeug.utils import cached_property


def is_known_charset(charset):
    """Checks if the given charset is known to Python."""
    try:
        codecs.lookup(charset)
    except LookupError:
        return False
    return True


class DynamicCharsetRequestMixin(object):

    """If this mixin is mixed into a request class it will provide
    a dynamic `charset` attribute.  This means that if the charset is
    transmitted in the content type headers it's used from there.

    Because it changes the behavior or :class:`Request` this class has
    to be mixed in *before* the actual request class::

        class MyRequest(DynamicCharsetRequestMixin, Request):
            pass

    By default the request object assumes that the URL charset is the
    same as the data charset.  If the charset varies on each request
    based on the transmitted data it's not a good idea to let the URLs
    change based on that.  Most browsers assume either utf-8 or latin1
    for the URLs if they have troubles figuring out.  It's strongly
    recommended to set the URL charset to utf-8::

        class MyRequest(DynamicCharsetRequestMixin, Request):
            url_charset = 'utf-8'

    .. versionadded:: 0.6
    """

    #: the default charset that is assumed if the content type header
    #: is missing or does not contain a charset parameter.  The default
    #: is latin1 which is what HTTP specifies as default charset.
    #: You may however want to set this to utf-8 to better support
    #: browsers that do not transmit a charset for incoming data.
    default_charset = 'latin1'

    def unknown_charset(self, charset):
        """Called if a charset was provided but is not supported by
        the Python codecs module.  By default latin1 is assumed then
        to not lose any information, you may override this method to
        change the behavior.

        :param charset: the charset that was not found.
        :return: the replacement charset.
        """
        return 'latin1'

    @cached_property
    def charset(self):
        """The charset from the content type."""
        header = self.environ.get('CONTENT_TYPE')
        if header:
            ct, options = parse_options_header(header)
            charset = options.get('charset')
            if charset:
                if is_known_charset(charset):
                    return charset
                return self.unknown_charset(charset)
        return self.default_charset


class DynamicCharsetResponseMixin(object):

    """If this mixin is mixed into a response class it will provide
    a dynamic `charset` attribute.  This means that if the charset is
    looked up and stored in the `Content-Type` header and updates
    itself automatically.  This also means a small performance hit but
    can be useful if you're working with different charsets on
    responses.

    Because the charset attribute is no a property at class-level, the
    default value is stored in `default_charset`.

    Because it changes the behavior or :class:`Response` this class has
    to be mixed in *before* the actual response class::

        class MyResponse(DynamicCharsetResponseMixin, Response):
            pass

    .. versionadded:: 0.6
    """

    #: the default charset.
    default_charset = 'utf-8'

    def _get_charset(self):
        header = self.headers.get('content-type')
        if header:
            charset = parse_options_header(header)[1].get('charset')
            if charset:
                return charset
        return self.default_charset

    def _set_charset(self, charset):
        header = self.headers.get('content-type')
        ct, options = parse_options_header(header)
        if not ct:
            raise TypeError('Cannot set charset if Content-Type '
                            'header is missing.')
        options['charset'] = charset
        self.headers['Content-Type'] = dump_options_header(ct, options)

    charset = property(_get_charset, _set_charset, doc="""
        The charset for the response.  It's stored inside the
        Content-Type header as a parameter.""")
    del _get_charset, _set_charset
