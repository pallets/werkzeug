import warnings


class ETagRequestMixin:
    def __init__(self, *args, **kwargs):
        warnings.warn(
            "'ETagRequestMixin' is deprecated and will be removed in"
            " Werkzeug version 2.1. 'Request' now includes the"
            " functionality directly.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(*args, **kwargs)


class ETagResponseMixin:
    def __init__(self, *args, **kwargs):
        warnings.warn(
            "'ETagResponseMixin' is deprecated and will be removed in"
            " Werkzeug version 2.1. 'Response' now includes the"
            " functionality directly.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(*args, **kwargs)
