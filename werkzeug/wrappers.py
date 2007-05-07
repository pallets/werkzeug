# -*- coding: utf-8 -*-
"""
    werkzeug.wrappers
    ~~~~~~~~~~~~~~~~~

    This module provides simple wrappers around `environ` and
    `start_response`.

    :copyright: 2007 by Armin Ronacher, Georg Brandl.
    :license: BSD, see LICENSE for more details.
"""
import cgi
import email
import urllib
import posixpath
from time import gmtime
from Cookie import SimpleCookie
from cStringIO import StringIO
from datetime import datetime
from email.Message import Message as MessageType

from werkzeug.constants import HTTP_STATUS_CODES
from werkzeug.utils import MultiDict, CombinedMultiDict, FieldStorage, \
     Headers, lazy_property


class BaseRequest(object):
    """
    Base Request class.
    """
    charset = 'ascii'

    def __init__(self, environ):
        self.environ = environ
        self.environ['werkzeug.request'] = self

    def _handle_file_upload(self, name, filename, content_type, payload):
        """You can override this to change the way uploads are handled."""
        return FieldStorage(name, filename, content_type, payload)

    def _load_post_data(self):
        """Method used internally to retrieve submitted data."""
        self._data = ''
        post = []
        files = []
        if self.environ['REQUEST_METHOD'] in ('POST', 'PUT'):
            maxlen = int(self.environ['CONTENT_LENGTH'])
            self._data = self.environ['wsgi.input'].read(maxlen)
            if self.environ.get('CONTENT_TYPE', '').startswith('multipart'):
                lines = ['Content-Type: %s' %
                         self.environ.get('CONTENT_TYPE', '')]
                for key, value in self.environ.items():
                    if key.startswith('HTTP_'):
                        lines.append('%s: %s' % (key, value))
                raw = '\r\n'.join(lines) + '\r\n\r\n' + self._data
                msg = email.message_from_string(raw)
                for sub in msg.get_payload():
                    if not isinstance(sub, MessageType):
                        continue
                    name_dict = cgi.parse_header(sub['Content-Disposition'])[1]
                    if 'filename' in name_dict:
                        payload = sub.get_payload()
                        filename = name_dict['filename']
                        if isinstance(payload, list) or not filename.strip():
                            continue
                        filename = name_dict['filename']
                        # fixes stupid ie bug but can cause problems
                        filename = filename[filename.rfind('\\') + 1:]
                        if 'Content-Type' in sub:
                            content_type = sub['Content-Type']
                        else:
                            content_type = None
                        fs = self._handle_file_upload(name_dict['name'], filename,
                                                      content_type, payload)
                        files.append(name_dict['name'], fs)
                    else:
                        value = sub.get_payload()
                        value = value.decode(self.charset, 'ignore')
                        post.append(name_dict['name'], value)
            else:
                d = cgi.parse_qs(self._data, True)
                for key, values in d.iteritems():
                    for value in values:
                        value = value.decode(self.charset, 'ignore')
                        post.append((key, value))
        self._form = MultiDict(post)
        self._files = MultiDict(files)

    def read(self, *args):
        if not hasattr(self, '_buffered_stream'):
            self._buffered_stream = StringIO(self.data)
        return self._buffered_stream.read(*args)

    def readline(self, *args):
        if not hasattr(self, '_buffered_stream'):
            self._buffered_stream = StringIO(self.data)
        return self._buffered_stream.readline(*args)

    def args(self):
        """URL parameters"""
        items = []
        qs = self.environ.get('QUERY_STRING', '')
        for key, values in cgi.parse_qs(qs, True).iteritems():
            for value in values:
                value = value.decode(self.charset, 'ignore')
                items.append((key, value))
        return MultiDict(items)
    args = lazy_property(args)

    def data(self):
        """raw value of input stream."""
        if not hasattr(self, '_data'):
            self._load_post_data()
        return self._data
    data = lazy_property(data)

    def form(self):
        """form parameters."""
        if not hasattr(self, '_form'):
            self._load_post_data()
        return self._form
    form = lazy_property(form)

    def values(self):
        """combined multi dict for `args` and `form`"""
        return CombinedMultiDict([self.args, self.form])
    values = lazy_property(values)

    def files(self):
        """File uploads."""
        if not hasattr(self, '_files'):
            self._load_post_data()
        return self._files
    files = lazy_property(files)

    def cookies(self):
        """Stored Cookies."""
        cookie = SimpleCookie()
        cookie.load(self.environ.get('HTTP_COOKIE', ''))
        return cookie
    cookies = lazy_property(cookies)

    def method(self):
        """Request method."""
        return self.environ['REQUEST_METHOD']
    method = lazy_property(method)

    def path(self):
        """Requested path."""
        path = '/' + (self.environ.get('PATH_INFO') or '').lstrip('/')
        path = path.decode(self.charset, self.charset)
        return path
    path = lazy_property(path)

    def get_debugging_vars(self):
        retvars = []
        for varname in dir(self):
            if varname[0] == '_': continue
            value = getattr(self, varname)
            if hasattr(value, 'im_func'): continue
            retvars.append((varname, value))
        return retvars


