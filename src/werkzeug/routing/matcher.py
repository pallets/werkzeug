import re
import typing as t

from ..urls import url_unquote
from .converters import ValidationError
from .exceptions import NoMatch
from .exceptions import RequestAliasRedirect
from .exceptions import RequestPath
from .rules import Rule


class TableMatcher:
    def __init__(self) -> None:
        self._rules: t.List[t.Tuple[t.Pattern[str], Rule]] = []

    def add(self, rule: Rule) -> None:
        regex_parts = []
        for dynamic, part in rule._parts:
            if part == "|":
                regex_parts.append("\\|")
            elif dynamic:
                convobj = rule._converters[part]
                regex_parts.append(f"(?P<{part}>{convobj.regex})")
            else:
                regex_parts.append(part)

        if not (rule.is_leaf and rule.strict_slashes):
            reps = "*" if rule.merge_slashes else "?"
            tail = f"(?<!/)(?P<__suffix__>/{reps})"
        else:
            tail = ""

        # Use \Z instead of $ to avoid matching before a %0a decoded to
        # a \n by WSGI.
        regex = rf"^{''.join(regex_parts)}{tail}$\Z"
        rule_regex = re.compile(regex)
        self._rules.append((rule_regex, rule))

    def update(self) -> None:
        self._rules.sort(key=lambda x: x[1].match_compare_key())

    def match(
        self, domain: str, path: str, method: str, websocket: bool
    ) -> t.Tuple[Rule, t.MutableMapping[str, t.Any]]:

        have_match_for = set()
        websocket_mismatch = False

        path = f"{domain}|{path}"
        for regex, rule in self._rules:
            rv = self.match_rule(regex, rule, path, method)

            if rv is not None:
                if rule.methods is not None and method not in rule.methods:
                    have_match_for.update(rule.methods)
                elif rule.websocket != websocket:
                    websocket_mismatch = True
                else:
                    return rule, rv

        raise NoMatch(have_match_for, websocket_mismatch)

    def match_rule(
        self, regex: t.Pattern[str], rule: Rule, path: str, method: str
    ) -> t.Optional[t.MutableMapping[str, t.Any]]:
        require_redirect = False

        m = regex.search(path)
        if m is not None:
            groups = m.groupdict()
            # we have a folder like part of the url without a trailing
            # slash and strict slashes enabled. raise an exception that
            # tells the map to redirect to the same url but with a
            # trailing slash
            if (
                rule.strict_slashes
                and not rule.is_leaf
                and not groups.pop("__suffix__")
                and (method is None or rule.methods is None or method in rule.methods)
            ):
                path += "/"
                require_redirect = True
            # if we are not in strict slashes mode we have to remove
            # a __suffix__
            elif not rule.strict_slashes:
                del groups["__suffix__"]

            result = {}
            for name, value in groups.items():
                try:
                    value = rule._converters[name].to_python(value)
                except ValidationError:
                    return None
                result[str(name)] = value
            if rule.defaults:
                result.update(rule.defaults)

            if rule.merge_slashes:
                new_path = "|".join(rule.build(result, False))  # type: ignore
                if path.endswith("/") and not new_path.endswith("/"):
                    new_path += "/"
                if new_path.count("/") < path.count("/"):
                    # The URL will be encoded when MapAdapter.match
                    # handles the RequestPath raised below. Decode
                    # the URL here to avoid a double encoding.
                    path = url_unquote(new_path)
                    require_redirect = True

            if require_redirect:
                path = path.split("|", 1)[1]
                raise RequestPath(path)

            if rule.alias and rule.map.redirect_defaults:
                raise RequestAliasRedirect(result, rule.endpoint)

            return result

        return None
