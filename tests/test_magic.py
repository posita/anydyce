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

import re
import warnings

import pytest
from dyce import TruncationWarning
from dyce.lifecycle import ExperimentalWarning
from IPython.core.interactiveshell import InteractiveShell
from lark.exceptions import UnexpectedToken

from anydyce import magic as magic_mod
from anydyce.anydice import AnyDiceResultsT
from anydyce.magic import anyd, load_ipython_extension


@pytest.fixture(scope="session")
def ipython_shell() -> InteractiveShell:
    # InteractiveShell.instance is a singleton that always returns a valid shell. This
    # is safer for tests than using IPython.testing.globalipapp.get_ipython, whose
    # backing (start_ipython) is once-only and can return None on subsequent calls.
    return InteractiveShell.instance()


class TestAnydMagicBasic:
    def test_single_output_default_format(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        anyd("", "output 3d6")
        out = capsys.readouterr().out
        assert re.search(r"^==== output 1 ====$", out, re.MULTILINE)
        # Default uses H.format, which is multi-line and includes "avg" header
        assert re.search(r"\bavg\b", out)

    def test_single_output_short_format(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        anyd("--short", "output 1d6")
        out = capsys.readouterr().out
        assert re.search(r"^==== output 1 ====$", out, re.MULTILINE)
        # Short uses H.format_short, which emits a single-line {...}, where H.format has
        # no braces and uses `|`-delimited rows
        assert "{" in out
        assert "}" in out
        assert "|" not in out

    def test_named_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        anyd("", 'output 1d6 named "my roll"')
        out = capsys.readouterr().out
        assert re.search(r"^==== my roll ====$", out, re.MULTILINE)

    def test_multiple_outputs(self, capsys: pytest.CaptureFixture[str]) -> None:
        anyd("", "output 1d6\noutput 2d6")
        out = capsys.readouterr().out
        assert re.search(r"^==== output 1 ====$", out, re.MULTILINE)
        assert re.search(r"^==== output 2 ====$", out, re.MULTILINE)

    def test_no_output_statements_silent(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        anyd("", "X: 5")
        out = capsys.readouterr().out
        assert out == "(no output)\n"

    def test_empty_cell_silent(self, capsys: pytest.CaptureFixture[str]) -> None:
        anyd("", "")
        out = capsys.readouterr().out
        assert out == "(no output)\n"


class TestAnydMagicArgs:
    def test_precision_passed_through(self, capsys: pytest.CaptureFixture[str]) -> None:
        # This is a sanity check only. A lower precision will produce a coarser
        # histogram. We only assert that both runs succeed and produce *different*
        # output (i.e., the flag actually reached the formatter).
        anyd("--precision 4", "output 4d6")
        coarse = capsys.readouterr().out
        anyd("--precision 64", "output 4d6")
        fine = capsys.readouterr().out
        assert coarse != fine

    def test_precision_passed_through_with_short(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        anyd("--precision 4 --short", "output 4d6")
        coarse = capsys.readouterr().out
        anyd("--precision 64 --short", "output 4d6")
        fine = capsys.readouterr().out
        assert coarse != fine

    def test_invalid_flag_raises(self) -> None:
        from IPython.core.error import UsageError

        with pytest.raises(UsageError):
            anyd("--nonsense", "output 1d6")

    def test_invalid_precision_value_raises(self) -> None:
        from IPython.core.error import UsageError

        with pytest.raises(UsageError):
            anyd("--precision notanint", "output 1d6")


class TestAnydMagicErrorsPropagate:
    def test_parse_error_propagates(self) -> None:
        with pytest.raises(UnexpectedToken):
            anyd("", "this is not valid anydice @@@")

    def test_interpreter_error_propagates(self) -> None:
        with pytest.raises(NameError, match=r"\bundefined function\b"):
            anyd("", "output [undefined function 1 2 3]")


class TestAnydMagicWarnings:
    def test_warning_suppressed(
        self,
        recwarn: pytest.WarningsRecorder,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        original_run = magic_mod.run

        def _emit_deprecation(source: str) -> AnyDiceResultsT:
            warnings.warn("test deprecation", DeprecationWarning, stacklevel=2)
            return original_run(source)

        def _emit_experimental(source: str) -> AnyDiceResultsT:
            warnings.warn("test experimental", ExperimentalWarning, stacklevel=2)
            return original_run(source)

        monkeypatch.setattr(magic_mod, "run", _emit_deprecation)
        anyd("", "output 1d6")

        monkeypatch.setattr(magic_mod, "run", _emit_experimental)
        anyd("", "output 1d6")

        # DeprecationWarnings and ExperimentalWarnings *are* suppressed
        assert not any(
            issubclass(w.category, (DeprecationWarning, ExperimentalWarning))
            for w in recwarn.list
        )

    def test_other_warnings_pass_through(
        self,
        recwarn: pytest.WarningsRecorder,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        original_run = magic_mod.run

        def _emit_truncation(source: str) -> AnyDiceResultsT:
            warnings.warn("test truncation", TruncationWarning, stacklevel=2)
            return original_run(source)

        monkeypatch.setattr(magic_mod, "run", _emit_truncation)
        anyd("", "output 1d6")

        # TruncationWarnings are *not* suppressed
        assert any(issubclass(w.category, TruncationWarning) for w in recwarn.list)


class TestLoadIPythonExtension:
    def test_registers_anyd_magic(self, ipython_shell: InteractiveShell) -> None:
        load_ipython_extension(ipython_shell)
        cell_magics = ipython_shell.magics_manager.magics["cell"]
        assert "anyd" in cell_magics

    def test_registered_magic_runs(
        self,
        capsys: pytest.CaptureFixture[str],
        ipython_shell: InteractiveShell,
    ) -> None:
        load_ipython_extension(ipython_shell)
        ipython_shell.run_cell_magic("anyd", "", "output 2d6")
        out = capsys.readouterr().out
        assert re.search(r"^==== output 1 ====$", out, re.MULTILINE)
