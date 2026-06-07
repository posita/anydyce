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

import pytest

from anydyce.anydice.settings import Settings

__all__ = ()


class TestDefaults:
    def test_calc_bit_width_default(self) -> None:
        # See anydyce.anydice.interpreter._DEFAULT_CALC_BIT_WIDTH
        assert Settings().calc_bit_width == 256

    def test_display_precision_default(self) -> None:
        # See anydyce.anydice.interpreter._DEFAULT_DISPLAY_PRECISION
        assert Settings().display_precision == 2


class TestIntValues:
    def test_calc_bit_width_set_to_int(self) -> None:
        s = Settings()
        assert s.calc_bit_width != 512
        s.set("anydyce: calculation precision", 512)
        assert s.calc_bit_width == 512

    def test_calc_bit_width_set_to_zero(self) -> None:
        s = Settings()
        assert s.calc_bit_width != 0
        s.set("anydyce: calculation precision", 0)
        assert s.calc_bit_width == 0

    def test_calc_bit_width_rejects_negative(self) -> None:
        s = Settings()
        with pytest.raises(ValueError, match="non-negative"):
            s.set("anydyce: calculation precision", -1)

    def test_display_precision_set_to_int(self) -> None:
        s = Settings()
        assert s.display_precision != 6
        s.set("anydyce: display precision", 6)
        assert s.display_precision == 6

    def test_display_precision_set_to_zero(self) -> None:
        s = Settings()
        assert s.display_precision != 0
        s.set("anydyce: display precision", 0)
        assert s.display_precision == 0

    def test_display_precision_rejects_negative(self) -> None:
        s = Settings()
        with pytest.raises(ValueError, match="non-negative"):
            s.set("anydyce: display precision", -1)


class TestSymbolicValues:
    @pytest.mark.parametrize(
        ("symbol", "expected"),
        [
            ("low", 64),
            ("medium", 256),
            ("high", 1024),
            ("exact", 0),
            ("default", 256),
        ],
    )
    def test_calc_bit_width_symbolic(self, symbol: str, expected: int) -> None:
        s = Settings()
        s.set("anydyce: calculation precision", symbol)
        assert s.calc_bit_width == expected

    @pytest.mark.parametrize(
        ("symbol", "expected"),
        [
            ("low", 0),
            ("medium", 2),
            ("high", 6),
            ("exact", 13),
            ("default", 2),
        ],
    )
    def test_display_precision_symbolic(self, symbol: str, expected: int) -> None:
        s = Settings()
        s.set("anydyce: display precision", symbol)
        assert s.display_precision == expected

    def test_calc_bit_width_rejects_unknown_symbol(self) -> None:
        s = Settings()
        with pytest.raises(ValueError, match=r"(?i)\binvalid\b"):
            s.set("anydyce: calculation precision", "nonsense")

    def test_display_precision_rejects_unknown_symbol(self) -> None:
        s = Settings()
        with pytest.raises(ValueError, match=r"(?i)\binvalid\b"):
            s.set("anydyce: display precision", "nonsense")
