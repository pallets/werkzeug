import re
import typing as t
from dataclasses import dataclass
from dataclasses import field

from ..urls import url_unquote
from .converters import ValidationError
from .exceptions import NoMatch
from .exceptions import RequestAliasRedirect
from .exceptions import RequestPath
from .rules import Rule
from .rules import RulePart
from .rules import Weighting


class SlashRequired(Exception):
    pass


@dataclass
class State:
    """A representation of a rule state.

    This includes the *rules* that correspond to the state and the
    possible *static* and *dynamic* transitions to the next state.
    """

    dynamic: t.List[t.Tuple[RulePart, "State"]] = field(default_factory=list)
    rules: t.List[Rule] = field(default_factory=list)
    static: t.Dict[str, "State"] = field(default_factory=dict)


class StateMachineMatcher:
    def __init__(self, merge_slashes: bool) -> None:
        self._root = State()
        self.merge_slashes = merge_slashes

    def add(self, rule: Rule) -> None:
        state = self._root
        for part in rule._parts:
            if part.static:
                state.static.setdefault(part.content, State())
                state = state.static[part.content]
            else:
                for test_part, new_state in state.dynamic:
                    if test_part == part:
                        state = new_state
                        break
                else:
                    new_state = State()
                    state.dynamic.append((part, new_state))
                    state = new_state
        state.rules.append(rule)

    def update(self) -> None:
        # For every state the dynamic transitions should be sorted by
        # the weight of the transition
        state = self._root

        def _update_state(state: State) -> None:
            state.dynamic.sort(key=lambda entry: entry[0].weight)
            for new_state in state.static.values():
                _update_state(new_state)
            for _, new_state in state.dynamic:
                _update_state(new_state)

        _update_state(state)

    def match(
        self, domain: str, path: str, method: str, websocket: bool
    ) -> t.Tuple[Rule, t.MutableMapping[str, t.Any]]:
        # To match to a rule we need to start at the root state and
        # try to follow the transitions until we find a match, or find
        # there is no transition to follow.

        have_match_for = set()
        websocket_mismatch = False

        def _match(
            state: State, parts: t.List[str], values: t.List[str]
        ) -> t.Optional[t.Tuple[Rule, t.List[str]]]:
            # This function is meant to be called recursively, and will attempt
            # to match the head part to the state's transitions.
            nonlocal have_match_for, websocket_mismatch

            # The base case is when all parts have been matched via
            # transitions. Hence if there is a rule with methods &
            # websocket that work return it and the dynamic values
            # extracted.
            if parts == []:
                for rule in state.rules:
                    if rule.methods is not None and method not in rule.methods:
                        have_match_for.update(rule.methods)
                    elif rule.websocket != websocket:
                        websocket_mismatch = True
                    else:
                        return rule, values

                # Test if there is a match with this path with a
                # trailing slash, if so raise an exception to report
                # that matching is possible with an additional slash
                if "" in state.static:
                    for rule in state.static[""].rules:
                        if (
                            rule.strict_slashes
                            and websocket == rule.websocket
                            and (rule.methods is None or method in rule.methods)
                        ):
                            raise SlashRequired()
                return None

            part = parts[0]
            # To match this part try the static transitions first
            if part in state.static:
                rv = _match(state.static[part], parts[1:], values)
                if rv is not None:
                    return rv
            # No match via the static transitions, so try the dynamic
            # ones.
            for test_part, new_state in state.dynamic:
                target = part
                remaining = parts[1:]
                # A final part indicates a transition that always
                # consumes the remaining parts i.e. transitions to a
                # final state.
                if test_part.final:
                    target = "/".join(parts)
                    remaining = []
                match = re.compile(test_part.content).match(target)
                if match is not None:
                    rv = _match(new_state, remaining, values + list(match.groups()))
                    if rv is not None:
                        return rv
            return None

        try:
            rv = _match(self._root, [domain, *path.split("/")], [])
        except SlashRequired:
            raise RequestPath(f"{path}/") from None

        if self.merge_slashes and rv is None:
            # Try to match again, but with slashes merged
            path = re.sub("/{2,}?", "/", path)
            try:
                rv = _match(self._root, [domain, *path.split("/")], [])
            except SlashRequired:
                raise RequestPath(f"{path}/") from None
            if rv is None:
                raise NoMatch(have_match_for, websocket_mismatch)
            else:
                raise RequestPath(f"{path}")
        elif rv is not None:
            rule, values = rv

            result = {}
            for name, value in zip(rule._converters.keys(), values):
                try:
                    value = rule._converters[name].to_python(value)
                except ValidationError:
                    raise NoMatch(have_match_for, websocket_mismatch) from None
                result[str(name)] = value
            if rule.defaults:
                result.update(rule.defaults)

            if rule.alias and rule.map.redirect_defaults:
                raise RequestAliasRedirect(result, rule.endpoint)

            return rule, result

        raise NoMatch(have_match_for, websocket_mismatch)


