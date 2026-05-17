# ======================================================================================
# Copyright and other protections apply. Please see the accompanying LICENSE file for
# rights and restrictions governing use of this software. All rights not expressly
# waived or licensed are reserved. If that file is missing or appears to be modified
# from its original, then please contact the author before viewing or using this
# software in any capacity.
#
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
# !!!!!!!!!!!!!!! IMPORTANT: READ THIS BEFORE EDITING! !!!!!!!!!!!!!!!
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
# Please keep each docstring sentence on its own unwrapped line. It looks like crap in a
# text editor, but it has no effect on rendering, and it allows much more useful diffs.
# (This does not apply to code comments.) Thank you!
# ======================================================================================

from fractions import Fraction
from typing import cast

__all__ = ("Settings",)

# Default truncation threshold for accumulator-level pruning. Outcomes whose
# within-H probability falls below this bound are dropped (and tracked for
# zero-count restoration at output time). Chosen to be conservative enough to
# not affect normal AnyDice programs, but aggressive enough to bound deep-
# recursion programs (e.g. `[highest of 10000000 x d6]`) whose tail
# probabilities decay below any float-representable threshold. Roughly matches
# the effective precision floor of AnyDice's float arithmetic.
_DEFAULT_PRECISION: Fraction = Fraction(1, 10**13)

_DEFAULTS: dict[str, int | str] = {
    "position order": "highest first",
    "maximum function depth": 10,
    "explode depth": 2,
}

_VALID_STRINGS: dict[str, set[str]] = {
    "position order": {"highest first", "lowest first"},
}

# Settings that accept only a positive integer (>= 1). Verified against AnyDice:
# `set "explode depth" to 0` (or negative, or a string) errors with
# "<key> can only be set to a positive integer (the default is N)".
_POSITIVE_INT_KEYS: frozenset[str] = frozenset(
    {"maximum function depth", "explode depth"}
)


class Settings:
    def __init__(self) -> None:
        self._data: dict[str, int | str] = dict(_DEFAULTS)
        # Python-only setting; not exposed via AnyDice's `set` directive since
        # AnyDice has no native syntax for fractional values. Configure via the
        # Python-level Settings object before invoking `run`.
        self.precision: Fraction = _DEFAULT_PRECISION

    def get(self, key: str) -> int | str:
        if key in self._data:
            return self._data[key]
        else:
            raise KeyError(f"unknown setting: {key!r}")

    def set(self, key: str, value: int | str) -> None:
        if key not in self._data:
            raise KeyError(f"unknown setting: {key!r}")
        if key in _VALID_STRINGS:
            allowed = _VALID_STRINGS[key]
            if value not in allowed:
                raise ValueError(
                    f"invalid value {value!r} for setting {key!r}; "
                    f"expected one of {allowed}"
                )
        elif key in _POSITIVE_INT_KEYS:
            # bool is a subclass of int but not a valid setting value here;
            # exclude it explicitly.
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError(
                    f"{key!r} can only be set to a positive integer (got {value!r})"
                )
        self._data[key] = value

    @property
    def position_order(self) -> str:
        return str(self._data["position order"])

    @property
    def max_depth(self) -> int:
        return cast("int", self._data["maximum function depth"])

    @property
    def explode_depth(self) -> int:
        return cast("int", self._data["explode depth"])

    def highest_first(self) -> bool:
        return self._data["position order"] == "highest first"
