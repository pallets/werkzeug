#!/usr/bin/env python3
"""
Fuzz harness for Werkzeug's HTTP header parsing.
Targets: parse_options_header, parse_list_header, parse_dict_header,
         parse_cache_control_header — all process untrusted HTTP input.
"""
import sys
import atheris

with atheris.instrument_imports():
    from werkzeug.http import (
        parse_options_header,
        parse_list_header,
        parse_dict_header,
        parse_cache_control_header,
        parse_accept_header,
        parse_set_header,
        parse_range_header,
        parse_content_range_header,
        parse_date,
        http_date,
    )

def TestOneInput(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)
    try:
        text = fdp.ConsumeUnicodeNoSurrogates(len(data))
    except Exception:
        return

    # Each call is a separate parsing path - any unhandled exception = bug
    for fn in [
        parse_list_header,
        parse_dict_header,
        parse_set_header,
    ]:
        try:
            fn(text)
        except (ValueError, TypeError, UnicodeError):
            pass  # expected
        except Exception as e:
            raise  # unexpected = real bug

    try:
        parse_options_header(text)
    except (ValueError, TypeError, UnicodeError):
        pass
    except Exception:
        raise

    try:
        parse_cache_control_header(text)
    except (ValueError, TypeError, UnicodeError):
        pass
    except Exception:
        raise

    try:
        parse_range_header(text)
    except (ValueError, TypeError, UnicodeError):
        pass
    except Exception:
        raise

    try:
        parse_content_range_header(text)
    except (ValueError, TypeError, UnicodeError):
        pass
    except Exception:
        raise

    try:
        parse_date(text)
    except (ValueError, TypeError, UnicodeError, OverflowError):
        pass
    except Exception:
        raise


atheris.Setup(sys.argv, TestOneInput)
atheris.Fuzz()
