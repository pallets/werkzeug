import warnings


class UserAgentMixin:
    def __init__(self, *args, **kwargs):
        warnings.warn(
            "'UserAgentMixin' is deprecated and will be removed in"
            " Werkzeug version 2.1. 'Request' now includes the"
            " functionality directly.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(*args, **kwargs)
