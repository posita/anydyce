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
from json import JSONDecodeError

import pytest

from anydyce.anydice.fetch import (
    EmptyProgramError,
    NoSuchProgramError,
    _extract_program_from_var_loaded_program,
    extract_program_from_json,
    sharded_subpath_from_program_id,
)

__all__ = ()


class TestExtractProgramFromJson:
    def test_basic(self) -> None:
        extracted = extract_program_from_json(
            r'''"output 3d6 named \"3d6\"
\noutput [highest 3 of 4d6] named \"highest 3 of 4d6\""''',
            program_id_hex="",
            program_url="",
        )
        assert (
            extracted
            == 'output 3d6 named "3d6"\n\noutput [highest 3 of 4d6] named "highest 3 of 4d6"'
        )

    def test_bad_json(self) -> None:
        program_id_hex = "abc123"
        program_url = "file:///from/nowhere/abc123.html"
        with pytest.raises(JSONDecodeError):
            extract_program_from_json(
                r"Ka-BLAM!",
                program_id_hex=program_id_hex,
                program_url=program_url,
            )

    def test_empty_program(self) -> None:
        program_id_hex = "abc123"
        program_url = "file:///from/nowhere/abc123.html"
        with pytest.raises(
            EmptyProgramError, match=rf"\bempty program\b.*{re.escape(program_id_hex)}"
        ):
            extract_program_from_json(
                r'""',
                program_id_hex=program_id_hex,
                program_url=program_url,
            )

    def test_no_such_program(self) -> None:
        program_id_hex = "abc123"
        program_url = "file:///from/nowhere/abc123.html"
        with pytest.raises(
            NoSuchProgramError,
            match=rf"\bno such program\b.*{re.escape(program_id_hex)}.*{re.escape(program_url)}",
        ):
            extract_program_from_json(
                r'"output 0 \\ Sorry, AnyDice does not have the program you requested. \\"',
                program_id_hex=program_id_hex,
                program_url=program_url,
            )

    def test_extract_program_from_var_loaded_program(self) -> None:
        html = r"""<!DOCTYPE html>
<html lang="en"><head><title>Fake</title>
<script>var loadedProgram = "

output 3d6 named \"3d6\"
\noutput [highest 3 of 4d6] named \"highest 3 of 4d6\"

        ";$(function(){});</script>
<body>Fake</body>
</html>"""
        extracted = _extract_program_from_var_loaded_program(
            html, program_id_hex="", program_url=""
        )
        assert (
            extracted
            == '\n\noutput 3d6 named "3d6"\n\noutput [highest 3 of 4d6] named "highest 3 of 4d6"\n\n        '
        )

    def test_extract_program_from_var_loaded_program_empty_program(self) -> None:
        program_id_hex = "abc123"
        program_url = "file:///from/nowhere/abc123.html"
        html = r"""<!DOCTYPE html>
<html lang="en"><head><title>Fake</title>
<body>Nothing to see here!</body>
</html>"""
        with pytest.raises(
            EmptyProgramError,
            match=rf"\bprogram entry missing\b.*{re.escape(program_id_hex)}",
        ):
            _extract_program_from_var_loaded_program(
                html, program_id_hex=program_id_hex, program_url=program_url
            )


class TestShardedSubpathFromProgramId:
    def test_positive_short(self) -> None:
        assert sharded_subpath_from_program_id("f").as_posix() == "00/0f/f.txt"

    def test_positive_exact(self) -> None:
        assert sharded_subpath_from_program_id("abcd").as_posix() == "ab/cd/abcd.txt"

    def test_positive_long(self) -> None:
        assert (
            sharded_subpath_from_program_id("1a2b3c").as_posix() == "2b/3c/1a2b3c.txt"
        )

    def test_negative_short_omits_minus_in_dirs(self) -> None:
        assert sharded_subpath_from_program_id("-f").as_posix() == "00/0f/-f.txt"

    def test_negative_exact_omits_minus_in_dirs(self) -> None:
        assert sharded_subpath_from_program_id("-abc").as_posix() == "0a/bc/-abc.txt"
        assert sharded_subpath_from_program_id("-abcd").as_posix() == "ab/cd/-abcd.txt"

    def test_negative_long_omits_minus_in_dirs(self) -> None:
        assert (
            sharded_subpath_from_program_id("-1a2b3c").as_posix() == "2b/3c/-1a2b3c.txt"
        )
