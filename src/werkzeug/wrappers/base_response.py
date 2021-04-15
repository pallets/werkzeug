import warnings

from .response import Response


class _FakeSubclassCheck(type):
    def __subclasscheck__(cls, subclass):
        warnings.warn(
            "'BaseResponse' is deprecated and will be removed in"
            " Werkzeug 2.1. Use 'issubclass(cls, Response)' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return issubclass(subclass, Response)

    def __instancecheck__(cls, instance):
        warnings.warn(
            "'BaseResponse' is deprecated and will be removed in"
            " Werkzeug 2.1. Use 'isinstance(obj, Response)' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return isinstance(instance, Response)


class BaseResponse(Response, metaclass=_FakeSubclassCheck):
    def __init__(self, *args, **kwargs):
        warnings.warn(
            "'BaseResponse' is deprecated and will be removed in"
            " Werkzeug 2.1. 'Response' now includes the functionality"
            " directly.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(*args, **kwargs)
