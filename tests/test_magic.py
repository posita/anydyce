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
from collections.abc import Callable

import pytest
from dyce import TruncationWarning
from dyce.lifecycle import ExperimentalWarning
from IPython.core.interactiveshell import InteractiveShell
from lark.exceptions import UnexpectedToken

try:
    import matplotlib as mpl  # noqa: F401
except ImportError:
    pytest.skip("matplotlib not available", allow_module_level=True)


from anydyce import magic as anydyce_magic
from anydyce.anydice import AnyDiceResultsT, Settings
from anydyce.anydice.fetch import NetworkError, NoSuchProgramError
from anydyce.magic import anyd, anyd_load, load_ipython_extension

__all__ = ()

_FetchImpl = Callable[[str], tuple[str, str, str, str]]


class _RecordingShell:
    r"""Minimal shell stub that records `set_next_input` calls."""

    def __init__(self) -> None:
        self.set_next_input_calls: list[tuple[str, bool]] = []

    def set_next_input(self, text: str, *, replace: bool = False) -> None:
        self.set_next_input_calls.append((text, replace))


@pytest.fixture(autouse=True)  # noqa: RUF076
def no_real_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    r"""
    Safety net: any test that reaches `fetch_anydice_program` without first installing a fake (via the `fake_fetch` fixture) raises instead of hitting the network.

    Autouse so it's in place for every test; tests that need a working fake install one via `fake_fetch`, which displaces this blocker for that test only.
    """

    def _blocked(*_args: object, **_kwargs: object) -> tuple[str, str, str, str]:
        raise AssertionError(
            "fetch_anydice_program called in test without configuring fake_fetch"
        )

    monkeypatch.setattr(anydyce_magic, "fetch_anydice_program", _blocked)


@pytest.fixture
def fake_fetch(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[_FetchImpl], None]:
    r"""
    Install a callable as the `fetch_anydice_program` implementation for this test, displacing the autouse `_no_real_fetch` blocker.
    """

    def install(impl: _FetchImpl) -> None:
        monkeypatch.setattr(anydyce_magic, "fetch_anydice_program", impl)

    return install


@pytest.fixture(scope="session")
def ipython_shell() -> InteractiveShell:
    # InteractiveShell.instance is a singleton that always returns a valid shell. This
    # is safer for tests than using IPython.testing.globalipapp.get_ipython, whose
    # backing (start_ipython) is once-only and can return None on subsequent calls.
    return InteractiveShell.instance()


@pytest.fixture
def recording_shell(monkeypatch: pytest.MonkeyPatch) -> _RecordingShell:
    r"""Replace the active IPython shell with a `RecordingShell` stub for this test."""
    shell = _RecordingShell()
    monkeypatch.setattr(anydyce_magic, "get_ipython", lambda: shell)
    return shell


