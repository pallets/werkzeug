==============
Mini Templates
==============

.. admonition:: Deprecated Functionality

   ``werkzeug.templates`` is deprecated without replacement functionality.
   Consider one of the following template engines as replacement:

   -    `Jinja2 <http://jinja.pocoo.org/>`_
   -    `Mako <http://www.makotemplates.org/>`_
   -    `Genshi <http://genshi.edgewall.org/>`_

.. module:: werkzeug.templates

Werkzeug ships a **minimal** templating system which is useful for small
scripts where you just want to generate some HTML and don't want another
dependency or full blown template engine system.

It it however not recommended to use this template system for anything else
than simple content generation.  The :class:`Template` class can be directly
imported from the :mod:`werkzeug` module.

The template engine recognizes ASP/PHP like blocks and executes the code
in them::

    from werkzeug.templates import Template
    t = Template('<% for u in users %>${u["username"]}\n<% endfor %>')
    t.render(users=[{'username': 'John'},
                    {'username': 'Jane'}])

would result in::

    John
    Jane

You can also create templates from files::

    t = Template.from_file('test.html')

The syntax elements are a mixture of django, genshi text and mod_python
templates and used internally in werkzeug components.

We do not recommend using this template engine in a real environment
because is quite slow and does not provide any advanced features.  For
simple applications (cgi script like) this can however be sufficient.


Syntax Elements
===============

Printing Variables:

.. sourcecode:: text

    $variable
    $variable.attribute[item](some, function)(calls)
    ${expression} or <%py print expression %>

Keep in mind that the print statement adds a newline after the call or
a whitespace if it ends with a comma.

For Loops:

.. sourcecode:: text

    <% for item in seq %>
        ...
    <% endfor %>

While Loops:

.. sourcecode:: text

    <% while expression %>
        <%py break / continue %>
    <% endwhile %>

If Conditions:

.. sourcecode:: text

    <% if expression %>
        ...
    <% elif expression %>
        ...
    <% else %>
        ...
    <% endif %>

Python Expressions:

.. sourcecode:: text

    <%py
        ...
    %>

    <%python
        ...
    %>

Note on python expressions:  You cannot start a loop in a python block
and continue it in another one.  This example does *not* work:

.. sourcecode:: text

    <%python
        for item in seq:
    %>
        ...

Comments:

.. sourcecode:: text

    <%#
        This is a comment
    %>


Missing Variables
=================

If you try to access a missing variable you will get back an `Undefined`
object.  You can iterate over such an object or print it and it won't
fail.  However every other operation will raise an error.  To test if a
variable is undefined you can use this expression:

.. sourcecode:: text

    <% if variable is Undefined %>
        ...
    <% endif %>


The Template Class
==================

.. autoclass:: Template

   Besides the normal global functions and objects, the following functions
   are added to every namespace: `escape`, `url_encode`, `url_quote`, and
   `url_quote_plus`.  You can change those by subclassing `Template` and
   overriding the `default_context` dict::

       class MyTemplate(Template):
           default_namespace = {
               'ueber_func':       ueber_func
           }
           # Now add the old functions, too, because they are useful.
           default_namespace.update(Template.default_namespace)

   .. automethod:: from_file

   .. automethod:: render([context])
