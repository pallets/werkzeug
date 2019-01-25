import warnings

from ..middleware.profile import *  # noqa: F401, F403

warnings.warn(
    "'werkzeug.contrib.profiler' has moved to"
    "'werkzeug.middleware.profile'. This import is deprecated as of"
    "version 0.15 and will be removed in version 1.0.",
    DeprecationWarning,
    stacklevel=2,
)
