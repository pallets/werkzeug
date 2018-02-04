=======
Django
=======

Django is a popular Python-based web application framework. It can be deployed
with different web servers (Nginx and Apache) and application servers (gunicorn
and uwsgi).

Django has hooks for inserting middleware applications at the request,
response and WSGI levels. The key to deploying Werkzeug is to wrap it as
middleware around a WSGI application.

Modifying a WSGI application file
===================================

First, install the Werkzeug package with `pip`.

Next, start with a typical wsgi.py file produced by
`django-admin.py startproject mysite`::

    import os

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings.dev')

    from django.core.wsgi import get_wsgi_application
    application = get_wsgi_application()

and then wrap the WSGI application with the Werkzeug middleware::

    import os

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings.dev')

    from django.core.wsgi import get_wsgi_application
    basic_application = get_wsgi_application()

    from werkzeug.debug import DebuggedApplication
    application = DebuggedApplication(basic_application, evalex=True)

Be sure *not* to add the Werkzeug middleware to Django's `MIDDLEWARE_CLASSES`
setting. That would add it to the request/response middleware, which is very
different from the WSGI middleware.
