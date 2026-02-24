from __future__ import annotations

import collections.abc as cabc
import typing as t

from .structures import CallbackDict


def csp_property(key: str, deprecated: str | None = None) -> t.Any:
    """Create a property for a CSP directive."""
    return property(
        lambda x: x._get_value(key, deprecated=deprecated),
        lambda x, v: x._set_value(key, v, deprecated=deprecated),
        lambda x: x._del_value(key, deprecated, deprecated=deprecated),
        f"The ``{key}`` directive.",
    )


class ContentSecurityPolicy(CallbackDict[str, str]):
    """A dict that stores values for a ``Content-Security-Policy`` header.
    Properties are available to access the CSP directives. The properties have
    the same name as the directives, with dashes replaced with underscore.

    To add a directive that does not have a property implemented, set the dict
    key directly, like ``csp["new-directive"] = "value"``.

    .. versionchanged:: 3.2
        Added the ``required_trusted_types_for``, ``trusted_types``, and
        ``upgrade_insecure_requests`` properties.

    .. versionadded:: 1.0
    """

    # sections from MDN docs
    # fetch directives
    child_src: str | None = csp_property("child-src")
    connect_src: str | None = csp_property("connect-src")
    default_src: str | None = csp_property("default-src")
    font_src: str | None = csp_property("font-src")
    frame_src: str | None = csp_property("frame-src")
    img_src: str | None = csp_property("img-src")
    manifest_src: str | None = csp_property("manifest-src")
    media_src: str | None = csp_property("media-src")
    object_src: str | None = csp_property("object-src")
    script_src: str | None = csp_property("script-src")
    script_src_attr: str | None = csp_property("script-src-attr")
    script_src_elem: str | None = csp_property("script-src-elem")
    style_src: str | None = csp_property("style-src")
    style_src_attr: str | None = csp_property("style-src-attr")
    style_src_elem: str | None = csp_property("style-src-elem")
    worker_src: str | None = csp_property("worker-src")
    # document directives
    base_uri: str | None = csp_property("base-uri")
    sandbox: str | None = csp_property("sandbox")
    # navigation directives
    form_action: str | None = csp_property("form-action")
    frame_ancestors: str | None = csp_property("frame-ancestors")
    # reporting directives
    report_to: str | None = csp_property("report-to")
    # other directives
    require_trusted_types_for: str | None = csp_property("require-trusted-types-for")
    trusted_types: str | None = csp_property("trusted-types")
    upgrade_insecure_requests: str | None = csp_property("upgrade-insecure-requests")
    # deprecated directives
    report_uri: str | None = csp_property("report-uri", deprecated="3.3")
    prefetch_src: str | None = csp_property("prefetch-src", deprecated="3.3")
    # removed directives
    navigate_to: str | None = csp_property("navigate-to", deprecated="3.3")
    plugin_types: str | None = csp_property("plugin-types", deprecated="3.3")

    def __init__(
        self,
        values: cabc.Mapping[str, str] | cabc.Iterable[tuple[str, str]] | None = (),
        on_update: cabc.Callable[[ContentSecurityPolicy], None] | None = None,
    ) -> None:
        super().__init__(values, on_update)
        self.provided = values is not None

    def _get_value(self, key: str, deprecated: str | None = None) -> str | None:
        """Used internally by the accessor properties."""
        if deprecated is not None:
            import warnings

            warnings.warn(
                f"The CSP '{key}' directive is deprecated and will be removed"
                f" in Werkzeug {deprecated}.",
                DeprecationWarning,
                stacklevel=3,
            )

        return self.get(key)

    def _set_value(
        self, key: str, value: str | None, deprecated: str | None = None
    ) -> None:
        """Used internally by the accessor properties."""
        if deprecated is not None:
            import warnings

            warnings.warn(
                f"The CSP '{key}' directive is deprecated and will be removed"
                f" in Werkzeug {deprecated}.",
                DeprecationWarning,
                stacklevel=3,
            )

        if value is None:
            self.pop(key, None)
        else:
            self[key] = value

    def _del_value(self, key: str, deprecated: str | None = None) -> None:
        """Used internally by the accessor properties."""
        if deprecated is not None:
            import warnings

            warnings.warn(
                f"The CSP '{key}' directive is deprecated and will be removed"
                f" in Werkzeug {deprecated}.",
                DeprecationWarning,
                stacklevel=3,
            )

        if key in self:
            del self[key]

    def to_header(self) -> str:
        """Convert the structured data into a header value."""
        from ..http import dump_csp_header

        return dump_csp_header(self)

    def __str__(self) -> str:
        return self.to_header()

    def __repr__(self) -> str:
        kv_str = " ".join(f"{k}={v!r}" for k, v in sorted(self.items()))
        return f"<{type(self).__name__} {kv_str}>"
