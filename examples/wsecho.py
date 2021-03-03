"""Shows how you can implement a simple WebSocket echo server using the
wsproto library.
"""
from werkzeug.exceptions import InternalServerError
from werkzeug.serving import run_simple
from werkzeug.wrappers import Request
from werkzeug.wrappers import Response
from wsproto import ConnectionType
from wsproto import WSConnection
from wsproto.events import AcceptConnection
from wsproto.events import CloseConnection
from wsproto.events import Message
from wsproto.events import Ping
from wsproto.events import Request as WSRequest
from wsproto.events import TextMessage
from wsproto.frame_protocol import CloseReason


@Request.application
def websocket(request):
    # The underlying socket must be provided by the server. Gunicorn and
    # Werkzeug's dev server are known to support this.
    stream = request.environ.get("werkzeug.socket")

    if stream is None:
        stream = request.environ.get("gunicorn.socket")

    if stream is None:
        raise InternalServerError()

    # Initialize the wsproto connection. Need to recreate the request
    # data that was read by the WSGI server already.
    ws = WSConnection(ConnectionType.SERVER)
    in_data = b"GET %s HTTP/1.1\r\n" % request.path.encode("utf8")

    for header, value in request.headers.items():
        in_data += f"{header}: {value}\r\n".encode("utf8")

    in_data += b"\r\n"
    ws.receive_data(in_data)
    running = True

    while True:
        out_data = b""

        for event in ws.events():
            if isinstance(event, WSRequest):
                out_data += ws.send(AcceptConnection())
            elif isinstance(event, CloseConnection):
                out_data += ws.send(event.response())
                running = False
            elif isinstance(event, Ping):
                out_data += ws.send(event.response())
            elif isinstance(event, TextMessage):
                # echo the incoming message back to the client
                if event.data == "quit":
                    out_data += ws.send(
                        CloseConnection(CloseReason.NORMAL_CLOSURE, "bye")
                    )
                    running = False
                else:
                    out_data += ws.send(Message(data=event.data))

        if out_data:
            stream.send(out_data)

        if not running:
            break

        in_data = stream.recv(4096)
        ws.receive_data(in_data)

    # The connection will be closed at this point, but WSGI still
    # requires a response.
    return Response("", status=204)


if __name__ == "__main__":
    run_simple("localhost", 5000, websocket)
