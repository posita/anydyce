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

import http.cookiejar
import json
import re
import sys
import urllib.request
import urllib.response
from collections.abc import Sequence
from functools import lru_cache
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urljoin, urlparse

__all__ = (
    "ANYDICE_HOST",
    "DEFAULT_HEADERS",
    "AnyDiceError",
    "BadOrMissingProgramIdError",
    "EmptyProgramError",
    "NetworkError",
    "NoSuchProgramError",
    "extract_program_from_json",
    "fetch_anydice_program",
    "gh_mirror_url_for_program_id_hex",
    "program_id_as_hex",
    "program_id_as_int",
)

ANYDICE_HOST = "anydice.com"
DEFAULT_HEADERS = {
    # RFC 9113 requires header keys to be lower case for HTTP/2, but HTTP/1.1 treats
    # header keys as case insensitive. The default appears to be something like
    # "User-agent: Python-urllib/<python-version>" (capital "U", lowercase "a"). Chrome
    # and Firefox both use "User-Agent" (capital "U", capital "A"), so we're sticking
    # with that.
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
}

_ANYDYCE_FETCH_URL_BASE = f"https://{ANYDICE_HOST}/program/"
_GH_MIRROR_URL_BASE = (
    "https://raw.githubusercontent.com/posita/anydice-data/"
    "refs/heads/main/anydice.com/program/"
)
_HEX_PROG_ID_RE = re.compile(r"^[0-9A-Fa-f]+$")
_HEX_PROG_ID_IN_LOC_RE = re.compile(r"/([0-9A-Fa-f]+)(?:\.html)?(?:[?#]|$)")
_VAR_LOADED_PROGRAM_SRC_RE = re.compile(
    r"""
var\ loadedProgram\ =\ "    # literal JS up to the opening quote of the string
(                           # start capture group 1 (all string contents)
  (?:                       # non-capturing group of "one token"
    [^"\\]                  # a char that's NEITHER '"' NOR "\"
    |                       # OR
    \\.                     # a literal backslash followed by a single char (escape sequence)
  )*                        # zero or more such tokens
)                           # end capture group 1
";                          # literal closing quote + semicolon
""",
    re.VERBOSE,
)

# AnyDice signals "no such program" by returning HTTP 200 with a placeholder program
# rather than a 4xx. We exact-match the placeholder text (after trimming surrounding
# whitespace) so that legit programs which merely *contain* the substring (e.g. inside a
# comment) aren't false-positive flagged.
_NOT_FOUND_PLACEHOLDER_TEXT = (
    "output 0 \\ Sorry, AnyDice does not have the program you requested. \\"
)

# Apparently a historical accident, these IDs were saved with content byte-identical to
# the not-found placeholder text (likely before AnyDice settled the "no such program"
# convention). We treat them as real programs, not absent-program responses. (Verified
# against the captured corpus.)
_NOT_FOUND_PLACEHOLDER_LEGIT_IDS = frozenset({0x790, 0x1AF0})


class NetworkError(RuntimeError):
    r"""Raised when a remote response is unexpected (status, host, or content shape)."""


class AnyDiceError(Exception):
    r"""
    Base class for any AnyDice application errors.

    Takes *msg* and *excs* and passes them to the `Exception` construction.
    Optionally takes *program_id_hex* and *program_url*, which are available as attributes.
    """

    def __init__(
        self,
        msg: str,
        excs: Sequence[Exception] = (),
        *,
        program_id_hex: str | None = None,
        program_url: str | None = None,
    ) -> None:
        super().__init__(msg, excs)
        self.program_id_hex = program_id_hex
        self.program_url = program_url


class BadOrMissingProgramIdError(AnyDiceError):
    r"""Raised when a program ID cannot be determined from an input."""


class EmptyProgramError(AnyDiceError):
    r"""Raised when a program was expected and present, but completely empty."""


class NoSuchProgramError(AnyDiceError):
    r"""Raised when there is no program found at a particular ID."""


def check_http_response(resp: urllib.response.addinfourl, expected_host: str) -> str:
    r"""
    Verify *resp* is a 200 from *expected_host* after any redirects and returns the response URL.

    Raises a [`NetworkError`][anydyce.anydice.fetch.NetworkError] on anything else.
    The status check guards against compromised hosts that return 4xx/5xx (caught by urlopen anyway) and against unexpected redirects to a different host (which urllib follows silently for GET).
    """
    status = getattr(resp, "status", None)
    if status and status != 200:
        raise NetworkError(f"unexpected status {status} from {resp.url}")
    final_host = urlparse(resp.url).netloc
    if final_host != expected_host:
        raise NetworkError(
            f"unexpected redirect: requested {expected_host}, got {final_host} ({resp.url})"
        )
    return resp.url


