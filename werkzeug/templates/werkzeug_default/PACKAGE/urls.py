# -*- coding: <%= FILE_ENCODING %> -*-
from werkzeug.routing import Map, Rule

#: url definitions
url_map = Map([
    Rule('/', endpoint='default/index')
])

#: endpoint for the not found page
not_found = 'default/not_found'
