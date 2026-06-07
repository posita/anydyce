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

from typing import cast

from dyce.h import DEFAULT_PRECISION  # , DEFAULT_QUANTIZATION_BIT_WIDTH

__all__ = ("Settings",)

# Defaults for the two anydyce-introduced settings.
#
# Calculation precision is the bit_width passed to `dyce.quantize_hs`.
# 256 matches the interpreter's prior `_DEFAULT_QUANTIZATION_BIT_WIDTH`
# (intentionally lower than dyce.h's 1024 default to keep AnyDice-style
# float-floor compatibility).
#
# Display precision is the decimal places passed to `H.format`. Matches
# `dyce.h.DEFAULT_PRECISION = 2`. The float64 noise floor for values in
# the [0.0, 100.0] percent range sits around 13 decimal places, so values
# above ~13 just print binary-to-decimal-conversion garbage.
_DEFAULT_CALC_BIT_WIDTH: int = 256  # DEFAULT_QUANTIZATION_BIT_WIDTH
_DEFAULT_DISPLAY_PRECISION: int = DEFAULT_PRECISION

# Symbolic resolution tables. The user may write either an integer literal
# or one of these strings as the value of `set "anydyce: ... precision" to
# X`. "exact" for calculation precision means "no quantization" (signalled
# by bit_width=0; see interpreter.py for the actual skip). "exact" for
# display precision means "as many decimals as float64 can meaningfully
# represent in the [0, 100] percent range" (~13).
_CALC_SYMBOLIC: dict[str, int] = {
    "default": _DEFAULT_CALC_BIT_WIDTH,
    "low": 64,
    "medium": 256,
    "high": 1024,
    "exact": 0,
}
_DISPLAY_SYMBOLIC: dict[str, int] = {
    "default": _DEFAULT_DISPLAY_PRECISION,
    "low": 0,
    "medium": 2,
    "high": 6,
    "exact": 13,
}

_DEFAULTS: dict[str, int | str] = {
    "position order": "highest first",
    "maximum function depth": 10,
    "explode depth": 2,
    "anydyce: calculation precision": _DEFAULT_CALC_BIT_WIDTH,
    "anydyce: display precision": _DEFAULT_DISPLAY_PRECISION,
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

# Settings that accept a non-negative integer (>= 0) OR one of the symbolic
# strings in the corresponding table above. 0 has a key role for
# calculation precision (= no quantization).
_NON_NEGATIVE_INT_OR_SYMBOLIC: dict[str, dict[str, int]] = {
    "anydyce: calculation precision": _CALC_SYMBOLIC,
    "anydyce: display precision": _DISPLAY_SYMBOLIC,
}


class Settings:
    def __init__(self) -> None:
        self._data: dict[str, int | str] = dict(_DEFAULTS)

    def get(self, key: str) -> int | str:
        if key in self._data:
            return self._data[key]
        else:
            raise KeyError(f"unknown setting: {key!r}")

    def set(self, key: str, value: int | str) -> None:  # noqa: C901
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
        elif key in _NON_NEGATIVE_INT_OR_SYMBOLIC:
            symbolic_table = _NON_NEGATIVE_INT_OR_SYMBOLIC[key]
            if isinstance(value, str):
                if value not in symbolic_table:
                    raise ValueError(
                        f"invalid value {value!r} for setting {key!r}; "
                        f"expected a non-negative integer or one of "
                        f"{sorted(symbolic_table.keys())}"
                    )
                value = symbolic_table[value]
            elif isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(
                    f"invalid value {value!r} for setting {key!r}; "
                    f"expected a non-negative integer or one of "
                    f"{sorted(symbolic_table.keys())}"
                )
            elif value < 0:
                raise ValueError(
                    f"{key!r} requires a non-negative integer (got {value!r})"
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

    @property
    def calc_bit_width(self) -> int:
        return cast("int", self._data["anydyce: calculation precision"])

    @property
    def display_precision(self) -> int:
        return cast("int", self._data["anydyce: display precision"])

    def highest_first(self) -> bool:
        return self._data["position order"] == "highest first"
