"""
werkzeug
~~~~~~~~

Werkzeug is the Swiss Army knife of Python web development.

It provides useful classes and functions for any WSGI application to
make the life of a python web developer much easier. All of the provided
classes are independent from each other so you can mix it with any other
library.

:copyright: 2007 Pallets
:license: BSD-3-Clause
"""
from . import exceptions
from . import routing
from ._internal import _easteregg
from .datastructures import Accept
from .datastructures import Authorization
from .datastructures import CallbackDict
from .datastructures import CharsetAccept
from .datastructures import CombinedMultiDict
from .datastructures import EnvironHeaders
from .datastructures import ETags
from .datastructures import FileMultiDict
from .datastructures import FileStorage
from .datastructures import Headers
from .datastructures import HeaderSet
from .datastructures import ImmutableDict
from .datastructures import ImmutableList
from .datastructures import ImmutableMultiDict
from .datastructures import ImmutableOrderedMultiDict
from .datastructures import ImmutableTypeConversionDict
from .datastructures import LanguageAccept
from .datastructures import MIMEAccept
from .datastructures import MultiDict
from .datastructures import OrderedMultiDict
from .datastructures import RequestCacheControl
from .datastructures import ResponseCacheControl
from .datastructures import TypeConversionDict
from .datastructures import WWWAuthenticate
from .debug import DebuggedApplication
from .exceptions import abort
from .exceptions import Aborter
from .formparser import parse_form_data
from .http import cookie_date
from .http import dump_cookie
from .http import dump_header
from .http import dump_options_header
from .http import generate_etag
from .http import http_date
from .http import HTTP_STATUS_CODES
from .http import is_entity_header
from .http import is_hop_by_hop_header
from .http import is_resource_modified
from .http import parse_accept_header
from .http import parse_authorization_header
from .http import parse_cache_control_header
from .http import parse_cookie
from .http import parse_date
from .http import parse_dict_header
from .http import parse_etags
from .http import parse_list_header
from .http import parse_options_header
from .http import parse_set_header
from .http import parse_www_authenticate_header
from .http import quote_etag
from .http import quote_header_value
from .http import remove_entity_headers
from .http import remove_hop_by_hop_headers
from .http import unquote_etag
from .http import unquote_header_value
from .local import Local
from .local import LocalManager
from .local import LocalProxy
from .local import LocalStack
from .local import release_local
from .middleware.dispatcher import DispatcherMiddleware
from .middleware.shared_data import SharedDataMiddleware
from .security import check_password_hash
from .security import generate_password_hash
from .serving import run_simple
from .test import Client
from .test import create_environ
from .test import EnvironBuilder
from .test import run_wsgi_app
from .testapp import test_app
from .urls import Href
from .urls import iri_to_uri
from .urls import uri_to_iri
from .urls import url_decode
from .urls import url_encode
from .urls import url_fix
from .urls import url_quote
from .urls import url_quote_plus
from .urls import url_unquote
from .urls import url_unquote_plus
from .useragents import UserAgent
from .utils import append_slash_redirect
from .utils import ArgumentValidationError
from .utils import bind_arguments
from .utils import cached_property
from .utils import environ_property
from .utils import escape
from .utils import find_modules
from .utils import format_string
from .utils import header_property
from .utils import html
from .utils import HTMLBuilder
from .utils import import_string
from .utils import redirect
from .utils import secure_filename
from .utils import unescape
from .utils import validate_arguments
from .utils import xhtml
from .wrappers import AcceptMixin
from .wrappers import AuthorizationMixin
from .wrappers import BaseRequest
from .wrappers import BaseResponse
from .wrappers import CommonRequestDescriptorsMixin
from .wrappers import CommonResponseDescriptorsMixin
from .wrappers import ETagRequestMixin
from .wrappers import ETagResponseMixin
from .wrappers import Request
from .wrappers import Response
from .wrappers import ResponseStreamMixin
from .wrappers import UserAgentMixin
from .wrappers import WWWAuthenticateMixin
from .wsgi import ClosingIterator
from .wsgi import extract_path_info
from .wsgi import FileWrapper
from .wsgi import get_current_url
from .wsgi import get_host
from .wsgi import LimitedStream
from .wsgi import make_line_iter
from .wsgi import peek_path_info
from .wsgi import pop_path_info
from .wsgi import responder
from .wsgi import wrap_file

__version__ = "1.0.0.dev0"