class TestAnydMagicBasic:
    def test_single_output_default_format(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        anyd("--text", "output 3d6")
        out = capsys.readouterr().out
        assert re.search(r"^==== output 1 ====$", out, re.MULTILINE)
        # Default uses H.format, which is multi-line and includes "avg" header
        assert re.search(r"\bavg\b", out)

    def test_single_output_short_format(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        anyd("--short-text", "output 1d6")
        out = capsys.readouterr().out
        assert re.search(r"^==== output 1 ====$", out, re.MULTILINE)
        # Short uses H.format_short, which emits a single-line {...}, where H.format has
        # no braces and uses `|`-delimited rows
        assert "{" in out
        assert "}" in out
        assert "|" not in out

    def test_named_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        anyd("--text", 'output 1d6 named "my roll"')
        out = capsys.readouterr().out
        assert re.search(r"^==== my roll ====$", out, re.MULTILINE)

    def test_multiple_outputs(self, capsys: pytest.CaptureFixture[str]) -> None:
        anyd("--text", "output 1d6\noutput 2d6")
        out = capsys.readouterr().out
        assert re.search(r"^==== output 1 ====$", out, re.MULTILINE)
        assert re.search(r"^==== output 2 ====$", out, re.MULTILINE)

    def test_no_output_statements_silent(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        anyd("--text", "X: 5")
        out = capsys.readouterr().out
        assert out == "(no output)\n"

    def test_empty_cell_silent(self, capsys: pytest.CaptureFixture[str]) -> None:
        anyd("--text", "")
        out = capsys.readouterr().out
        assert out == "(no output)\n"


class TestAnydMagicArgs:
    def test_precision_passed_through(self, capsys: pytest.CaptureFixture[str]) -> None:
        # This is a sanity check only. A lower precision will produce a coarser
        # histogram. We only assert that both runs succeed and produce *different*
        # output (i.e., the flag actually reached the formatter).
        anyd("--text --precision 4", "output 4d6")
        coarse = capsys.readouterr().out
        anyd("--text --precision 64", "output 4d6")
        fine = capsys.readouterr().out
        assert coarse != fine

    def test_precision_passed_through_with_short(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        anyd("--short-text --precision 4", "output 4d6")
        coarse = capsys.readouterr().out
        anyd("--short-text --precision 64 ", "output 4d6")
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
            anyd("--text", "this is not valid anydice @@@")

    def test_interpreter_error_propagates(self) -> None:
        with pytest.raises(NameError, match=r"\bundefined function\b"):
            anyd("--text", "output [undefined function 1 2 3]")


class TestAnydMagicWarnings:
    def test_warning_suppressed(
        self,
        recwarn: pytest.WarningsRecorder,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        original_run = anydyce_magic.run

        def _emit_deprecation(
            source: str, *, settings: Settings | None = None
        ) -> AnyDiceResultsT:
            warnings.warn("test deprecation", DeprecationWarning, stacklevel=2)
            return original_run(source, settings=settings)

        def _emit_experimental(
            source: str, *, settings: Settings | None = None
        ) -> AnyDiceResultsT:
            warnings.warn("test experimental", ExperimentalWarning, stacklevel=2)
            return original_run(source, settings=settings)

        monkeypatch.setattr(anydyce_magic, "run", _emit_deprecation)
        anyd("--text", "output 1d6")

        monkeypatch.setattr(anydyce_magic, "run", _emit_experimental)
        anyd("--text", "output 1d6")

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
        original_run = anydyce_magic.run

        def _emit_truncation(
            source: str, *, settings: Settings | None = None
        ) -> AnyDiceResultsT:
            warnings.warn("test truncation", TruncationWarning, stacklevel=2)
            return original_run(source, settings=settings)

        monkeypatch.setattr(anydyce_magic, "run", _emit_truncation)
        anyd("--text", "output 1d6")

        # TruncationWarnings are *not* suppressed
        assert any(issubclass(w.category, TruncationWarning) for w in recwarn.list)


class TestAnydLoadMagicBasic:
    # `recording_shell` replaces the IPython shell with a stub that records
    # `set_next_input` calls. `fake_fetch` installs a stand-in for
    # `fetch_anydice_program` so the magic never hits the network (the autouse
    # `_no_real_fetch` blocker fires for any test that forgets to do so).

    def test_replaces_cell_on_success(
        self,
        fake_fetch: Callable[[_FetchImpl], None],
        recording_shell: _RecordingShell,
    ) -> None:
        fake_fetch(
            lambda _arg: (
                "4d2",
                "https://anydice.com/program/4d2",
                "https://anydice.com/",
                "output 3d6\n",
            )
        )

        anyd_load("4d2")

        assert len(recording_shell.set_next_input_calls) == 1
        text, replace = recording_shell.set_next_input_calls[0]
        assert replace is True
        assert text.startswith("%%anyd\n")
        assert text.rstrip().endswith("output 3d6")

    def test_program_url_and_input_in_comment(
        self,
        fake_fetch: Callable[[_FetchImpl], None],
        recording_shell: _RecordingShell,
    ) -> None:
        # The fetched-from URL returned by fetch_anydice_program appears in the header,
        # and the replayed `%anyd_load` line echoes what the user originally typed so
        # the cell shows how to re-fetch
        fake_fetch(
            lambda _arg: (
                "4d2",
                "https://anydice.com/program/4d2",
                "https://anydice.com/",
                "output 3d6\n",
            )
        )

        anyd_load("4d2")

        text, _ = recording_shell.set_next_input_calls[0]
        assert "fetched from https://anydice.com/program/4d2" in text
        assert "%anyd_load 4d2\n" in text

    def test_fetched_at_in_comment(
        self,
        fake_fetch: Callable[[_FetchImpl], None],
        recording_shell: _RecordingShell,
    ) -> None:
        fake_fetch(
            lambda _arg: (
                "4d2",
                "https://anydice.com/program/4d2",
                "https://anydice.com/",
                "output 3d6\n",
            )
        )

        anyd_load("4d2")

        text, _ = recording_shell.set_next_input_calls[0]
        # ISO 8601 timestamp with tz offset somewhere in the comment header.
        assert re.search(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}",
            text,
        )

    def test_program_id_passed_to_fetch(
        self,
        fake_fetch: Callable[[_FetchImpl], None],
        # Present for the side-effect of patching anydyce.magic.get_python
        recording_shell: _RecordingShell,  # noqa: ARG002
    ) -> None:
        captured: list[str] = []

        def _capture(arg: str) -> tuple[str, str, str, str]:
            captured.append(arg)
            return (
                "4d2",
                "https://anydice.com/program/4d2",
                "https://anydice.com/",
                "output 3d6\n",
            )

        fake_fetch(_capture)

        anyd_load("4d2")
        anyd_load("https://anydice.com/program/4d2")

        assert captured == [
            "4d2",
            "https://anydice.com/program/4d2",
        ]


class TestAnydLoadMagicErrors:
    def test_no_such_program_propagates(
        self,
        fake_fetch: Callable[[_FetchImpl], None],
        recording_shell: _RecordingShell,
    ) -> None:
        def _raise(_arg: str) -> tuple[str, str, str, str]:
            raise NoSuchProgramError("no such program", program_id_hex="deadbeef")

        fake_fetch(_raise)

        with pytest.raises(NoSuchProgramError):
            anyd_load("deadbeef")

        # Cell must NOT be replaced on failure
        assert recording_shell.set_next_input_calls == []

    def test_network_error_propagates(
        self,
        fake_fetch: Callable[[_FetchImpl], None],
        recording_shell: _RecordingShell,
    ) -> None:
        def _raise(_arg: str) -> tuple[str, str, str, str]:
            raise NetworkError("connection refused")

        fake_fetch(_raise)

        with pytest.raises(NetworkError):
            anyd_load("4d2")

        assert recording_shell.set_next_input_calls == []

    def test_missing_arg_raises(self) -> None:
        from IPython.core.error import UsageError

        with pytest.raises(UsageError):
            anyd_load("")


class TestLoadIPythonExtension:
    def test_registers_anyd_magic(self, ipython_shell: InteractiveShell) -> None:
        load_ipython_extension(ipython_shell)
        cell_magics = ipython_shell.magics_manager.magics["cell"]
        assert "anyd" in cell_magics

    def test_registers_anyd_load_magic(self, ipython_shell: InteractiveShell) -> None:
        load_ipython_extension(ipython_shell)
        line_magics = ipython_shell.magics_manager.magics["line"]
        assert "anyd_load" in line_magics

    def test_registered_magic_runs(
        self,
        capsys: pytest.CaptureFixture[str],
        ipython_shell: InteractiveShell,
    ) -> None:
        load_ipython_extension(ipython_shell)
        ipython_shell.run_cell_magic("anyd", "--text", "output 2d6")
        out = capsys.readouterr().out
        assert re.search(r"^==== output 1 ====$", out, re.MULTILINE)
