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
    def __init__(self, priority: tuple[tuple[t.Any, ...], ...]) -> None:
        self.priority = priority


@dataclass
class State:
    """A representation of a rule state.

    This includes the *rules* that correspond to the state and the
    possible *static* and *dynamic* transitions to the next state.
    """

    dynamic: list[tuple[RulePart, State]] = field(default_factory=list)
    rules: list[Rule] = field(default_factory=list)
    static: dict[str, State] = field(default_factory=dict)


@dataclass
class StateMatch:
    rule: Rule
    values: list[str]
    priority: tuple[tuple[t.Any, ...], ...]


class StateMachineMatcher:
    def __init__(self, merge_slashes: bool) -> None:
        self._root = State()
        self._rule_order: dict[int, int] = {}
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

        for existing in state.rules:
            if rule.is_duplicate(existing):
                raise DuplicateRuleError(existing, rule)

        self._rule_order[id(rule)] = len(self._rule_order)
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
        ) -> StateMatch | None:
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
                        return StateMatch(
                            rule, values, (((2, self._rule_order[id(rule)]),))
                        )

                # Test if there is a match with this path with a
                # trailing slash, if so raise an exception to report
                # that matching is possible with an additional slash
                if "" in state.static:
                    for rule in state.static[""].rules:
                        if websocket == rule.websocket and (
                            rule.methods is None or method in rule.methods
                        ):
                            if rule.strict_slashes:
                                raise SlashRequired(((2, self._rule_order[id(rule)]),))
                            else:
                                return StateMatch(
                                    rule,
                                    values,
                                    (((2, self._rule_order[id(rule)]),)),
                                )
                return None

            part = parts[0]
            # To match this part try the static transitions first
            if part in state.static:
                rv = _match(state.static[part], parts[1:], values)
                if rv is not None:
                    rv.priority = ((0,), *rv.priority)
                    return rv
            # No match via the static transitions, so try the dynamic
            # ones.
            pos = 0

            while pos < len(state.dynamic):
                weight = state.dynamic[pos][0].weight
                matches: list[StateMatch] = []

                # Equal-weight transitions have equal priority at this
                # segment, so defer choosing until later parts break the tie.
                best_slash_required: SlashRequired | None = None

                while (
                    pos < len(state.dynamic) and state.dynamic[pos][0].weight == weight
                ):
                    test_part, new_state = state.dynamic[pos]
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
                            # If a part_isolating=False part has a slash suffix,
                            # remove the suffix from the match and check for the
                            # slash redirect next.
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
                        try:
                            rv = _match(new_state, remaining, values + groups)
                        except SlashRequired as e:
                            e.priority = ((1, test_part.weight), *e.priority)
                            if (
                                best_slash_required is None
                                or e.priority < best_slash_required.priority
                            ):
                                best_slash_required = e
                        else:
                            if rv is not None:
                                rv.priority = ((1, test_part.weight), *rv.priority)
                                matches.append(rv)

                    pos += 1

                if matches:
                    best_match = min(matches, key=lambda match: match.priority)

                    if (
                        best_slash_required is not None
                        and best_slash_required.priority < best_match.priority
                    ):
                        raise best_slash_required

                    return best_match

                if best_slash_required is not None:
                    raise best_slash_required

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
                        return StateMatch(
                            rule, values, (((2, self._rule_order[id(rule)]),))
                        )

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
            if rv is None or rv.rule.merge_slashes is False:
                raise NoMatch(have_match_for, websocket_mismatch)
            else:
                raise RequestPath(f"{path}")
        elif rv is not None:
            rule = rv.rule
            values = rv.values

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
