# -*- coding: <%= FILE_ENCODING %> -*-
<%= make_docstring(MODULE, '''\
Use this module to point from the abstract URL map to the view callback
functions in the `views` module. Note that you can only have one slash, thus
one depth for the callbacks (``module/callback``) and that slashes are used
to separate module and view.''') %>
from werkzeug.routing import Map, Rule

#: url definitions
url_map = Map([
    Rule('/', endpoint='default/index')
])

#: endpoint for the not found page
not_found = 'default/not_found'
