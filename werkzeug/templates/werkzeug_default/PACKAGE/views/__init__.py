# -*- coding: <%= FILE_ENCODING %> -*-

def get_view(name):
    module, callback = name.split('/', 1)
    m = __import__('<%= PACKAGE %>.views.%s' % module, None, None, [callback])
    return getattr(m, callback)
