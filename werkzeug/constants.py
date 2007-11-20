# -*- coding: utf-8 -*-
"""
    werkzeug.constants
    ~~~~~~~~~~~~~~~~~~

    Various werkzeug related constants.

    :copyright: 2007 by Armin Ronacher, Leif K-Brooks.
    :license: BSD, see LICENSE for more details.
"""


HTTP_STATUS_CODES = {
    100:    'Continue',
    101:    'Switching Protocols',
    102:    'Processing',
    200:    'OK',
    201:    'Created',
    202:    'Accepted',
    203:    'Non Authoritative Information',
    204:    'No Content',
    205:    'Reset Content',
    206:    'Partial Content',
    207:    'Multi Status',
    300:    'Multiple Choices',
    301:    'Moved Permanently',
    302:    'Found',
    303:    'See Other',
    304:    'Not Modified',
    305:    'Use Proxy',
    307:    'Temporary Redirect',
    400:    'Bad Request',
    401:    'Unauthorized',
    402:    'Payment Required',
    403:    'Forbidden',
    404:    'Not Found',
    405:    'Method Not Allowed',
    406:    'Not Acceptable',
    407:    'Proxy Authentication Required',
    408:    'Request Timeout',
    409:    'Conflict',
    410:    'Gone',
    411:    'Length Required',
    412:    'Precondition Failed',
    413:    'Request Entity Too Large',
    414:    'Request URI Too Long',
    415:    'Unsupported Media Type',
    416:    'Requested Range Not Satisfiable',
    417:    'Expectation Failed',
    422:    'Unprocessable Entity',
    423:    'Locked',
    424:    'Failed Dependency',
    426:    'Upgrade Required',
    449:    'Retry With',           # propritary MS extension
    500:    'Internal Server Error',
    501:    'Not Implemented',
    502:    'Bad Gateway',
    503:    'Service Unavailable',
    504:    'Gateway Timeout',
    505:    'HTTP Version Not Supported',
    507:    'Insufficient Storage',
    510:    'Not Extended'
}


JAVASCRIPT_ROUTING = u'''\
<% if name_parts: %>\
<% for idx in xrange(0, len(name_parts) - 1): %>\
if (typeof <%= '.'.join(name_parts[:idx + 1]) %> === 'undefined') \
<%= '.'.join(name_parts[:idx + 1]) %> = {};
<% end %>\
<%= '.'.join(name_parts) %> = <% end %>\
(function (server_name, script_name, subdomain, url_scheme) {
    var converters = [<%= ', '.join(converters) %>];
    var rules = <%= rules %>;
    function in_array(array, value) {
        if (array.indexOf != undefined) {
            return array.indexOf(value) != -1;
        }
        for (var i = 0; i < array.length; i++) {
            if (array[i] == value) {
                return true;
            }
        }
        return false;
    }
    function array_diff(array1, array2) {
        array1 = array1.slice();
        for (var i = array1.length-1; i >= 0; i--) {
            if (in_array(array2, array1[i])) {
                array1.splice(i, 1);
            }
        }
        return array1;
    }
    function split_obj(obj) {
        var names = [];
        var values = [];
        for (var name in obj) {
            if (typeof(obj[name]) != 'function') {
                names.push(name);
                values.push(obj[name]);
            }
        }
        return {names: names, values: values, original: obj};
    }
    function suitable(rule, args) {
        var default_args = split_obj(rule.defaults || {});
        var diff_arg_names = array_diff(rule.arguments, default_args.names);

        for (var i = 0; i < diff_arg_names.length; i++) {
            if (!in_array(args.names, diff_arg_names[i])) {
                return false;
            }
        }

        if (array_diff(rule.arguments, args.names).length == 0) {
            if (rule.defaults == null) {
                return true;
            }
            for (var i = 0; i < default_args.names.length; i++) {
                var key = default_args.names[i];
                var value = default_args.values[i];
                if (value != args.original[key]) {
                    return false;
                }
            }
        }

        return true;
    }
    function build(rule, args) {
        var tmp = [];
        var processed = rule.arguments.slice();
        for (var i = 0; i < rule.trace.length; i++) {
            var part = rule.trace[i];
            if (part.is_dynamic) {
                var converter = converters[rule.converters[part.data]];
                var data = converter(args.original[part.data]);
                if (data == null) {
                    return null;
                }
                tmp.push(data);
                processed.push(part.name);
            } else {
                tmp.push(part.data);
            }
        }
        tmp = tmp.join('');
        var pipe = tmp.indexOf('|');
        var subdomain = tmp.substring(0, pipe);
        var url = tmp.substring(pipe+1);

        var unprocessed = array_diff(args.names, processed);
        var first_query_var = true;
        for (var i = 0; i < unprocessed.length; i++) {
            if (first_query_var) {
                url += '?';
            } else {
                url += '&';
            }
            first_query_var = false;
            url += encodeURIComponent(unprocessed[i]);
            url += '=';
            url += encodeURIComponent(args.original[unprocessed[i]]);
        }
        return {subdomain: subdomain, path: url};
    }
    function lstrip(s, c) {
        while (s && s.substring(0, 1) == c) {
            s = s.substring(1);
        }
        return s;
    }
    function rstrip(s, c) {
        while (s && s.substring(s.length-1, s.length) == c) {
            s = s.substring(0, s.length-1);
        }
        return s;
    }
    return function(endpoint, args, force_external) {
        args = split_obj(args);
        var rv = null;
        for (var i = 0; i < rules.length; i++) {
            var rule = rules[i];
            if (rule.endpoint != endpoint) continue;
            if (suitable(rule, args)) {
                rv = build(rule, args);
                if (rv != null) {
                    break;
                }
            }
        }
        if (rv == null) {
            return null;
        }
        if (!force_external && rv.subdomain == subdomain) {
            return rstrip(script_name, '/') + '/' + lstrip(rv.path, '/');
        } else {
            return url_scheme + '://'
                   + (rv.subdomain ? rv.subdomain + '.' : '')
                   + server_name + rstrip(script_name, '/')
                   + '/' + lstrip(rv.path, '/');
        }
    };
})'''
