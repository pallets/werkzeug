# -*- coding: utf-8 -*-

import sys
from subprocess import Popen, PIPE


import_code = '''\
import sys
sys.path.insert(0, '..')
import werkzeug.%s
print ':'.join([k[9:] for k, v in sys.modules.iteritems()
                if v is not None and k.startswith('werkzeug.')])
'''


def perform_import(module, allowed):
    client = Popen([sys.executable, '-c', import_code % module],
                   stdout=PIPE)
    imported = set(client.communicate()[0].strip().split(':'))
    rv = imported - allowed - set([module])
    print 'leftovers from %r import: %s' % (module, rv)
    return rv


def test_old_imports():
    """Make sure everything imports from old places"""
    from werkzeug.utils import Headers, MultiDict, CombinedMultiDict, \
         Headers, EnvironHeaders
    from werkzeug.http import Accept, MIMEAccept, CharsetAccept, \
         LanguageAccept, ETags, HeaderSet, WWWAuthenticate, \
         Authorization


def test_exposed_werkzeug_mod():
    """Make sure all public classes are from the werkzeug module."""
    import werkzeug
    wrong_modules = []
    for key in werkzeug.__all__:
        obj = getattr(werkzeug, key)
        if isinstance(obj, type) and obj.__module__ != 'werkzeug':
            wrong_modules.append(obj)

    if wrong_modules:
        print 'objects with wrong modules: %s' % ', '.join(
            (x.__module__ + '.' + x.__name__ for x in wrong_modules))
        assert False, 'found objects with __module__ not set to werkzeug'


def test_demand_import():
    """Make sure that we're not importing too much."""
    allowed_imports = set(['_internal', 'utils', 'http', 'exceptions',
                           'datastructures'])

    assert perform_import('http', allowed_imports) == set()
    assert perform_import('utils', allowed_imports) == set()

    allowed_imports.update(('urls', 'formparser', 'wsgi'))
    assert perform_import('wrappers', allowed_imports) == set()

    allowed_imports.add('wrappers')
    assert perform_import('useragents', allowed_imports) == set()
    assert perform_import('test', allowed_imports) == set()
    assert perform_import('serving', allowed_imports) == set()


def test_fix_headers_in_response():
    """Make sure fix_headers still works for backwards compatibility"""
    from werkzeug import Response
    class MyResponse(Response):
        def fix_headers(self, environ):
            Response.fix_headers(self, environ)
            self.headers['x-foo'] = "meh"
    myresp = MyResponse('Foo')
    resp = Response.from_app(myresp, {'REQUEST_METHOD': 'GET'})
    assert resp.headers['x-foo'] == 'meh'
    assert resp.data == 'Foo'
