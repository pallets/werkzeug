from typing import List

trials: List[int] = []


def app(environ, start_response):
    assert not trials, "should have reloaded"
    trials.append(1)
    import real_app  # type: ignore

    return real_app.real_app(environ, start_response)
