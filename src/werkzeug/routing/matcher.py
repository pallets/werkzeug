from __future__ import annotations

import re
import typing as t
from dataclasses import dataclass
from dataclasses import field

from .converters import ValidationError
from .exceptions import DuplicateRuleError
from .exceptions import NoMatch
from .exceptions import RequestAliasRedirect
from .exceptions import RequestPath
from .rules import Rule
from .rules import RulePart


class SlashRequired(Exception):
    pass


@dataclass
class State:
    """A representation of a rule state.

    This includes the *rules* that correspond to the state and the
    possible *static* and *dynamic* transitions to the next state.
    """

    dynamic: list[tuple[RulePart, State]] = field(default_factory=list)
    rules: list[Rule] = field(default_factory=list)
    static: dict[str, State] = field(default_factory=dict)


def _rule_match_preference(rule: Rule) -> tuple[int, int, int]:
    """Score a fully matched rule when choosing among equal-weight dynamic peers.

    Higher is better. Prefer rules with more static parts and fewer dynamic
    parts (specificity), then earlier registration order (stable first-wins).

    See https://github.com/pallets/werkzeug/issues/3156
    """
    static_count = sum(1 for part in rule._parts if part.static)
    dynamic_count = sum(1 for part in rule._parts if not part.static)
    # Earlier rules have smaller _match_order; invert so max() prefers them.
    order = getattr(rule, "_match_order", 0)
    return (static_count, -dynamic_count, -order)


class StateMachineMatcher:
    def __init__(self, merge_slashes: bool) -> None:
        self._root = State()
        self.merge_slashes = merge_slashes
        self._rule_order = 0

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

        for existing in state.rules:
            if rule.is_duplicate(existing):
                raise DuplicateRuleError(existing, rule)

        # Stable registration index for equal-weight dynamic peer selection.
        rule._match_order = self._rule_order  # type: ignore[attr-defined]
        self._rule_order += 1
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
    ) -> tuple[Rule, t.MutableMapping[str, t.Any]]:
        # To match to a rule we need to start at the root state and
        # try to follow the transitions until we find a match, or find
        # there is no transition to follow.

        have_match_for = set()
        websocket_mismatch = False

        def _match(
            state: State, parts: list[str], values: list[str]
        ) -> tuple[Rule, list[str]] | None:
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
                        if websocket == rule.websocket and (
                            rule.methods is None or method in rule.methods
                        ):
                            if rule.strict_slashes:
                                raise SlashRequired()
                            else:
                                return rule, values
                return None

            part = parts[0]
            # To match this part try the static transitions first
            if part in state.static:
                rv = _match(state.static[part], parts[1:], values)
                if rv is not None:
                    return rv
            # No match via the static transitions, so try the dynamic
            # ones. Dynamic transitions are sorted by weight; within the
            # same weight, try every matching converter and pick the best
            # rule. Returning the first successful transition alone lets
            # an unrelated earlier rule reorder equal-weight peers when
            # RuleParts are merged (pallets/werkzeug#3156).
            dynamics = state.dynamic
            di = 0
            while di < len(dynamics):
                weight = dynamics[di][0].weight
                dj = di + 1
                while dj < len(dynamics) and dynamics[dj][0].weight == weight:
                    dj += 1

                candidates: list[tuple[Rule, list[str]]] = []
                for test_part, new_state in dynamics[di:dj]:
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
                        if test_part.suffixed:
                            # If a part_isolating=False part has a slash
                            # suffix, remove the suffix from the match and
                            # check for the slash redirect next.
                            suffix = match.groups()[-1]
                            if suffix == "/":
                                remaining = [""]

                        converter_groups = sorted(
                            match.groupdict().items(), key=lambda entry: entry[0]
                        )
                        groups = [
                            value
                            for key, value in converter_groups
                            if key[:11] == "__werkzeug_"
                        ]
                        rv = _match(new_state, remaining, values + groups)
                        if rv is not None:
                            candidates.append(rv)

                if candidates:
                    return max(
                        candidates, key=lambda item: _rule_match_preference(item[0])
                    )

                di = dj

            # If there is no match and the only part left is a
            # trailing slash ("") consider rules that aren't
            # strict-slashes as these should match if there is a final
            # slash part.
            if parts == [""]:
                for rule in state.rules:
                    if rule.strict_slashes:
                        continue
                    if rule.methods is not None and method not in rule.methods:
                        have_match_for.update(rule.methods)
                    elif rule.websocket != websocket:
                        websocket_mismatch = True
                    else:
                        return rule, values

            return None

        try:
            rv = _match(self._root, [domain, *path.split("/")], [])
        except SlashRequired:
            raise RequestPath(f"{path}/") from None

        if self.merge_slashes and rv is None:
            # Try to match again, but with slashes merged
            path = re.sub("/{2,}", "/", path)
            try:
                rv = _match(self._root, [domain, *path.split("/")], [])
            except SlashRequired:
                raise RequestPath(f"{path}/") from None
            if rv is None or rv[0].merge_slashes is False:
                raise NoMatch(have_match_for, websocket_mismatch)
            else:
                raise RequestPath(f"{path}")
        elif rv is not None:
            rule, values = rv

            result = {}
            for name, value in zip(rule._converters.keys(), values, strict=True):
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