def extract_program_from_json(
    json_str: str, program_id_hex: str, program_url: str | None = None
) -> str:
    r"""
    Extracts a JSON object from *json_str*, which should be a literal JSON string, including enclosing quotes.

    *program_id_hex* and *program_url* are used in error processing.
    Raises an [`EmptyProgramError`][anydyce.anydice.fetch.EmptyProgramError] if the program is missing from the retrieved content or literally the empty string.
    Raises a [`NoSuchProgramError`][anydyce.anydice.fetch.NoSuchProgramError] if a program was returned, but matches the missing placeholder used if *program_id_hex* does not reference a saved program.
    Can also raise a `json.JSONDecodeError` (or possibly other errors) if *json_str* isn't valid JSON.
    """
    # When json.loads is passed a literal JSON string, it will decode a subset of
    # allowed escape sequences (e.g., \n, \\, \", etc.) as JavaScript would.
    # strict=False allows literal control characters to be present without causing an
    # error.
    program = json.loads(json_str, strict=False)
    if not program:
        raise EmptyProgramError(
            f"empty program found in content at {program_id_hex}"
            + (f" ({program_url})" if program_url else ""),
            program_id_hex=program_id_hex,
            program_url=program_url,
        )
    if (
        program.strip() == _NOT_FOUND_PLACEHOLDER_TEXT
        and program_id_as_int(program_id_hex) not in _NOT_FOUND_PLACEHOLDER_LEGIT_IDS
    ):
        raise NoSuchProgramError(
            f"no such program {program_id_hex} exists"
            + (f" ({program_url})" if program_url else ""),
            program_id_hex=program_id_hex,
            program_url=program_url,
        )
    return program


def extract_program_id_hex_and_url(program_loc_or_id: str | int) -> tuple[str, str]:
    r"""
    Returns `(program_id_hex, program_url)`, if discoverable from *program_loc_or_id*.
    Raises a [`BadOrMissingProgramIdError`][anydyce.anydice.fetch.BadOrMissingProgramIdError] otherwise.
    """
    if isinstance(program_loc_or_id, int):
        program_id_hex = program_id_as_hex(program_loc_or_id)
        program_url = _anydice_url_for_program_id_hex(program_id_hex)
    elif _HEX_PROG_ID_RE.match(program_loc_or_id):
        program_id_hex = program_loc_or_id
        program_url = _anydice_url_for_program_id_hex(program_id_hex)
    else:
        m = _HEX_PROG_ID_IN_LOC_RE.search(program_loc_or_id)
        if not m:
            raise BadOrMissingProgramIdError(
                f"unable to determine program ID from location ({program_loc_or_id})",
                program_url=program_loc_or_id,
            )
        program_id_hex = m.group(1)
        program_url = program_loc_or_id
    program_url = (
        program_url
        if urlparse(program_url).scheme
        else Path(program_url).resolve().as_uri()
    )
    return program_id_hex, program_url


def fetch_anydice_program(program_loc_or_id: str | int) -> tuple[str, str, str, str]:
    r"""
    Fetches and caches any program associated with *program_loc_or_id*.
    Returns `(program_id_hex, initial_url, final_url, program)`, if found.

    *program_loc_or_id* can be a location (e.g., `/path/to/.../program_id_hex(.html)`, `file:///path/to/.../program_id_hex(.html)`, `http://.../program_id_hex`), or a hexadecimal program ID string or an `int`.
    If *program_loc_or_id* is a program ID, a URL will be constructed and the program (if any) will be retrieved from AnyDice's website.
    If fetching was successful, subsequent calls on the same *program_loc_or_id* should avoid additional network round trips so long as they remain in-cache.
    Programs from retrieved from local filesystems are not cached.

    Raises a [`BadOrMissingProgramIdError`][anydyce.anydice.fetch.BadOrMissingProgramIdError] if the program ID cannot be determined from *program_loc_or_id*.
    Raises an [`EmptyProgramError`][anydyce.anydice.fetch.EmptyProgramError] if the program is missing from the retrieved content or literally the empty string.
    Raises a [`NetworkError`][anydyce.anydice.fetch.NetworkError] if there was a problem retrieving the content.
    Raises a [`NoSuchProgramError`][anydyce.anydice.fetch.NoSuchProgramError] if a program was returned, but matches the missing placeholder used if *program_id_hex* does not reference a saved program.
    """
    program_id_hex, initial_url = extract_program_id_hex_and_url(program_loc_or_id)
    try:
        mirror_url = gh_mirror_url_for_program_id_hex(program_id_hex)
        final_url, program = fetch_content_for_url_cached(mirror_url)
    except (EmptyProgramError, HTTPError, NetworkError, NoSuchProgramError):
        if is_pyodide():
            raise
        final_url, html = fetch_content_for_url_cached(initial_url)
        program = _extract_program_from_var_loaded_program(
            html, program_id_hex=program_id_hex, program_url=final_url
        )
    return (
        program_id_hex,
        initial_url,
        final_url,
        program,
    )


@lru_cache(maxsize=128)
def fetch_content_for_url_cached(url: str) -> tuple[str, str]:
    r"""
    TODO(posita): Fill this out.
    """
    if is_pyodide():
        from pyodide.http import (  # type: ignore[import-not-found] # ty: ignore[unresolved-import]
            open_url,
        )

        return (url, open_url(url).read())
    else:
        jar = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        opener.addheaders = list(DEFAULT_HEADERS.items())
        with opener.open(url) as resp:
            content_url = check_http_response(resp, urlparse(url).hostname or "")
            raw = resp.read()
        return content_url, raw.decode("utf-8", errors="replace")