class TableMatcher:
    def __init__(self, merge_slashes: bool) -> None:
        self._rules: t.List[t.Tuple[t.Pattern[str], Rule, Weighting]] = []
        self.merge_slashes = merge_slashes

    def add(self, rule: Rule) -> None:
        weight = rule._parts[0].weight
        regex = rf"^{rule._parts[0].content}\|"

        regex += r"/".join(
            re.escape(part.content) if part.static else part.content
            for part in rule._parts[1:]
        )

        for part in rule._parts[1:]:
            weight = weight + part.weight

        # A full part includes an end, which we don't need
        if regex[-3:] == r"$\Z":
            regex = regex[:-3]

        if rule.is_branch and rule.strict_slashes:
            # Replace the final `/` with an optional capturing `/`
            regex = rf"{regex[:-1]}(?<!\/)(\/?)"

        # Use \Z instead of $ to avoid matching before a %0a decoded to
        # a \n by WSGI.
        regex += r"$\Z"

        rule_regex = re.compile(regex)
        self._rules.append((rule_regex, rule, weight))

    def update(self) -> None:
        self._rules.sort(key=lambda x: x[2])

    def match(
        self, domain: str, path: str, method: str, websocket: bool
    ) -> t.Tuple[Rule, t.MutableMapping[str, t.Any]]:

        have_match_for = set()
        websocket_mismatch = False

        for regex, rule, _ in self._rules:
            rv = self._match_rule(regex, rule, domain, path, method)

            if rv is not None:
                if rule.methods is not None and method not in rule.methods:
                    have_match_for.update(rule.methods)
                elif rule.websocket != websocket:
                    websocket_mismatch = True
                else:
                    return rule, rv

        raise NoMatch(have_match_for, websocket_mismatch)

    def _match_rule(
        self, regex: t.Pattern[str], rule: Rule, domain: str, path: str, method: str
    ) -> t.Optional[t.MutableMapping[str, t.Any]]:
        m = regex.search(f"{domain}|{path}")
        if m is not None:
            groups = list(m.groups())

            if rule.is_branch and rule.strict_slashes:
                # Remove the optional slash group from the groups
                slash = groups.pop()

                if (
                    method is None or rule.methods is None or method in rule.methods
                ) and slash == "":
                    # Rule requires a slash (strict slashes) but is missing one.
                    raise RequestPath(f"{path}/")

            result = {}
            for name, value in zip(rule._converters.keys(), groups):
                try:
                    value = rule._converters[name].to_python(value)
                except ValidationError:
                    return None
                result[str(name)] = value
            if rule.defaults:
                result.update(rule.defaults)

            if self.merge_slashes:
                new_path = "|".join(rule.build(result, False))  # type: ignore
                if path.endswith("/") and not new_path.endswith("/"):
                    new_path += "/"
                if new_path.count("/") < path.count("/"):
                    # The URL will be encoded when MapAdapter.match
                    # handles the RequestPath raised below. Decode
                    # the URL here to avoid a double encoding.
                    path = url_unquote(new_path)
                    raise RequestPath(path)

            if rule.alias and rule.map.redirect_defaults:
                raise RequestAliasRedirect(result, rule.endpoint)

            return result

        return None
