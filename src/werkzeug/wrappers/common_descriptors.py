import warnings


class CommonRequestDescriptorsMixin:
    def __init__(self, *args, **kwargs):
        warnings.warn(
            "'CommonRequestDescriptorsMixin' is deprecated and will be"
            " removed in Werkzeug 2.1. 'Request' now includes the"
            " functionality directly.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(*args, **kwargs)


class CommonResponseDescriptorsMixin:
    def __init__(self, *args, **kwargs):
        warnings.warn(
            "'CommonResponseDescriptorsMixin' is deprecated and will be"
            " removed in Werkzeug 2.1. 'Response' now includes the"
            " functionality directly.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(*args, **kwargs)