def gh_mirror_url_for_program_id_hex(program_id_hex: str) -> str:
    r"""
    Returns the mirror URL for a given *program_hex_id*.
    This is pure formatting.
    It does not guarantee that anything exists at the URL.

        >>> from anydyce.anydice.fetch import gh_mirror_url_for_program_id_hex
        >>> gh_mirror_url_for_program_id_hex("123")
        'https://raw.githubusercontent.com/posita/anydice-data/refs/heads/main/anydice.com/program/01/23/123.txt'
        >>> gh_mirror_url_for_program_id_hex("fedcba98")
        'https://raw.githubusercontent.com/posita/anydice-data/refs/heads/main/anydice.com/program/ba/98/fedcba98.txt'
    """
    sharded_subpath = sharded_subpath_from_program_id(program_id_hex)
    return urljoin(_GH_MIRROR_URL_BASE, sharded_subpath.as_posix())


def is_pyodide() -> bool:
    return "pyodide" in sys.modules


def program_id_as_hex(program_id: str | int) -> str:
    r"""
    Returns *program_id* in hexadecimal string form.

        >>> from anydyce.anydice.fetch import program_id_as_hex
        >>> program_id_as_hex(22)
        '16'
        >>> program_id_as_hex(-255)
        '-ff'
        >>> program_id_as_hex("-abc")
        '-abc'
        >>> program_id_as_hex("Ka-BLAM!")
        Traceback (most recent call last):
          ...
        BadOrMissingProgramIdError: unable to parse program ID: ('Ka-BLAM!')
    """
    try:
        return (
            f"{int(program_id, 16):x}"
            if isinstance(program_id, str)
            else f"{program_id:x}"
        )
    except ValueError as exc:
        raise BadOrMissingProgramIdError(
            f"unable to parse program ID {program_id}", program_id_hex=str(program_id)
        ) from exc


def program_id_as_int(program_id: str | int) -> int:
    r"""
    Returns *program_id* in integer form.

        >>> from anydyce.anydice.fetch import program_id_as_int
        >>> program_id_as_int(22)
        22
        >>> program_id_as_int(-255)
        -255
        >>> program_id_as_int("-abc")
        -2748
        >>> program_id_as_int("Ka-BLAM!")
        Traceback (most recent call last):
          ...
        BadOrMissingProgramIdError: unable to parse program ID: ('Ka-BLAM!')
    """
    try:
        return int(program_id, 16) if isinstance(program_id, str) else program_id
    except ValueError as exc:
        raise BadOrMissingProgramIdError(
            f"unable to parse program ID ({program_id})", program_id_hex=str(program_id)
        ) from exc


def sharded_subpath_from_program_id(program_id: str | int) -> Path:
    r"""
    Returns the canonical sharded subpath of the program file associated with *program_id*.

        >>> from anydyce.anydice.fetch import sharded_subpath_from_program_id
        >>> sharded_subpath_from_program_id("f").as_posix()
        '00/0f/f.txt'
        >>> sharded_subpath_from_program_id("1a2b3c").as_posix()
        '2b/3c/1a2b3c.txt'

    Any minus sign is preserved for the final filename only.

        >>> sharded_subpath_from_program_id("-abc").as_posix()
        '0a/bc/-abc.txt'
    """
    program_id_hex_padded = (
        f"{program_id_as_int(program_id):05x}"  # pad to 5 to account for any negative
    )
    program_id_hex = program_id_as_hex(program_id)
    return (
        Path(program_id_hex_padded[-4:-2]) / program_id_hex_padded[-2:] / program_id_hex
    ).with_suffix(".txt")


def _anydice_url_for_program_id_hex(program_id_hex: str) -> str:
    return urljoin(_ANYDYCE_FETCH_URL_BASE, program_id_hex)


def _extract_program_from_var_loaded_program(
    html: str, *, program_id_hex: str, program_url: str | None = None
) -> str:
    r"""
    Attempts to find the AnyDice program in *html* and calls [`extract_program_from_json`][anydyce.anydice.fetch.extract_program_from_json] it, if found.

    *program_id_hex* and *program_url* are used in error processing.
    Raises an [`EmptyProgramError`][anydyce.anydice.fetch.EmptyProgramError] if the program is missing from *html* or literally the empty string.
    Raises a [`NoSuchProgramError`][anydyce.anydice.fetch.NoSuchProgramError] if a program was returned, but matches the missing placeholder used if *program_id_hex* does not reference a saved program.
    """
    m = _VAR_LOADED_PROGRAM_SRC_RE.search(html)
    if m is None:
        raise EmptyProgramError(
            "program entry missing from content at location"
            + (f" ({program_url})" if program_url else ""),
            program_id_hex=program_id_hex,
            program_url=program_url,
        )
    # The captured group is the JS string literal content
    return extract_program_from_json(
        f'"{m.group(1)}"', program_id_hex=program_id_hex, program_url=program_url
    )
