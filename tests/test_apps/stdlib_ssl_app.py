import ssl
import tempfile

from werkzeug import serving


def stdlib_ssl_app(environ, start_response):
    start_response("200 OK", [("Content-Type", "text/html")])
    return [b"hello"]


certificate, private_key = serving.make_ssl_devcert(
    str(tempfile.mkdtemp(suffix="certs"))
)
ctx = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
ctx.load_cert_chain(certificate, private_key)
ssl_kwargs = {}
ssl_kwargs["ssl_context"] = ctx
