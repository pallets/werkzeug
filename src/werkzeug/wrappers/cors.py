import warnings


class CORSRequestMixin:
    def __init__(self, *args, **kwargs):
        warnings.warn(
            "'CORSRequestMixin' is deprecated and will be removed in"
            " Werkzeug version 2.1. 'Request' now includes the"
            " functionality directly.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(*args, **kwargs)


class CORSResponseMixin:
    def __init__(self, *args, **kwargs):
        warnings.warn(
            "'CORSResponseMixin' is deprecated and will be removed in"
            " Werkzeug version 2.1. 'Response' now includes the"
            " functionality directly.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(*args, **kwargs)
