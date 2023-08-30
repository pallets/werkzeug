import datetime
import os
from unittest.mock import ANY
from unittest.mock import MagicMock
from unittest.mock import patch

from werkzeug.middleware.profiler import Profile
from werkzeug.middleware.profiler import ProfilerMiddleware
from werkzeug.test import Client


def dummy_application(environ, start_response):
    start_response("200 OK", [("Content-Type", "text/plain")])
    return [b"Foo"]


def test_filename_format_function():
    # This should be called once with the generated file name
    mock_capture_name = MagicMock()

    def filename_format(env):
        now = datetime.datetime.fromtimestamp(env["werkzeug.profiler"]["time"])
        timestamp = now.strftime("%Y-%m-%d:%H:%M:%S")
        path = (
            "_".join(token for token in env["PATH_INFO"].split("/") if token) or "ROOT"
        )
        elapsed = env["werkzeug.profiler"]["elapsed"]
        name = f"{timestamp}.{env['REQUEST_METHOD']}.{path}.{elapsed:.0f}ms.prof"
        mock_capture_name(name=name)
        return name

    client = Client(
        ProfilerMiddleware(
            dummy_application,
            stream=None,
            profile_dir="profiles",
            filename_format=filename_format,
        )
    )

    # Replace the Profile class with a function that simulates an __init__()
    # call and returns our mock instance.
    mock_profile = MagicMock(wraps=Profile())
    mock_profile.dump_stats = MagicMock()
    with patch("werkzeug.middleware.profiler.Profile", lambda: mock_profile):
        client.get("/foo/bar")

        mock_capture_name.assert_called_once_with(name=ANY)
        name = mock_capture_name.mock_calls[0].kwargs["name"]
        mock_profile.dump_stats.assert_called_once_with(os.path.join("profiles", name))
