import pytest
from werkzeug.datastructures import MIMEAccept

def test_mime_accept_best_match_quality_weights():
    """Verify MIMEAccept selects highest quality factor representation."""
    accept = MIMEAccept([
        ("text/html", 0.8),
        ("application/json", 1.0),
        ("*/*", 0.1)
    ])
    
    assert accept.best_match(["text/html", "application/json"]) == "application/json"
    assert accept.best_match(["text/plain", "image/png"]) == "text/plain"

def test_mime_accept_empty_header_fallback():
    accept = MIMEAccept([])
    assert accept.best_match(["application/json", "text/html"]) == "application/json"
