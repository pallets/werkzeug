# -*- coding: utf-8 -*-
"""
    werkzeug.constants
    ~~~~~~~~~~~~~~~~~~

    Various werkzeug related constants.

    :copyright: 2007 by Armin Ronacher, Leif K-Brooks.
    :license: BSD, see LICENSE for more details.
"""


HTTP_STATUS_CODES = {
    100:    'CONTINUE',
    101:    'SWITCHING PROTOCOLS',
    102:    'PROCESSING',
    200:    'OK',
    201:    'CREATED',
    202:    'ACCEPTED',
    203:    'NON-AUTHORITATIVE INFORMATION',
    204:    'NO CONTENT',
    205:    'RESET CONTENT',
    206:    'PARTIAL CONTENT',
    207:    'MULTI STATUS',
    300:    'MULTIPLE CHOICES',
    301:    'MOVED PERMANENTLY',
    302:    'FOUND',
    303:    'SEE OTHER',
    304:    'NOT MODIFIED',
    305:    'USE PROXY',
    306:    'RESERVED',
    307:    'TEMPORARY REDIRECT',
    400:    'BAD REQUEST',
    401:    'UNAUTHORIZED',
    402:    'PAYMENT REQUIRED',
    403:    'FORBIDDEN',
    404:    'NOT FOUND',
    405:    'METHOD NOT ALLOWED',
    406:    'NOT ACCEPTABLE',
    407:    'PROXY AUTHENTICATION REQUIRED',
    408:    'REQUEST TIMEOUT',
    409:    'CONFLICT',
    410:    'GONE',
    411:    'LENGTH REQUIRED',
    412:    'PRECONDITION FAILED',
    413:    'REQUEST ENTITY TOO LARGE',
    414:    'REQUEST-URI TOO LONG',
    415:    'UNSUPPORTED MEDIA TYPE',
    416:    'REQUESTED RANGE NOT SATISFIABLE',
    417:    'EXPECTATION FAILED',
    500:    'INTERNAL SERVER ERROR',
    501:    'NOT IMPLEMENTED',
    502:    'BAD GATEWAY',
    503:    'SERVICE UNAVAILABLE',
    504:    'GATEWAY TIMEOUT',
    505:    'HTTP VERSION NOT SUPPORTED',
    506:    'VARIANT ALSO VARIES',
    507:    'INSUFFICIENT STORAGE',
    510:    'NOT EXTENDED'
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