class BaseResponse(object):
    """
    Base response class.
    """
    charset = 'ascii'

    def __init__(self, response=None, headers=None, status=200, mimetype=None):
        if response is None:
            self.response = []
        elif isinstance(response, basestring):
            self.response = [response]
        else:
            self.response = iter(response)
        if not headers:
            self.headers = Headers()
        elif isinstance(headers, Headers):
            self.headers = headers
        else:
            self.headers = Headers(headers)
        if mimetype is not None:
            if 'charset=' not in mimetype:
                mimetype += '; charset=' + self.charset
            self.headers.add('Content-Type', mimetype)
        elif 'Content-Type' not in self.headers:
            self.headers.add('Content-Type', 'text/plain; charset=' +
                             self.charset)
        self.status = status
        self._cookies = None

    def write(self, value):
        if not isinstance(self.response, list):
            raise RuntimeError('cannot write to streaming response')
        self.write = self.response.append
        self.response.append(value)

    def set_cookie(self, key, value='', max_age=None, expires=None,
                   path='/', domain=None, secure=None):
        if self._cookies is None:
            self._cookies = SimpleCookie()
        if isinstance(value, unicode):
            value = value.encode(self.charset)
        self._cookies[key] = value
        if max_age is not None:
            self._cookies[key]['max-age'] = max_age
        if expires is not None:
            if isinstance(expires, basestring):
                self._cookies[key]['expires'] = expires
                expires = None
            elif isinstance(expires, datetime):
                expires = expires.utctimetuple()
            elif not isinstance(expires, (int, long)):
                expires = gmtime(expires)
            else:
                raise ValueError('datetime or integer required')
            month = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul',
                     'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][expires.tm_mon - 1]
            day = ['Monday', 'Tuesday', 'Wednesday', 'Thursday',
                   'Friday', 'Saturday', 'Sunday'][expires.tm_wday]
            date = '%02d-%s-%s' % (
                expires.tm_mday, month, str(expires.tm_year)[-2:]
            )
            d = '%s, %s %02d:%02d:%02d GMT' % (day, date, expires.tm_hour,
                                               expires.tm_min, expires.tm_sec)
            self._cookies[key]['expires'] = d
        if not path is None:
            self._cookies[key]['path'] = path
        if not domain is None:
            self._cookies[key]['domain'] = domain
        if not secure is None:
            self._cookies[key]['secure'] = secure

    def delete_cookie(self, key):
        if self._cookies is None:
            self._cookies = SimpleCookie()
        if not key in self._cookies:
            self._cookies[key] = ''
        self._cookies[key]['max-age'] = 0

    def __call__(self, environ, start_response):
        headers = self.headers.to_list(self.charset)
        if self._cookies is not None:
            for morsel in self._cookies.values():
                headers.append(('Set-Cookie', morsel.output(header='')))
        status = '%d %s' % (self.status, HTTP_STATUS_CODES[self.status])

        charset = self.charset or 'ascii'
        start_response(status, headers)
        for item in self.response:
            if isinstance(item, unicode):
                yield item.encode(charset)
            else:
                yield str(item)
