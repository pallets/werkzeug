import warnings


class JSONMixin:
    def __init__(self, *args, **kwargs):
        warnings.warn(
            "'JSONMixin' is deprecated and will be removed in Werkzeug"
            " 2.1. 'Request' now includes the functionality directly.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(*args, **kwargs)
