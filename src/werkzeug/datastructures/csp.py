from __future__ import annotations

import typing as t

from .structures import CallbackDict

if t.TYPE_CHECKING:
    import typing_extensions as te


def _csp_property(key: str, deprecated: str | None = None) -> t.Any:
    """Create a property for a CSP directive."""
    return property(
        lambda x: x._get_value(key, deprecated=deprecated),
        lambda x, v: x._set_value(key, v, deprecated=deprecated),
        lambda x: x._del_value(key, deprecated, deprecated=deprecated),
        f"The ``{key}`` directive.",
    )


class ContentSecurityPolicy(CallbackDict[str, t.Any]):
    """A parsed ``Content-Security-Policy`` header.

    Set :attr:`.Response.content_security_policy` or
    :attr:`.Response.content_security_policy_report_only` to an instance to set
    the header. Modifying the instance will update the header.

    Typically, you'll use the various directive properties. It also allows
    indexing ``csp[directive]`` to get, set, or delete unknown directives that
    do not have corresponding properties.

    .. versionchanged:: 3.2
        Directives with only a name and no space or value are considered boolean
        rather than discarded.

        Added the ``required_trusted_types_for``, ``trusted_types``, and
        ``upgrade_insecure_requests`` properties.

        The ``prefetch_src``, ``navigate_to``, and ``plugin_types`` properties
        are deprecated and will be removed in Werkzeug 3.3.

        The ``on_update`` parameter was removed.

    .. versionadded:: 1.0
    """

    # sections from MDN docs
    # fetch directives
    child_src: str | None = _csp_property("child-src")
    connect_src: str | None = _csp_property("connect-src")
    default_src: str | None = _csp_property("default-src")
    font_src: str | None = _csp_property("font-src")
    frame_src: str | None = _csp_property("frame-src")
    img_src: str | None = _csp_property("img-src")
    manifest_src: str | None = _csp_property("manifest-src")
    media_src: str | None = _csp_property("media-src")
    object_src: str | None = _csp_property("object-src")
    script_src: str | None = _csp_property("script-src")
    script_src_attr: str | None = _csp_property("script-src-attr")
    script_src_elem: str | None = _csp_property("script-src-elem")
    style_src: str | None = _csp_property("style-src")
    style_src_attr: str | None = _csp_property("style-src-attr")
    style_src_elem: str | None = _csp_property("style-src-elem")
    worker_src: str | None = _csp_property("worker-src")
    # document directives
    base_uri: str | None = _csp_property("base-uri")
    sandbox: str | None = _csp_property("sandbox")
    # navigation directives
    form_action: str | None = _csp_property("form-action")
    frame_ancestors: str | None = _csp_property("frame-ancestors")
    # reporting directives
    report_to: str | None = _csp_property("report-to")
    # other directives
    require_trusted_types_for: str | None = _csp_property("require-trusted-types-for")
    trusted_types: str | None = _csp_property("trusted-types")
    upgrade_insecure_requests: bool | None = _csp_property("upgrade-insecure-requests")
    # deprecated directives
    report_uri: str | None = _csp_property("report-uri")  # still widely supported
    prefetch_src: str | None = _csp_property("prefetch-src", deprecated="3.3")
    # removed directives
    navigate_to: str | None = _csp_property("navigate-to", deprecated="3.3")
    plugin_types: str | None = _csp_property("plugin-types", deprecated="3.3")

    def _get_value(self, key: str, deprecated: str | None = None) -> t.Any | None:
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
            if (value := self[key]) is None:
                return True

            return value

        return None

    def _set_value(
        self, key: str, value: t.Any | None, deprecated: str | None = None
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

        if not value:
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

    @classmethod
    def from_header(cls, value: str | None) -> te.Self:
        """Parse a ``Content-Security-Policy`` header value and create an
        instance of this class.

        .. versionadded:: 3.2
        """
        if not value:
            return cls()

        items: list[tuple[str, str | None]] = []

        for policy in value.split(";"):
            policy = policy.strip(" \t")

            # Ignore badly formatted policies (no space)
            if " " in policy:
                directive, _, value = policy.partition(" ")
                items.append((directive.strip(" \t"), value.strip(" \t")))
            else:
                items.append((policy, None))

        return cls(items)

    def to_header(self) -> str:
        """Convert to a ``Content-Security-Policy`` header value."""
        out = []

        for key, value in self.items():
            if value is None:
                out.append(key)
            else:
                out.append(f"{key} {value}")

        return "; ".join(out)

    def __str__(self) -> str:
        return self.to_header()

    def __repr__(self) -> str:
        kv_str = " ".join(f"{k}={v!r}" for k, v in sorted(self.items()))
        return f"<{type(self).__name__} {kv_str}>"
