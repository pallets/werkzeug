import warnings


class AuthorizationMixin:
    def __init__(self, *args, **kwargs):
        warnings.warn(
            "'AuthorizationMixin' is deprecated and will be removed in"
            " Werkzeug version 2.1. 'Request' now includes the"
            " functionality directly.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(*args, **kwargs)


class WWWAuthenticateMixin:
    def __init__(self, *args, **kwargs):
        warnings.warn(
            "'WWWAuthenticateMixin' is deprecated and will be removed"
            " in Werkzeug version 2.1. 'Response' now includes the"
            " functionality directly.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(*args, **kwargs)
