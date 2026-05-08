#!/usr/bin/env python3
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

import argparse
import http.cookiejar
import json
import multiprocessing
import os
import re
import resource
import signal
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.response
from collections.abc import Iterator  # noqa: TC003
from fractions import Fraction
from functools import reduce
from math import gcd
from pathlib import Path
from urllib.parse import urlparse

from dyce import H
from dyce.anydyce import parse as anydyce_parse
from dyce.anydyce import unparse as anydyce_unparse
from dyce.anydyce.ast_ import (
    BinOp,
    Call,
    DiceBinOp,
    DiceUnary,
    FunctionDef,
    HashOp,
    IfStmt,
    LoopStmt,
    NegOp,
    NotOp,
    OutputStmt,
    PosOp,
    Program,
    RangeElem,
    RangeRepeatElem,
    ResultStmt,
    SeqExpr,
    SetStmt,
    StringExpr,
    ValueElem,
    ValueRepeatElem,
    VarAssign,
)
from dyce.anydyce.interpreter import (
    AnyDiceInterpreter,
    _call_shape,
    _pattern_shape,
)

_DB_DEFAULT = Path(__file__).parent / Path(__file__).with_suffix(".db").name
_ANYDICE_HOST = "anydice.com"
_DEFAULT_HEADERS = {
    # RFC 9113 requires header keys to be lower case for HTTP/2, but HTTP/1.1 treats
    # header keys as case insensitive. The default appears to be something like
    # "User-agent: Python-urllib/<python-version>" (capital "U", lowercase "a"). Chrome
    # and Firefox both use "User-Agent" (capital "U", capital "A"), so we're sticking
    # with that.
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
}
_CALCULATOR_URL = f"https://{_ANYDICE_HOST}/calculator_limited.php"
_CREATE_LINK_URL = f"https://{_ANYDICE_HOST}/createLink.php"

_ID_RE = re.compile(r"/program/([0-9a-fA-F]+)(?:\.html)?(?:[?#]|$)")
_HEX_RE = re.compile(r"^[0-9a-fA-F]+$")
_SRC_RE = re.compile(r'var loadedProgram = "((?:[^"\\]|\\.)*)";')

# AnyDice signals "no such program" by returning HTTP 200 with a placeholder
# program rather than a 4xx. We exact-match the placeholder text (after
# trimming surrounding whitespace) so that legit programs which merely
# *contain* the substring -- e.g. inside a comment -- aren't false-positive
# flagged. The exact text has been legitimately saved at the IDs in the
# allowlist below (people trolled). Add new IDs only when their stored
# program is byte-equal to the placeholder.
_NOT_FOUND_PLACEHOLDER_TEXT = (
    "output 0 \\ Sorry, AnyDice does not have the program you requested. \\"
)
_NOT_FOUND_PLACEHOLDER_LEGIT_IDS = frozenset({0x790, 0x1AF0})


def _is_not_found_placeholder(program: str, requested_id: int) -> bool:
    return (
        program.strip() == _NOT_FOUND_PLACEHOLDER_TEXT
        and requested_id not in _NOT_FOUND_PLACEHOLDER_LEGIT_IDS
    )


class _NetworkError(RuntimeError):
    r"""Raised when a remote response is unexpected (status, host, or content shape)."""


def _check_response(resp: urllib.response.addinfourl, expected_host: str) -> None:
    r"""Verify *resp* is a 200 from *expected_host* after any redirects.

    Aborts on anything else. Status check guards against compromised hosts that
    return 4xx/5xx (caught by urlopen anyway) and against unexpected redirects to
    a different host (which urllib follows silently for GET).
    """
    status = getattr(resp, "status", None)
    if status != 200:
        raise _NetworkError(f"unexpected status {status} from {resp.url}")
    final_host = urlparse(resp.url).netloc
    if final_host != expected_host:
        raise _NetworkError(
            f"unexpected redirect: requested {expected_host}, got {final_host} ({resp.url})"
        )


def _extract_json(body: str) -> str:
    r"""Strip a non-JSON prefix from a response body, returning the JSON portion.

    AnyDice's PHP layer occasionally emits a fatal-error HTML prefix before
    the structured timeout JSON, e.g.:

        <br />\n<b>Fatal error</b>:  Maximum execution time of 5 seconds
        exceeded ... <br />\n{"error":{"message":"...","type":"..."}}

    `json.loads` rejects this because the first non-whitespace char isn't
    `{`/`[`. We find the first `{` and slice from there. If the body is
    already JSON-shaped or has no `{`, it's returned unchanged.
    """
    stripped = body.lstrip()
    if stripped and stripped[0] in "{[":
        return stripped
    idx = body.find("{")
    return body[idx:] if idx >= 0 else body


# ---- Database ------------------------------------------------------------------------


def _canonicalize(program: str) -> str | None:
    r"""Return the canonical form of *program*, or `None` if it does not parse."""
    try:
        return anydyce_unparse(anydyce_parse(program))
    except Exception:  # noqa: BLE001
        return None


def _has_program_id_unique(conn: sqlite3.Connection) -> bool:
    for idx_row in conn.execute("PRAGMA index_list(programs)"):
        if idx_row[2]:  # unique flag
            cols = conn.execute(f"PRAGMA index_info({idx_row[1]})").fetchall()
            if len(cols) == 1 and cols[0][2] == "program_id":
                return True
    return False


def _canonical_is_notnull(conn: sqlite3.Connection) -> bool:
    # PRAGMA table_info row format: (cid, name, type, notnull, dflt_value, pk).
    for row in conn.execute("PRAGMA table_info(programs)"):
        if row[1] == "canonical":
            return bool(row[3])
    return False


def _open_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    has_table = (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='programs'"
        ).fetchone()
        is not None
    )

    if has_table:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(programs)")}
        # Migrate when canonical is missing entirely, when program_id lacks UNIQUE, or
        # when canonical still carries the old NOT NULL constraint that we have since
        # relaxed (NULL canonical now signals a parse failure).
        if (
            "canonical" not in cols
            or not _has_program_id_unique(conn)
            or _canonical_is_notnull(conn)
        ):
            _migrate_to_current_schema(conn)
    else:
        conn.execute(
            """
            CREATE TABLE programs (
                program_id  INTEGER NOT NULL UNIQUE,
                program     TEXT    NOT NULL,
                canonical   TEXT             UNIQUE,
                output      TEXT
            )
            """
        )
        conn.commit()

    # Annotations table: tracks per-program metadata that's not derivable from the
    # source. Today's only use is `kind='anydice-bug'` for programs whose AnyDice
    # output is buggy and we deliberately don't reproduce; verify reclassifies
    # those rows from `mismatch:values` to `divergence:anydice-bug`. Created on
    # first open if missing -- migration is just a fresh CREATE TABLE.
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS annotations (
            program_id  INTEGER NOT NULL,
            kind        TEXT    NOT NULL,
            note        TEXT,
            PRIMARY KEY (program_id, kind),
            FOREIGN KEY (program_id) REFERENCES programs(program_id)
        )
        """
    )
    conn.commit()

    return conn


def _rebuild_programs_table(
    conn: sqlite3.Connection,
    rows: list[tuple[int, str, str | None]],
) -> None:
    # Deduplicate. For programs that parse, dedup by canonical form. For programs that
    # do not parse (canonical=None), dedup by raw program text since there is no
    # canonical key to compare. rows must arrive sorted by program_id DESC so
    # first-seen wins. We also build `kept_by_id`: for every input program_id, the
    # program_id of the row that survives the dedup. This drives annotation
    # migration after the rebuild so a discarded row's annotations follow the
    # canonical content to the kept row.
    seen_canonical: dict[str, tuple[int, str, str | None]] = {}
    seen_unparsable: dict[str, tuple[int, str, str | None]] = {}
    kept_by_id: dict[int, int] = {}
    for program_id, program, output in rows:
        canonical = _canonicalize(program)
        if canonical is not None:
            if canonical not in seen_canonical:
                seen_canonical[canonical] = (program_id, program, output)
            kept_by_id[program_id] = seen_canonical[canonical][0]
        else:
            if program not in seen_unparsable:
                seen_unparsable[program] = (program_id, program, output)
            kept_by_id[program_id] = seen_unparsable[program][0]

    new_rows: list[tuple[int, str, str | None, str | None]] = [
        (pid, prog, can, out) for can, (pid, prog, out) in seen_canonical.items()
    ]
    for pid, prog, out in seen_unparsable.values():
        new_rows.append((pid, prog, None, out))

    # Snapshot annotations before the DROP so we can re-insert them under the
    # translated program_ids after the rebuild. INSERT OR IGNORE on the way back
    # preserves whichever annotation is seen first when a discarded row's
    # annotation collides with an existing annotation on the kept row at the
    # same kind -- rare in practice; users can re-annotate if context drifts.
    annotation_rows = conn.execute(
        "SELECT program_id, kind, note FROM annotations"
    ).fetchall()
    new_annotations = [
        (kept_by_id.get(old_id, old_id), kind, note)
        for old_id, kind, note in annotation_rows
    ]

    # Rename dance inside an explicit transaction so a partial failure leaves the
    # original table intact. isolation_level=None disables Python's own implicit
    # transaction management, letting us control BEGIN/COMMIT/ROLLBACK directly.
    # Python's implicit handling may issue a COMMIT before DDL statements in some
    # Python versions.
    old_isolation = conn.isolation_level
    conn.isolation_level = None
    try:
        conn.execute("BEGIN EXCLUSIVE")
        try:
            conn.execute("DROP TABLE IF EXISTS programs_new")
            conn.execute(
                """
                CREATE TABLE programs_new (
                    program_id  INTEGER NOT NULL UNIQUE,
                    program     TEXT    NOT NULL,
                    canonical   TEXT             UNIQUE,
                    output      TEXT
                )
                """
            )
            conn.executemany(
                "INSERT INTO programs_new (program_id, program, canonical, output)"
                " VALUES (?, ?, ?, ?)",
                new_rows,
            )
            conn.execute("DROP TABLE programs")
            conn.execute("ALTER TABLE programs_new RENAME TO programs")
            # Re-establish annotations under the translated program_ids.
            conn.execute("DELETE FROM annotations")
            conn.executemany(
                "INSERT OR IGNORE INTO annotations (program_id, kind, note)"
                " VALUES (?, ?, ?)",
                new_annotations,
            )
            conn.execute("COMMIT")
            conn.execute("VACUUM")
        except Exception:
            conn.execute("ROLLBACK")
            raise
    finally:
        conn.isolation_level = old_isolation


def _migrate_to_current_schema(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        "SELECT program_id, program, output FROM programs ORDER BY program_id DESC"
    ).fetchall()
    _rebuild_programs_table(conn, rows)


# ---- Fetch helpers -------------------------------------------------------------------


def _normalize_fetch_arg(arg: str) -> str:
    # Already has a URL scheme. Return as-is.
    if urlparse(arg).scheme:
        return arg
    # Exists as a local path. Return as-is (bare path -> file:// in _fetch_html).
    if Path(arg).exists():
        return arg
    # Looks like a bare hex program ID. Expand to full URL.
    if _HEX_RE.match(arg):
        return f"https://anydice.com/program/{arg}"
    # Otherwise use as-is and let it fail naturally.
    return arg


def _program_id_from_url(url: str) -> int | None:
    parsed = urlparse(url)
    m = _ID_RE.search(parsed.path)
    if m is None:
        return None
    return int(m.group(1), 16)


def _try_program_id(arg: str) -> int | None:
    # Bare hex ID -- handles positives ("42b06") and the negative IDs used by
    # `link --fake` ("-1", "-2", ...). `int(s, 16)` accepts a leading sign.
    try:
        return int(arg, 16)
    except ValueError:
        pass
    return _program_id_from_url(arg)


def _fetch_html(url: str) -> str:
    # Treat bare paths as file:// URLs.
    if not urlparse(url).scheme:
        url = Path(url).resolve().as_uri()
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    opener.addheaders = list(_DEFAULT_HEADERS.items())
    with opener.open(url) as resp:
        if urlparse(url).scheme in ("http", "https"):
            _check_response(resp, _ANYDICE_HOST)
        raw = resp.read()
    return raw.decode("utf-8", errors="replace")


def _extract_program(html: str) -> str | None:
    m = _SRC_RE.search(html)
    if m is None:
        return None
    # The captured group is the JS string literal content; json.loads decodes escape
    # sequences (\n, \\, \", etc.) exactly as JavaScript would. strict=False accepts
    # literal control characters embedded in the string.
    return json.loads(f'"{m.group(1)}"', strict=False)


def _upsert_program(conn: sqlite3.Connection, program_id: int, program: str) -> str:
    r"""Insert or update a program row, deduplicating on canonical form.

    Returns `#!python 'added'`, `#!python 'updated'` (existing row had a lower ID), or `#!python 'duplicate'`.
    The original program text is preserved on update to retain any comments.
    Programs that do not parse (`canonical` is `#!python None`) deduplicate on raw
    program text instead.
    """
    canonical = _canonicalize(program)
    if canonical is not None:
        row = conn.execute(
            "SELECT program_id FROM programs WHERE canonical = ?", (canonical,)
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT program_id FROM programs WHERE canonical IS NULL AND program = ?",
            (program,),
        ).fetchone()

    if row is None:
        conn.execute(
            "INSERT INTO programs (program_id, program, canonical) VALUES (?, ?, ?)",
            (program_id, program, canonical),
        )
        conn.commit()
        return "added"

    existing_id: int = row[0]
    if program_id > existing_id:
        # Update the ID but leave the original program text untouched.
        # Annotations keyed by the old ID migrate alongside so the rationale
        # stays attached to the (now upgraded) row.
        conn.execute(
            "UPDATE programs SET program_id = ? WHERE program_id = ?",
            (program_id, existing_id),
        )
        conn.execute(
            "UPDATE annotations SET program_id = ? WHERE program_id = ?",
            (program_id, existing_id),
        )
        conn.commit()
        return "updated"

    return "duplicate"


# ---- Compute helpers -----------------------------------------------------------------


def _create_link(program: str) -> int:
    data = urllib.parse.urlencode({"program": program}).encode()
    req = urllib.request.Request(
        _CREATE_LINK_URL, data=data, headers=_DEFAULT_HEADERS, method="POST"
    )
    with urllib.request.urlopen(req) as resp:  # noqa: S310
        _check_response(resp, _ANYDICE_HOST)
        body = resp.read().decode("utf-8").strip()
    # Expected response shape: a URL like https://anydice.com/program/1a2b
    program_id = _program_id_from_url(body)
    if program_id is None:
        raise _NetworkError(f"unexpected response body from createLink.php: {body!r}")
    return program_id


def _print_timeout_retry(timeout: float, attempt: int, retries: int) -> None:
    print(
        f"warning: request timed out after {timeout}s, retrying "
        f"(attempt {attempt + 1}/{retries + 1})",
        file=sys.stderr,
    )


def _post_program(program: str, *, timeout: float = 30.0, retries: int = 1) -> str:
    data = urllib.parse.urlencode({"program": program}).encode()
    req = urllib.request.Request(
        _CALCULATOR_URL, data=data, headers=_DEFAULT_HEADERS, method="POST"
    )
    # AnyDice occasionally echoes raw request bytes back inside an error
    # response without re-encoding, producing invalid UTF-8. errors="replace"
    # lets us preserve the structural JSON and substitute U+FFFD for the bad
    # bytes inside string values rather than crashing the helper.
    saw_http_error = False
    attempt = 0
    while True:
        attempt += 1
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
                _check_response(resp, _ANYDICE_HOST)
                body = resp.read().decode("utf-8", errors="replace")
            break
        except urllib.error.HTTPError as exc:
            # AnyDice returns 500 with a structured JSON error body for execution
            # errors such as timeouts. AnyDice returns 503 with an HTML body when
            # certain programs crash its infrastructure (e.g. very large d-face
            # counts trigger an OOM). Preserve both as legitimate results so the
            # row records the failure mode and we don't keep retrying. Other HTTP
            # codes propagate.
            if exc.code not in (500, 503):
                raise
            if urlparse(exc.url or "").netloc != _ANYDICE_HOST:
                raise _NetworkError(f"unexpected redirect on error: {exc.url}") from exc
            if exc.code == 503:
                # 503 body is HTML, not JSON. Synthesize a recognizable JSON
                # marker so the output column stays JSON-shaped and `_classify`
                # can bucket the row as `anydice-503` via the error.type field.
                return json.dumps(
                    {
                        "error": {
                            "type": "Infrastructure503",
                            "message": (
                                "AnyDice returned 503 Service Unavailable "
                                "(likely OOM or infrastructure timeout on "
                                "AnyDice's end)"
                            ),
                        }
                    }
                )
            body = exc.read().decode("utf-8", errors="replace")
            saw_http_error = True
            break
        except urllib.error.URLError as exc:
            # Connect-time timeouts surface as URLError(reason=TimeoutError).
            # Retry once before raising so a single stuck request doesn't fail
            # the row outright. On final exhaustion we re-raise rather than
            # synthesizing a marker -- a stuck request is a transient condition,
            # not a property of the program, so `cmd_compute`'s except-clause
            # prints an error and the row stays NULL for natural pickup on the
            # next `compute --all`.
            if isinstance(exc.reason, TimeoutError) and attempt <= retries:
                _print_timeout_retry(timeout, attempt, retries)
                continue
            raise
        except TimeoutError:
            # Read-time timeouts propagate bare from the socket layer (vs the
            # URLError wrap on connect-time timeouts). Same retry policy.
            if attempt <= retries:
                _print_timeout_retry(timeout, attempt, retries)
                continue
            raise
    # AnyDice can return 500 with an empty body when the request exhausts
    # server-side resources (e.g. memory for `1d200000000`). Treat that as a
    # legitimate-but-opaque outcome and store the empty string.
    if saw_http_error and not body:
        return body
    # Expected response shape: a JSON object containing either "distributions"
    # or "error" at the top level. Anything else (e.g. an HTML page from a
    # compromised host) is rejected before any DB mutation. strict=False
    # tolerates literal control characters inside string values, which AnyDice
    # is known to emit for some calculation-error messages. _extract_json
    # strips a non-JSON HTML prefix that AnyDice's PHP layer emits with
    # certain timeout/fatal-error responses.
    body = _extract_json(body)
    try:
        parsed = json.loads(body, strict=False)
    except json.JSONDecodeError:
        # AnyDice can truncate mid-stream when its calculation times out
        # *while* serializing results (vs. before, which produces a clean
        # `error` JSON). The truncated body is unparsable. Synthesize a
        # recognizable JSON marker so the row gets stored and `_classify`
        # can bucket it as `anydice-bad-json` cleanly. Capture the first
        # 200 chars of the raw body in the message for diagnosis. Verified
        # via 321d9 which times out mid-stream when AnyDice is otherwise
        # idle but produces a clean `Maximum execution time` error under
        # parallel load.
        return json.dumps(
            {
                "error": {
                    "type": "BadJSON",
                    "message": (
                        "AnyDice response could not be parsed as JSON "
                        "(likely truncated mid-stream). First 200 chars: "
                        f"{body[:200]!r}"
                    ),
                }
            }
        )
    # AnyDice returns an empty object `{}` when a program runs to completion
    # without reaching any `output` statement (e.g. a guarded branch that
    # produces nothing). Treat that as a legitimate result. Non-empty dicts
    # must carry one of the two documented top-level keys.
    if not isinstance(parsed, dict) or (
        parsed and "distributions" not in parsed and "error" not in parsed
    ):
        raise _NetworkError(
            f"unexpected JSON shape from calculator_limited.php: {body[:200]!r}"
        )
    return body


def _store_output(
    conn: sqlite3.Connection, program_id: int, output: str, *, force: bool
) -> tuple[str, str | None]:
    r"""
    Store output for the given program_id and return (*status*, *old_output*).

    *status* is one of `#!python 'computed'`, `#!python 'skipped'`, `#!python 'unchanged'`, or `#!python 'changed'`.
    *old_output* is the previous value when status is `#!python 'changed'`, else `#!python None`.
    `#!python 'changed'` means `--force` was set and the new result differs from the stored one.
    """
    row = conn.execute(
        "SELECT output FROM programs WHERE program_id = ?", (program_id,)
    ).fetchone()

    if row is None:
        # Shouldn't happen if the caller resolved IDs from the DB, but be safe
        return "skipped", None

    existing_output: str | None = row[0]

    if existing_output is not None and not force:
        return "skipped", None

    if existing_output == output:
        return "unchanged", None

    conn.execute(
        "UPDATE programs SET output = ? WHERE program_id = ?",
        (output, program_id),
    )
    conn.commit()
    status = "changed" if existing_output is not None else "computed"
    return status, existing_output


# ---- Subcommand implementations ------------------------------------------------------


def _is_remote(url: str) -> bool:
    return urlparse(url).scheme in ("http", "https")


def _abort_remote_disabled(command: str) -> None:
    print(
        f"error: {command} requires --allow-remote (this command contacts "
        f"{_ANYDICE_HOST}; only enable when you trust the upstream site)",
        file=sys.stderr,
    )
    sys.exit(2)


def cmd_fetch(
    urls: list[str], db_path: Path, *, debug: bool, allow_remote: bool
) -> None:
    conn = _open_db(db_path)

    for url in urls:
        url = _normalize_fetch_arg(url)  # noqa: PLW2901

        if debug:
            print(f"debug: processing {url}", file=sys.stderr)

        if _is_remote(url) and not allow_remote:
            print(f"warning: skipping remote URL {url} (use --allow-remote to enable)")
            continue

        try:
            program_id = _program_id_from_url(url)
            if program_id is None:
                print(f"warning: no hex program ID in URL, skipping: {url}")
                continue

            html = _fetch_html(url)

            program = _extract_program(html)
            if program is None:
                print(f"warning: loadedProgram not found in page: {url}")
                continue

            if _is_not_found_placeholder(program, program_id):
                # AnyDice returned its "no such program" placeholder for a
                # program_id that isn't the legit 1af0 save. Don't pollute the
                # DB.
                print(
                    f"warning: AnyDice has no program at id={program_id:x} "
                    "(returned the not-found placeholder); skipping"
                )
                continue

            status = _upsert_program(conn, program_id, program)
            hex_id = f"{program_id:x}"
            print(f"{status}: program_id={hex_id} ({url})")
        except _NetworkError:
            # Abort the whole batch: a network anomaly may indicate the upstream
            # is compromised, and continuing risks corrupting the DB.
            raise
        except Exception as exc:  # noqa: BLE001
            print(f"error: {type(exc).__name__}: {exc} ({url})")

    conn.close()


def _next_fake_id(conn: sqlite3.Connection) -> int:
    r"""Return the next auto-assigned fake program_id (a negative integer).

    Negative IDs distinguish locally-stored programs from AnyDice-assigned
    IDs (always positive). Each call returns one less than the current
    minimum, so successive calls walk -1, -2, -3, ... regardless of whether
    earlier fakes have since been merged away by `recanon` upgrades.
    """
    row = conn.execute("SELECT MIN(program_id) FROM programs").fetchone()
    current_min = row[0] if row[0] is not None else 0
    return min(current_min, 0) - 1


def cmd_link(
    programs: list[str],
    db_path: Path,
    *,
    debug: bool,
    allow_remote: bool,
    fake_auto: bool = False,
    fake_id: int | None = None,
) -> None:
    is_fake = fake_auto or fake_id is not None
    if not is_fake and not allow_remote:
        _abort_remote_disabled("link")
    conn = _open_db(db_path)

    for program in programs:
        if debug:
            verb = "fake-linking" if is_fake else "linking"
            print(f"debug: {verb} {program!r}", file=sys.stderr)

        try:
            if fake_auto:
                program_id = _next_fake_id(conn)
            elif fake_id is not None:
                program_id = fake_id
            else:
                program_id = _create_link(program)
            status = _upsert_program(conn, program_id, program)
            hex_id = f"{program_id:x}"
            print(f"{status}: program_id={hex_id}")
        except _NetworkError:
            raise
        except Exception as exc:  # noqa: BLE001
            print(f"error: {type(exc).__name__}: {exc} ({program!r})")

    conn.close()


def cmd_recanon(db_path: Path, *, debug: bool) -> None:
    conn = _open_db(db_path)

    old_rows = conn.execute(
        "SELECT program_id, program, canonical, output FROM programs"
        " ORDER BY program_id DESC"
    ).fetchall()

    changed: list[tuple[int, str | None, str | None]] = []  # (program_id, old, new)
    for program_id, program, old_canonical, _ in old_rows:
        new_canonical = _canonicalize(program)
        if new_canonical != old_canonical:
            changed.append((program_id, old_canonical, new_canonical))

    rows = [(r[0], r[1], r[3]) for r in old_rows]  # (program_id, program, output)
    _rebuild_programs_table(conn, rows)

    new_count = conn.execute("SELECT COUNT(*) FROM programs").fetchone()[0]
    merged = len(old_rows) - new_count

    if not changed and not merged:
        print("no changes")
    else:
        if changed:
            print(f"updated: {len(changed)} canonical(s) changed")
        if merged:
            print(f"merged: {merged} duplicate(s) removed")

    if debug:
        for program_id, old_canonical, new_canonical in changed:
            hex_id = f"{program_id:x}"
            print(f"  program_id={hex_id}", file=sys.stderr)
            print(f"    old: {old_canonical!r}", file=sys.stderr)
            print(f"    new: {new_canonical!r}", file=sys.stderr)

    conn.close()


# ---- Annotations ---------------------------------------------------------------------

# The set of annotation kinds we currently support. Extend here when adding new
# divergence-classification categories. `verify` re-buckets `mismatch:values`
# rows that have an `anydice-bug` annotation as `divergence:anydice-bug`.
_ANNOTATION_KINDS: frozenset[str] = frozenset({"anydice-bug"})


def _load_annotations(conn: sqlite3.Connection) -> dict[int, dict[str, str | None]]:
    r"""Load all annotations into a `{program_id: {kind: note}}` dict.

    Used by `verify` to reclassify rows in a single in-memory lookup rather
    than per-row queries.
    """
    out: dict[int, dict[str, str | None]] = {}
    for program_id, kind, note in conn.execute(
        "SELECT program_id, kind, note FROM annotations"
    ):
        out.setdefault(program_id, {})[kind] = note
    return out


def cmd_annotate_add(
    hex_id: str,
    kind: str,
    note: str | None,
    db_path: Path,
) -> None:
    if kind not in _ANNOTATION_KINDS:
        print(
            f"error: unknown annotation kind {kind!r}; expected one of "
            f"{sorted(_ANNOTATION_KINDS)}",
            file=sys.stderr,
        )
        sys.exit(1)
    program_id = int(hex_id, 16)
    conn = _open_db(db_path)
    exists = conn.execute(
        "SELECT 1 FROM programs WHERE program_id = ?", (program_id,)
    ).fetchone()
    if exists is None:
        print(
            f"error: no program with program_id={hex_id} in {db_path}",
            file=sys.stderr,
        )
        conn.close()
        sys.exit(1)
    conn.execute(
        "INSERT INTO annotations (program_id, kind, note) VALUES (?, ?, ?)"
        " ON CONFLICT(program_id, kind) DO UPDATE SET note=excluded.note",
        (program_id, kind, note),
    )
    conn.commit()
    print(f"annotated program_id={hex_id} kind={kind}")
    conn.close()


def cmd_annotate_list(
    ids: list[str],
    kind_filter: str | None,
    db_path: Path,
) -> None:
    conn = _open_db(db_path)
    if ids:
        int_ids = [int(h, 16) for h in ids]
        placeholders = ",".join("?" * len(int_ids))
        params: list[object] = list(int_ids)
        where = f"program_id IN ({placeholders})"
    else:
        where = "1=1"
        params = []
    if kind_filter is not None:
        where += " AND kind = ?"
        params.append(kind_filter)
    rows = conn.execute(
        f"SELECT program_id, kind, note FROM annotations WHERE {where}"  # noqa: S608
        " ORDER BY program_id, kind",
        params,
    ).fetchall()
    if not rows:
        print("(no annotations match)")
    else:
        for program_id, kind, note in rows:
            print(f"  {program_id:x}  kind={kind}")
            if note:
                for line in note.splitlines():
                    print(f"      {line}")
    conn.close()


def cmd_annotate_remove(
    hex_id: str,
    kind: str,
    db_path: Path,
) -> None:
    program_id = int(hex_id, 16)
    conn = _open_db(db_path)
    cursor = conn.execute(
        "DELETE FROM annotations WHERE program_id = ? AND kind = ?",
        (program_id, kind),
    )
    conn.commit()
    if cursor.rowcount == 0:
        print(f"no annotation removed (program_id={hex_id} kind={kind} not found)")
    else:
        print(f"removed annotation: program_id={hex_id} kind={kind}")
    conn.close()


def cmd_compute(
    ids: list[str],
    db_path: Path,
    *,
    all_missing: bool,
    force: bool,
    delay: float,
    debug: bool,
    allow_remote: bool,
    timeout: float,
) -> None:
    if not allow_remote:
        _abort_remote_disabled("compute")
    conn = _open_db(db_path)

    if ids:
        int_ids = [int(h, 16) for h in ids]
        rows = conn.execute(
            "SELECT program_id, program FROM programs WHERE program_id IN "  # noqa: S608
            f"({','.join('?' * len(int_ids))})",
            int_ids,
        ).fetchall()
        found_ids = {r[0] for r in rows}
        for h, i in zip(ids, int_ids, strict=True):
            if i not in found_ids:
                print(f"warning: program_id={h} not found in database")
    elif all_missing:
        if force:
            rows = conn.execute("SELECT program_id, program FROM programs").fetchall()
        else:
            rows = conn.execute(
                "SELECT program_id, program FROM programs WHERE output IS NULL"
            ).fetchall()
    else:
        print("error: specify HEX_ID(s) or pass --all", file=sys.stderr)
        conn.close()
        sys.exit(1)

    first = True
    for program_id, program in rows:
        hex_id = f"{program_id:x}"

        if not first and delay > 0:
            time.sleep(delay)
        first = False

        if debug:
            print(f"debug: computing program_id={hex_id}", file=sys.stderr)

        try:
            output = _post_program(program, timeout=timeout)
            status, old_output = _store_output(conn, program_id, output, force=force)
            print(f"{status}: program_id={hex_id}")
            if status == "changed":
                print(f"  old: {old_output}")
                print(f"  new: {output}")
        except _NetworkError:
            raise
        except Exception as exc:  # noqa: BLE001
            print(f"error: {type(exc).__name__}: {exc} (program_id={hex_id})")

    conn.close()


# ---- Show helpers -------------------------------------------------------------------


_PCT_RECOVERY_DENOMS = (10**3, 10**4, 10**5, 10**6, 10**7, 10**8, 10**9)
_PCT_RECOVERY_TIGHT_TOL = 1e-9
_PCT_RECOVERY_LOOSE_TOL = 1e-6


def _try_pct_recovery(
    filtered: list[tuple[int, float]], max_denom: int
) -> tuple[dict[int, int], float]:
    r"""Try to recover counts at the given `limit_denominator` bound.

    Returns `(counts, max_round_trip_error)` where the error is the largest
    `abs(recovered_pct - input_pct)` across outcomes.
    """
    fracs = [
        (o, Fraction(str(p)).limit_denominator(max_denom) / 100) for o, p in filtered
    ]
    denom = reduce(lambda a, b: a * b // gcd(a, b), (f.denominator for _, f in fracs))
    counts = {o: int(f * denom) for o, f in fracs}
    total = sum(counts.values())
    if total == 0:
        return counts, float("inf")
    err = max(abs(counts[o] / total * 100 - p) for o, p in filtered)
    return counts, err


_PCT_RECOVERY_T_BOUND = 10**15
# Tolerance for `match:approximate`: absolute difference in percentage space.
# 1e-8 % = 1e-10 in proportion -- comfortably above _pct_to_counts recovery noise
# (~1e-12 in proportion when the limit_denominator fallback fires) and comfortably
# below the smallest real-bug magnitude (e.g. a one-count error in 12d4 produces
# ~6e-6 % differential).
_APPROX_TOLERANCE_PCT = Fraction(1, 10**8)
_PCT_RECOVERY_T_K_MAX = 32


def _try_total(
    filtered: list[tuple[int, float]], total: int, tol: float
) -> dict[int, int] | None:
    r"""Try to recover counts assuming sum-of-counts equals *total*.

    Returns a count dict if every outcome's count rounds cleanly and the
    reconstructed percentages match the input within *tol*. Returns `None`
    otherwise.
    """
    counts = {o: round(p * total / 100) for o, p in filtered}
    if sum(counts.values()) != total:
        return None
    err = max(abs(counts[o] / total * 100 - p) for o, p in filtered)
    if err > tol:
        return None
    return counts


def _pct_to_counts(outcomes: list[list]) -> tuple[dict[int, int], list[str]]:
    r"""Convert `#!python [[outcome, pct], ...]` to `#!python {outcome: count}`.

    Returns the count dict and a list of precision-warning strings (empty if all
    round-trips are within `_PCT_RECOVERY_LOOSE_TOL`).

    Two-stage recovery:

    1. **Estimate total from smallest percentage.** AnyDice's smallest-count outcome
       is typically `1/T` of the total, so `T ≈ 100/p_min`. Try `T = T_est * k` for
       small `k` (handles cases where the smallest count is > 1). This nails the
       common case in microseconds without scanning denominators.

    2. **Fall back to `Fraction.limit_denominator` walk.** For pathological
       distributions where stage 1 fails (e.g. `p_min` doesn't directly reflect a
       count of 1, or AnyDice's printed precision doesn't pin the total uniquely),
       walk denominator bounds 1e3..1e9 and accept the first that round-trips
       within tolerance. If even 1e9 fails, return the 1e9 result with the wider
       warning threshold.
    """
    # AnyDice represents an empty distribution as [[null, null]].
    filtered: list[tuple[int, float]] = [
        (int(o), p) for o, p in outcomes if o is not None and p is not None
    ]
    if not filtered:
        return {}, []

    nonzero_pcts = [p for _, p in filtered if p > 0]
    if nonzero_pcts:
        p_min = min(nonzero_pcts)
        # Skip strategy 1 if p_min is too small for T_est to fit within T_BOUND.
        # p_min <= 100/T_BOUND implies T_est >= T_BOUND, which can also overflow
        # float arithmetic to infinity for extremely small p_min.
        if p_min >= 100.0 / _PCT_RECOVERY_T_BOUND:
            t_est_base = round(100.0 / p_min)
            if 1 <= t_est_base <= _PCT_RECOVERY_T_BOUND:
                for k in range(1, _PCT_RECOVERY_T_K_MAX):
                    total = t_est_base * k
                    if total > _PCT_RECOVERY_T_BOUND:
                        break
                    counts = _try_total(filtered, total, _PCT_RECOVERY_TIGHT_TOL)
                    if counts is not None:
                        return counts, []

    counts: dict[int, int] = {}
    for max_denom in _PCT_RECOVERY_DENOMS:
        counts, err = _try_pct_recovery(filtered, max_denom)
        if err < _PCT_RECOVERY_TIGHT_TOL:
            return counts, []

    warnings: list[str] = []
    total = sum(counts.values())
    for o, pct in filtered:
        recovered = counts[o] / total * 100
        if abs(recovered - pct) > _PCT_RECOVERY_LOOSE_TOL:
            warnings.append(
                f"  outcome {o}: AnyDice={pct:.10f}, recovered={recovered:.10f}"
            )
    return counts, warnings


def _h_expr(counts: dict[int, int]) -> str:
    if not counts:
        return "H({})"
    items = ", ".join(f"{k}: {v}" for k, v in sorted(counts.items()))
    return f"H({{{items}}})"


def cmd_show(args: list[str], db_path: Path) -> None:
    conn = _open_db(db_path)

    for arg in args:
        row = None
        program_id = _try_program_id(arg)
        if program_id is not None:
            row = conn.execute(
                "SELECT program, output FROM programs WHERE program_id = ?",
                (program_id,),
            ).fetchone()
        else:
            canonical = _canonicalize(arg)
            if canonical is not None:
                row = conn.execute(
                    "SELECT program, output FROM programs WHERE canonical = ?",
                    (canonical,),
                ).fetchone()
            else:
                # Argument doesn't parse; match by raw program text only.
                row = conn.execute(
                    "SELECT program, output FROM programs"
                    " WHERE canonical IS NULL AND program = ?",
                    (arg,),
                ).fetchone()

        if row is None:
            print(f"not found: {arg!r}")
            continue

        program, output_json = row
        if output_json is None:
            print(f"no output yet: {program!r}")
            continue

        if output_json == "":
            print(f"resource exhaustion (empty 500 from server): {program!r}")
            continue

        try:
            data = json.loads(_extract_json(output_json), strict=False)
        except json.JSONDecodeError:
            print(f"non-JSON output (likely AnyDice crash): {program!r}")
            continue

        if "error" in data:
            print(f"error: {data['error']['message']!r} ({program!r})")
            continue

        if not data:
            print(f"no distributions produced: {program!r}")
            continue

        dists = data.get("distributions", {})
        dist_data = dists.get("data", [])
        labels = dists.get("labels", [])

        results: list[tuple[str | None, str]] = []
        for i, outcomes in enumerate(dist_data):
            raw_label = labels[i] if i < len(labels) else ""
            label: str | None = raw_label or None
            counts, warnings = _pct_to_counts(outcomes)
            if warnings:
                print(
                    f"warning: precision issue in distribution {i} of {program!r}",
                    file=sys.stderr,
                )
                for w in warnings:
                    print(w, file=sys.stderr)
            results.append((label, _h_expr(counts)))

        parts = [f"({label!r}, {h})" for label, h in results]
        print(f"[{', '.join(parts)}]")

    conn.close()


# ---- Compare ------------------------------------------------------------------------


def cmd_compare(ids: list[str], db_path: Path, *, timeout_s: float) -> None:
    r"""Side-by-side dump of every distribution from our interpreter vs the stored
    AnyDice output for one or more programs. Unlike `verify`, this does NOT
    short-circuit on the first mismatch -- all dists are printed in order, with
    a per-dist match indicator.
    """
    from dyce.anydyce import run

    conn = _open_db(db_path)
    for arg in ids:
        program_id = int(arg, 16)
        row = conn.execute(
            "SELECT program, output FROM programs WHERE program_id = ?",
            (program_id,),
        ).fetchone()
        if row is None:
            print(f"not found: program_id={arg}")
            continue
        program, output_json = row
        if output_json is None:
            print(f"no AnyDice output stored for program_id={arg}")
            continue
        if output_json == "":
            print(f"resource exhaustion (empty 500): program_id={arg}")
            continue
        try:
            data = json.loads(_extract_json(output_json), strict=False)
        except json.JSONDecodeError:
            print(f"non-JSON stored output: program_id={arg}")
            continue
        if "error" in data:
            msg = (
                data["error"].get("message", "")
                if isinstance(data["error"], dict)
                else ""
            )
            print(f"AnyDice errored on program_id={arg}: {msg}")
            continue

        # Bound interpreter wall-clock time.
        prev_handler = signal.signal(signal.SIGALRM, _alarm_handler)
        signal.setitimer(signal.ITIMER_REAL, timeout_s)
        try:
            ours = run(program)
        except _InterpTimeout:
            print(f"interpreter timeout (>{timeout_s}s): program_id={arg}")
            continue
        except Exception as exc:  # noqa: BLE001
            print(f"interpreter error on program_id={arg}: {type(exc).__name__}: {exc}")
            continue
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, prev_handler)

        their_dists = data.get("distributions", {}).get("data", [])
        their_labels = data.get("distributions", {}).get("labels", [])
        n = max(len(ours), len(their_dists))

        print(f"=== program_id={arg} ({n} dist(s)) ===")
        any_diff = False
        for i in range(n):
            our_label, our_h = ours[i] if i < len(ours) else (f"<missing[{i}]>", H({}))
            their_label = their_labels[i] if i < len(their_labels) else "<missing>"
            their_outcomes = their_dists[i] if i < len(their_dists) else []
            their_counts, _ = _pct_to_counts(their_outcomes)
            o = _normalize_counts({int(k): int(v) for k, v in our_h.items()})
            t = _normalize_counts(their_counts)
            if o == t:
                marker = "match"
            elif _proportions_close(o, t):
                marker = "match:approx"
            else:
                marker = "DIFF"
                any_diff = True
            label_match = (
                ""
                if our_label == their_label
                else f" [labels differ: ours={our_label!r}, theirs={their_label!r}]"
            )
            print(f"  dist[{i}] {our_label!r}: {marker}{label_match}")
            if marker != "match":
                print(f"    ours   = {o}")
                print(f"    theirs = {t}")
        if not any_diff:
            print("  all distributions match (or match within tolerance).")
    conn.close()


def cmd_run(source: str, *, timeout_s: float, short: bool, width: int) -> None:
    r"""Run *source* through the anydyce interpreter and print each output's
    distribution. Bounded by `timeout_s` via SIGALRM. Exits 1 on parse error,
    2 on interpreter error or timeout. Output formatting mirrors `H.format()`
    by default (multi-line with avg/std/var and per-outcome bars); `--short`
    switches to `H.format_short()`.
    """
    try:
        program_ast = anydyce_parse(source)
    except Exception as exc:  # noqa: BLE001
        print(f"parse error: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)

    prev_handler = signal.signal(signal.SIGALRM, _alarm_handler)
    signal.setitimer(signal.ITIMER_REAL, timeout_s)
    try:
        results = AnyDiceInterpreter().run(program_ast)
    except _InterpTimeout:
        print(f"interpreter timeout (>{timeout_s}s)", file=sys.stderr)
        sys.exit(2)
    except Exception as exc:  # noqa: BLE001
        print(f"interpreter error: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(2)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, prev_handler)

    for i, (label, h) in enumerate(results):
        if i > 0:
            print()
        print(f"=== {label} ===")
        if not h:
            print("(empty distribution)")
        elif short:
            print(h.format_short())
        else:
            print(h.format(width=width))


# ---- Verify helpers ------------------------------------------------------------------


def _walk_calls(node: object) -> "Iterator[Call]":
    r"""Yield every `Call` reachable from *node*. Recurses into stmt bodies and exprs."""
    if isinstance(node, Call):
        yield node
        for part in node.parts:
            if not isinstance(part, str):
                yield from _walk_calls(part)
    elif isinstance(node, Program):
        for stmt in node.stmts:
            yield from _walk_calls(stmt)
    elif isinstance(node, OutputStmt):
        yield from _walk_calls(node.expr)
        if node.name is not None:
            yield from _walk_calls(node.name)
    elif isinstance(node, FunctionDef):
        for stmt in node.body:
            yield from _walk_calls(stmt)
    elif isinstance(node, LoopStmt):
        yield from _walk_calls(node.over)
        for stmt in node.body:
            yield from _walk_calls(stmt)
    elif isinstance(node, IfStmt):
        for br in node.branches:
            yield from _walk_calls(br.condition)
            for stmt in br.body:
                yield from _walk_calls(stmt)
        if node.else_branch is not None:
            for stmt in node.else_branch.body:
                yield from _walk_calls(stmt)
    elif isinstance(node, VarAssign | ResultStmt):
        yield from _walk_calls(node.expr)
    elif isinstance(node, SetStmt):
        yield from _walk_calls(node.value)
    elif isinstance(node, BinOp):
        yield from _walk_calls(node.left)
        yield from _walk_calls(node.right)
    elif isinstance(node, DiceBinOp):
        yield from _walk_calls(node.n)
        yield from _walk_calls(node.faces)
    elif isinstance(node, DiceUnary):
        yield from _walk_calls(node.faces)
    elif isinstance(node, HashOp | NotOp | NegOp | PosOp):
        yield from _walk_calls(node.expr)
    elif isinstance(node, SeqExpr):
        for elem in node.elems:
            if isinstance(elem, RangeRepeatElem):
                yield from _walk_calls(elem.start)
                yield from _walk_calls(elem.stop)
                yield from _walk_calls(elem.repeat)
            elif isinstance(elem, RangeElem):
                yield from _walk_calls(elem.start)
                yield from _walk_calls(elem.stop)
            elif isinstance(elem, ValueRepeatElem):
                yield from _walk_calls(elem.expr)
                yield from _walk_calls(elem.repeat)
            elif isinstance(elem, ValueElem):
                yield from _walk_calls(elem.expr)
    elif isinstance(node, StringExpr):
        # StrLit/StrVar parts hold no nested expressions.
        pass
    # Number, Var, EmptySeq, str, int, None: terminal.


def _user_function_shapes(program: Program) -> set[tuple[str | None, ...]]:
    return {
        _pattern_shape(stmt.pattern)
        for stmt in program.stmts
        if isinstance(stmt, FunctionDef)
    }


def _shape_display(shape: tuple[str | None, ...]) -> str:
    return "[" + " ".join(p if p is not None else "?" for p in shape) + "]"


def _normalize_counts(counts: dict[int, int]) -> dict[int, int]:
    nonzero = [abs(v) for v in counts.values() if v != 0]
    if not nonzero:
        return dict(counts)
    g = reduce(gcd, nonzero)
    if g <= 1:
        return dict(counts)
    return {k: v // g for k, v in counts.items()}


def _elide_one_sided_zeros(
    ours: dict[int, int], theirs: dict[int, int]
) -> tuple[dict[int, int], dict[int, int]]:
    r"""Drop zero-count entries from each dict that don't appear on the other side.

    Treats `{outcome: 0}` on one side as equivalent to outcome-absent on the
    other. AnyDice's float arithmetic and our exact-rational truncation differ
    in which low-probability outcomes survive as zero-count entries vs. are
    elided entirely; both encode the same probabilistic content (zero
    probability mass either way). Without this elision, 22432-class and
    3d5e2-class precision-tail discrepancies bucket as `mismatch:values` even
    though the actual distributions agree.
    """
    ours_filtered = {k: v for k, v in ours.items() if not (v == 0 and k not in theirs)}
    theirs_filtered = {
        k: v for k, v in theirs.items() if not (v == 0 and k not in ours)
    }
    return ours_filtered, theirs_filtered


def _proportions_close(
    ours: dict[int, int],
    theirs: dict[int, int],
    tol_pct: Fraction = _APPROX_TOLERANCE_PCT,
) -> bool:
    r"""Compare two count dicts as proportions in percentage space.

    Returns `True` iff the outcome sets agree and every per-outcome percentage
    differs by no more than *tol_pct*. Uses `Fraction` exact arithmetic so the
    result has no float-precision artifacts.
    """
    if set(ours) != set(theirs):
        return False
    o_total = sum(ours.values())
    t_total = sum(theirs.values())
    if o_total == 0 or t_total == 0:
        return o_total == t_total
    for k in ours:
        diff = abs(Fraction(ours[k], o_total) - Fraction(theirs[k], t_total)) * 100
        if diff > tol_pct:
            return False
    return True


def _our_results_to_counts(
    results: "list[tuple[str, object]]",
) -> list[dict[int, int]]:
    out: list[dict[int, int]] = []
    for _label, h in results:
        out.append(_normalize_counts({int(k): int(v) for k, v in h.items()}))
    return out


def _their_results_to_counts(data: dict) -> list[dict[int, int]]:
    dists = data.get("distributions", {})
    dist_data = dists.get("data", [])
    out: list[dict[int, int]] = []
    for outcomes in dist_data:
        counts, _warnings = _pct_to_counts(outcomes)
        out.append(_normalize_counts(counts))
    return out


class _InterpTimeout(Exception):  # noqa: N818
    r"""Raised by the SIGALRM handler when interpreter execution exceeds the per-row budget."""


def _alarm_handler(signum: int, frame: object) -> None:  # noqa: ARG001
    raise _InterpTimeout


def _classify(
    program: str,
    output_json: str | None,
    *,
    timeout_s: float,
) -> tuple[str, str | None]:
    r"""Bucket a row.

    Returns `(bucket, detail)`. *bucket* is one of: `match`, `match:approximate`,
    `mismatch:dist-count`, `mismatch:values`, `parse-fail`, `parse-fail:legacy`,
    `interp-error:<ExcType>`, `interp-timeout`, `interp-oom`, `anydice-error`,
    `anydice-503`, `anydice-empty`, `anydice-resource`, `anydice-bad-json`,
    `anydice-bad-shape`, `unrun`. *detail* is a short string for sample reporting,
    or `None`. The `interp-killed` bucket is added by `_verify_isolated` (worker
    died unexpectedly) and never returned by `_classify` directly.

    `match:approximate` covers distributions whose integer counts differ but whose
    proportions agree within `_APPROX_TOLERANCE_PCT` -- typically the result of
    `_pct_to_counts` recovering a different (but mathematically equivalent within
    AnyDice's print precision) rational than ours.
    """
    if output_json is None:
        return "unrun", None
    if output_json == "":
        return "anydice-resource", None

    try:
        data = json.loads(_extract_json(output_json), strict=False)
    except json.JSONDecodeError:
        return "anydice-bad-json", None
    if not isinstance(data, dict):
        return "anydice-bad-shape", None
    if "error" in data:
        msg = ""
        err_type = ""
        if isinstance(data["error"], dict):
            msg = str(data["error"].get("message", ""))
            err_type = str(data["error"].get("type", ""))
        # Distinguish AnyDice infrastructure failures (HTTP 503 turned into a
        # synthetic JSON marker by `_post_program`) from semantic AnyDice
        # errors. 503s are typically reproducible and tied to specific
        # programs (e.g. `output d123456789106` triggers an OOM on AnyDice's
        # side); the dedicated bucket lets verify show them clustered.
        if err_type == "Infrastructure503":
            return "anydice-503", msg
        # BadJSON is also a synthetic marker (from `_post_program` when the
        # response body fails to parse as JSON, typically from a mid-stream
        # truncation). Routes to the existing `anydice-bad-json` bucket.
        if err_type == "BadJSON":
            return "anydice-bad-json", msg
        return "anydice-error", msg
    if not data:
        return "anydice-empty", None

    try:
        program_ast = anydyce_parse(program)
    except Exception as exc:  # noqa: BLE001
        detail = f"{type(exc).__name__}: {exc}"
        # Sub-bucket parse-fails for AnyDice features we deliberately don't
        # support but want to cluster in verify summaries (vs. real parser
        # bugs in our grammar). The Lark error shape `Token('LOWERNAME',
        # 'legacy')` is the unambiguous signature of `output legacy "..."`-
        # style programs; AnyDice's `legacy` notation is a separate
        # mini-language we don't implement.
        if "Token('LOWERNAME', 'legacy')" in detail:
            return "parse-fail:legacy", detail
        return "parse-fail", detail

    # Bound interpreter wall-clock time per program. setitimer accepts floats so we
    # don't have to round timeout up to a whole second. Linux/macOS only; the helper
    # is not expected to run on Windows.
    prev_handler = signal.signal(signal.SIGALRM, _alarm_handler)
    signal.setitimer(signal.ITIMER_REAL, timeout_s)
    try:
        ours = AnyDiceInterpreter().run(program_ast)
    except _InterpTimeout:
        return "interp-timeout", f">{timeout_s}s"
    except MemoryError as exc:
        # Caught before the generic Exception handler so an `interp-oom`
        # bucket surfaces (vs. interp-error:MemoryError). When running with
        # `--isolate`, MemoryError is the typical signal that a worker
        # exceeded its RLIMIT_AS cap; in-process MemoryErrors are rare but
        # bucket the same way.
        return "interp-oom", str(exc)
    except Exception as exc:  # noqa: BLE001
        return f"interp-error:{type(exc).__name__}", str(exc)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, prev_handler)

    our_counts = _our_results_to_counts(ours)
    their_counts = _their_results_to_counts(data)
    our_labels = [label for label, _ in ours]
    their_labels = list(data.get("distributions", {}).get("labels", []))
    if len(our_counts) != len(their_counts):
        return (
            "mismatch:dist-count",
            f"ours = {len(our_counts)} {our_labels!r}; "  # noqa: ISC004
            f"theirs = {len(their_counts)} {their_labels!r}",
        )
    approximate_dists: list[int] = []
    for i, (oc, tc) in enumerate(zip(our_counts, their_counts, strict=True)):
        # Drop one-sided zero-count entries before comparison: a `{k: 0}` on
        # one side and outcome-absent on the other carry the same probabilistic
        # content, just different representations. AnyDice's float arithmetic
        # and our truncation diverge here harmlessly (see 22432, 3d5e2-class).
        oc, tc = _elide_one_sided_zeros(oc, tc)  # noqa: PLW2901
        if oc == tc:
            continue
        # Distinguish a precision-recovery noise mismatch from a real divergence
        # by comparing proportions as exact Fractions, with absolute tolerance
        # `_APPROX_TOLERANCE_PCT` in percentage space.
        if _proportions_close(oc, tc):
            approximate_dists.append(i)
            continue
        olbl = our_labels[i] if i < len(our_labels) else None
        tlbl = their_labels[i] if i < len(their_labels) else None
        label_info = (
            f"dist[{i}] {olbl!r}"
            if olbl == tlbl
            else f"dist[{i}] our label={olbl!r}, their label={tlbl!r}"
        )
        return (
            "mismatch:values",
            f"{label_info}; ours = {oc}; theirs = {tc}",
        )
    if approximate_dists:
        return (
            "match:approximate",
            f"dist indices: {approximate_dists}",
        )
    return "match", None


# ---- Subprocess-isolated verify ------------------------------------------------------


def _verify_worker(
    args: "tuple[int, str, str | None, float]",
) -> "tuple[int, str, str | None]":
    r"""Pool worker entry point. Just calls `_classify` and returns the bucket
    + detail along with the program_id so the parent can route results back
    to their rows. Module-level so it pickles cleanly under `forkserver`.
    """
    program_id, program, output_json, timeout_s = args
    bucket, detail = _classify(program, output_json, timeout_s=timeout_s)
    return program_id, bucket, detail


def _verify_isolated(
    rows: "list[tuple[int, str, str | None]]",
    *,
    timeout_s: float,
    workers: int,
    maxtasksperchild: int,
    debug: bool,
) -> "tuple[dict[str, list[tuple[int, str, str | None]]], int]":
    r"""Run `_classify` for each row in a `forkserver`-backed worker pool.

    Workers inherit the parent's `RLIMIT_AS` at fork time (the parent applies
    it in `cmd_verify`), so per-worker `setrlimit` is unnecessary. Buckets
    surfaced by isolation:

    - `interp-oom`: worker's `MemoryError` from hitting `RLIMIT_AS` (caught in
      `_classify`).
    - `interp-killed`: worker died unexpectedly (kernel SIGKILL via OOM-killer
      or signal-9; segfault; etc.). Detected as a worker-side exception
      surfacing on `AsyncResult.get()`.

    `_classify` enforces its own `SIGALRM`-based wall-clock timeout in the
    worker, so the parent's `get(timeout=...)` is just a safety buffer for
    stuck workers.

    Returns `(buckets, processed_count)`. On `KeyboardInterrupt`, returns the
    partial buckets collected so far; the Pool's `__exit__` cleanly
    terminates remaining workers.
    """
    ctx = multiprocessing.get_context("forkserver")

    rows_by_id: dict[int, tuple[int, str, str | None]] = {
        pid: (pid, prog, out) for pid, prog, out in rows
    }
    buckets: dict[str, list[tuple[int, str, str | None]]] = {}

    if debug:
        print(
            f"debug: starting forkserver Pool: workers={workers}, "
            f"maxtasksperchild={maxtasksperchild}, jobs={len(rows)}",
            file=sys.stderr,
        )

    processed = 0
    with ctx.Pool(
        processes=workers,
        maxtasksperchild=maxtasksperchild,
    ) as pool:
        async_results: list[tuple[int, multiprocessing.pool.AsyncResult]] = [
            (
                program_id,
                pool.apply_async(
                    _verify_worker,
                    ((program_id, program, output_json, timeout_s),),
                ),
            )
            for program_id, program, output_json in rows
        ]

        # Parent-side wait buffer: workers enforce SIGALRM at timeout_s, so the
        # parent only needs enough slack for IPC/unwinding. 10s is generous.
        parent_wait = timeout_s + 10.0
        try:
            for program_id, ar in async_results:
                _, program, _ = rows_by_id[program_id]
                if debug:
                    print(
                        f"debug: collecting program_id={program_id:x}",
                        file=sys.stderr,
                    )
                try:
                    _, bucket, detail = ar.get(timeout=parent_wait)
                except multiprocessing.TimeoutError:
                    # Worker hung past its own SIGALRM; rare, usually means a C
                    # extension didn't honor the alarm. Bucket as timeout and
                    # proceed; the worker will eventually be replaced.
                    bucket, detail = (
                        "interp-timeout",
                        f">{timeout_s}s (parent wait of {parent_wait}s exceeded)",
                    )
                except MemoryError as exc:
                    bucket, detail = "interp-oom", str(exc)
                except Exception as exc:  # noqa: BLE001
                    # Worker died from kernel kill (OOM-killer beyond rlimit,
                    # SIGKILL, segfault) or another unexpected fault. Pool
                    # automatically replaces the dead worker.
                    bucket, detail = (
                        "interp-killed",
                        f"{type(exc).__name__}: {exc}",
                    )
                buckets.setdefault(bucket, []).append((program_id, program, detail))
                processed += 1
        except KeyboardInterrupt:
            # Fall through to the with-block exit; Pool.__exit__ runs
            # pool.terminate() + pool.join() to clean up workers and the
            # forkserver. Buckets contain the partial state collected so far.
            print(
                f"\n*** interrupted after {processed}/{len(rows)} rows ***",
                file=sys.stderr,
            )

    return buckets, processed


def cmd_verify(
    ids: list[str],
    db_path: Path,
    *,
    all_rows: bool,
    summary_only: bool,
    show_max: int,
    builtins_report: bool,
    timeout_s: float,
    debug: bool,
    isolated_workers: int,
    rlimit_mb: int,
    maxtasksperchild: int,
) -> None:
    # Apply RLIMIT_AS on the parent process. Forkserver-spawned workers
    # inherit this limit at fork time, so workers don't need a separate
    # setrlimit. The cap protects both in-process runs (a runaway program's
    # MemoryError gets caught in `_classify` and bucketed as `interp-oom`)
    # and isolated runs (same MemoryError handling, just inside a worker).
    # Pass --rlimit-mb 0 to disable.
    if rlimit_mb > 0:
        rlimit_bytes = rlimit_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (rlimit_bytes, rlimit_bytes))
    conn = _open_db(db_path)

    if ids:
        int_ids = [int(h, 16) for h in ids]
        rows = conn.execute(
            "SELECT program_id, program, output FROM programs WHERE program_id IN "  # noqa: S608
            f"({','.join('?' * len(int_ids))})",
            int_ids,
        ).fetchall()
        found_ids = {r[0] for r in rows}
        for h, i in zip(ids, int_ids, strict=True):
            if i not in found_ids:
                print(f"warning: program_id={h} not found in database")
    elif all_rows:
        rows = conn.execute(
            "SELECT program_id, program, output FROM programs"
        ).fetchall()
    else:
        print("error: specify HEX_ID(s) or pass --all", file=sys.stderr)
        conn.close()
        sys.exit(1)

    if builtins_report:
        from collections import Counter

        builtin_counts: Counter[str] = Counter()
        parse_failures = 0
        for _program_id, program, _output_json in rows:
            try:
                program_ast = anydyce_parse(program)
            except Exception:  # noqa: BLE001
                parse_failures += 1
                continue
            user_shapes = _user_function_shapes(program_ast)
            for call in _walk_calls(program_ast):
                shape = _call_shape(call.parts)
                if shape in user_shapes:
                    continue
                builtin_counts[_shape_display(shape)] += 1

        total_calls = sum(builtin_counts.values())
        print(
            f"=== builtin call frequency "
            f"({len(builtin_counts)} distinct, "
            f"{total_calls} total, "
            f"parse-fail rows skipped: {parse_failures}) ==="
        )
        if builtin_counts:
            width = max(len(s) for s in builtin_counts)
            for shape, n in sorted(
                builtin_counts.items(), key=lambda kv: (-kv[1], kv[0])
            ):
                print(f"  {shape:<{width}}  {n}")
        conn.close()
        return

    annotations = _load_annotations(conn)

    if isolated_workers > 0:
        raw_buckets, processed = _verify_isolated(
            rows,
            timeout_s=timeout_s,
            workers=isolated_workers,
            maxtasksperchild=maxtasksperchild,
            debug=debug,
        )
    else:
        raw_buckets = {}
        processed = 0
        try:
            for program_id, program, output_json in rows:
                if debug:
                    print(
                        f"debug: verifying program_id={program_id:x}",
                        file=sys.stderr,
                    )
                bucket, detail = _classify(program, output_json, timeout_s=timeout_s)
                raw_buckets.setdefault(bucket, []).append((program_id, program, detail))
                processed += 1
        except KeyboardInterrupt:
            print(
                f"\n*** interrupted after {processed}/{len(rows)} rows ***",
                file=sys.stderr,
            )

    interrupted = processed < len(rows)

    # Apply annotation-based reclassification uniformly for both in-process
    # and isolated paths: a `mismatch:values` row with an `anydice-bug`
    # annotation becomes `divergence:anydice-bug`; the annotation note is
    # appended to the detail for context.
    buckets: dict[str, list[tuple[int, str, str | None]]] = {}
    for bucket, entries in raw_buckets.items():
        for program_id, program, detail in entries:
            program_annotations = annotations.get(program_id, {})
            new_bucket = bucket
            if bucket == "mismatch:values" and "anydice-bug" in program_annotations:
                new_bucket = "divergence:anydice-bug"
                note = program_annotations["anydice-bug"]
                if note:
                    detail = (  # noqa: PLW2901
                        f"{detail} | reason: {note}" if detail else f"reason: {note}"
                    )
            buckets.setdefault(new_bucket, []).append((program_id, program, detail))

    total = sum(len(v) for v in buckets.values())
    if interrupted:
        print(
            f"=== verify summary (PARTIAL: {total}/{len(rows)} rows processed before interrupt) ==="
        )
    else:
        print(f"=== verify summary ({total} rows) ===")
    width = max((len(k) for k in buckets), default=0)
    for bucket in sorted(buckets):
        n = len(buckets[bucket])
        print(f"  {bucket:<{width}}  {n:>5}")

    if summary_only:
        conn.close()
        if interrupted:
            sys.exit(130)
        return

    print("\n=== samples ===")
    unlimited = show_max <= 0
    for bucket in sorted(buckets):
        if bucket == "match":
            continue
        sample = buckets[bucket] if unlimited else buckets[bucket][:show_max]
        for program_id, program, detail in sample:
            hex_id = f"{program_id:x}"
            print(f"\n[{bucket}] program_id={hex_id}")
            print(f"  program: {program!r}")
            if detail:
                print(f"  detail:  {detail}")
        rest = len(buckets[bucket]) - len(sample)
        if rest > 0:
            print(f"  ... ({rest} more in {bucket})")

    conn.close()
    if interrupted:
        # Exit 130 (128 + SIGINT) so shell scripts can distinguish a
        # Ctrl-C'd partial run from a normal completion. Partial summary
        # was still printed above so the user sees what was collected.
        sys.exit(130)


# ---- CLI -----------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Manage a local SQLite cache of AnyDice programs and outputs."
    )
    parser.add_argument(
        "--db",
        metavar="PATH",
        type=Path,
        default=_DB_DEFAULT,
        help=f"SQLite database path (default: {_DB_DEFAULT})",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="print extra diagnostic info to stderr while processing",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # ---- fetch -------------------------------------------------------------------
    fetch_parser = subparsers.add_parser(
        "fetch",
        help="Extract a program's source from each argument and insert it into the database. "
        "Each argument may be a hex program ID (e.g. a3f1), a full URL, or a local file path. "
        "A bare hex ID is expanded to https://anydice.com/program/<id>. "
        "If a local file with the same name exists it takes priority. "
        "Each URL must contain a hex program ID in the path (e.g. /program/1a2b or /program/1a2b.html). "
        "On duplicate program text the higher program_id wins. "
        "This allows us to make corrections in the formatting of the programs (e.g., adding clarifying comments, etc.). "
        "URL may be http://, https://, file://, or a bare local path.",
    )
    fetch_parser.add_argument(
        "urls",
        metavar="URL_OR_ID",
        nargs="+",
        help="AnyDice program URL(s) or hex program ID(s)",
    )
    fetch_parser.add_argument(
        "--allow-remote",
        action="store_true",
        help=f"permit http(s) URLs (default-deny because contacting {_ANYDICE_HOST}"
        f" can be unsafe when the upstream is compromised)",
    )

    # ---- link --------------------------------------------------------------------
    link_parser = subparsers.add_parser(
        "link",
        help="POST each program text to https://anydice.com/createLink.php to obtain a permanent program ID, then insert the program and ID into the database as if "
        "fetched independently. "
        "On duplicate program text the higher program_id wins. "
        "Pass --fake to skip the network call and assign a locally-unique negative ID. "
        "Pass --fake-id N to assign a specific negative ID. "
        "Useful when AnyDice's link service is unavailable. "
        "If AnyDice later assigns a real (positive) ID, `recanon` will merge the local row away on the next rebuild since the real ID is higher.",
    )
    link_parser.add_argument(
        "programs", metavar="PROGRAM", nargs="+", help="AnyDice program text(s)"
    )
    link_parser.add_argument(
        "--allow-remote",
        action="store_true",
        help=f"required for the network path; ignored when --fake or --fake-id is set (no network call is made). "
        f"Without --fake/--fake-id, the command contacts {_ANYDICE_HOST}.",
    )
    link_fake_group = link_parser.add_mutually_exclusive_group()
    link_fake_group.add_argument(
        "--fake",
        action="store_true",
        help="auto-assign each program the next available negative ID (skips the network call). "
        "Multiple programs each get their own fake ID.",
    )
    link_fake_group.add_argument(
        "--fake-id",
        metavar="N",
        type=int,
        default=None,
        help="assign the specified negative ID (must be < 0; collides with existing rows are upserted via the standard higher-ID-wins rule). "
        "Requires exactly one program argument.",
    )

    # ---- recanon -----------------------------------------------------------------
    subparsers.add_parser(
        "recanon",
        help="Recompute the canonical form for every row and atomically rebuild the table. "
        "Use this after a parser or unparser change that affects canonical output. "
        "Rows whose canonical forms become identical are merged, keeping the highest program_id. "
        "The original program text is always preserved. "
        "Pass --debug to log each changed canonical to stderr.",
    )

    # ---- compute -----------------------------------------------------------------
    compute_parser = subparsers.add_parser(
        "compute",
        help="POST each program to https://anydice.com/calculator_limited.php and store the JSON result in the output column. "
        "By default only rows with no output are processed. Pass --force to re-fetch existing outputs. "
        'When the new result differs from the stored one it is reported as "changed" and updated.',
    )
    compute_parser.add_argument(
        "--all",
        dest="all_missing",
        action="store_true",
        help="process all rows with missing output (or all rows with --force)",
    )
    compute_parser.add_argument(
        "--force",
        action="store_true",
        help="re-fetch output even for rows that already have one",
    )
    compute_parser.add_argument(
        "--delay",
        metavar="SECONDS",
        type=float,
        default=0.0,
        help="pause between requests (default: 0)",
    )
    compute_parser.add_argument(
        "--timeout",
        metavar="SECONDS",
        type=float,
        default=30.0,
        help="per-request HTTP timeout (default: 30); on timeout the request is retried once, then the row is left untouched for natural pickup on the next run",
    )
    compute_parser.add_argument(
        "ids",
        metavar="HEX_ID",
        nargs="*",
        help="hex program ID(s) to compute (mutually exclusive with --all)",
    )
    compute_parser.add_argument(
        "--allow-remote",
        action="store_true",
        help=f"required to run; this command always contacts {_ANYDICE_HOST}",
    )

    # ---- show --------------------------------------------------------------------
    show_parser = subparsers.add_parser(
        "show",
        help="Translate the stored AnyDice output for one or more programs into Python H expressions suitable for test assertions. "
        "Each argument may be a hex program ID, a full URL, or raw program text. "
        "Warns to stderr if percentage-to-count round-trip error exceeds 1e-6.",
    )
    show_parser.add_argument(
        "programs",
        metavar="PROGRAM_OR_ID",
        nargs="+",
        help="program text, hex program ID, or URL",
    )

    # ---- compare -----------------------------------------------------------------
    compare_parser = subparsers.add_parser(
        "compare",
        help="Side-by-side dump of every distribution from our interpreter vs the stored AnyDice output for one or more programs. "
        "Unlike `verify`, this does NOT short-circuit on the first mismatch. "
        "All dists are  printed in order with a per-dist match indicator.",
    )
    compare_parser.add_argument(
        "ids",
        metavar="HEX_ID",
        nargs="+",
        help="hex program ID(s) to compare",
    )
    compare_parser.add_argument(
        "--timeout",
        metavar="SECONDS",
        type=float,
        default=5.0,
        help="per-program interpreter wall-clock budget (default: 5.0)",
    )

    # ---- run ---------------------------------------------------------------------
    run_parser = subparsers.add_parser(
        "run",
        help="Run an AnyDice program through the dyce.anydyce interpreter and print each output's distribution. "
        "Source may be inline text, read from a file via --file, or read from stdin (positional `-`). "
        "Useful for ad-hoc debugging without round-tripping through the database.",
    )
    run_parser.add_argument(
        "source",
        nargs="?",
        default=None,
        help="program text (or `-` to read from stdin); omit if --file is given",
    )
    run_parser.add_argument(
        "--file",
        dest="file",
        metavar="FILE",
        default=None,
        help="read program text from FILE (mutually exclusive with positional source)",
    )
    run_parser.add_argument(
        "--timeout",
        metavar="SECONDS",
        type=float,
        default=5.0,
        help="interpreter wall-clock budget in seconds (default: 5.0)",
    )
    run_parser.add_argument(
        "--short",
        action="store_true",
        help="print each distribution via H.format_short() instead of the multi-line H.format()",
    )
    run_parser.add_argument(
        "--width",
        metavar="N",
        type=int,
        default=65,
        help="width passed to H.format() (default: 65; ignored when --short is set)",
    )

    # ---- verify ------------------------------------------------------------------
    verify_parser = subparsers.add_parser(
        "verify",
        help="Run each program through the dyce.anydyce interpreter and compare its result to the stored AnyDice output. "
        "Buckets each row as match, mismatch, parse-fail, interp-error, interp-timeout, or one of the AnyDice-side outcomes "
        "(error, 503 infrastructure failure, empty, resource exhaustion, unrun). "
        "With --isolate, two more buckets surface: interp-oom (worker hit RLIMIT_AS) and interp-killed (worker died unexpectedly). "
        "Comparison normalizes both sides by dividing counts by their gcd. "
        "Programs annotated as known-AnyDice-bug (see `annotate`) re-bucket from mismatch:values to divergence:anydice-bug. "
        "Pass --builtins-report to skip verification and instead print a frequency table of non-user-defined call shapes across the corpus.",
    )
    verify_parser.add_argument(
        "ids",
        metavar="HEX_ID",
        nargs="*",
        help="hex program ID(s) to verify (mutually exclusive with --all)",
    )
    verify_parser.add_argument(
        "--all",
        dest="all_rows",
        action="store_true",
        help="verify every row in the database",
    )
    verify_parser.add_argument(
        "--summary-only",
        action="store_true",
        help="print bucket counts and exit; suppress per-row samples",
    )
    verify_parser.add_argument(
        "--show-max",
        metavar="N",
        type=int,
        default=5,
        help="maximum samples to print per non-match bucket (default: 5; 0 or negative for all)",
    )
    verify_parser.add_argument(
        "--timeout",
        metavar="SECONDS",
        type=float,
        default=5.0,
        help="per-program interpreter wall-clock budget in seconds (default: 5.0)",
    )
    verify_parser.add_argument(
        "--builtins-report",
        action="store_true",
        help="print frequency of non-user-defined call shapes instead of verifying",
    )
    verify_parser.add_argument(
        "--isolated-workers",
        metavar="N",
        type=int,
        default=None,
        help="forkserver-backed worker pool size. 0 means in-process (the "
        "default unless --all is passed). When --all is passed and this flag "
        "is omitted, defaults to os.cpu_count(). Pass --isolated-workers 0 to "
        "force in-process even with --all. Adds two buckets when N>0: "
        "interp-oom (worker hit RLIMIT_AS, MemoryError caught) and "
        "interp-killed (worker died from kernel kill or fault).",
    )
    verify_parser.add_argument(
        "--rlimit-mb",
        metavar="MB",
        type=int,
        default=4096,
        help="memory cap (RLIMIT_AS) applied to both the parent process and "
        "any isolated workers. Always applied (not isolation-specific) so the "
        "default protects in-process runs from runaway allocations. "
        "Default: 4096; pass 0 to disable.",
    )
    verify_parser.add_argument(
        "--maxtasksperchild",
        metavar="N",
        type=int,
        default=100,
        help="recycle each isolated worker after N tasks to bound slow memory "
        "creep (default: 100; no effect when --isolated-workers 0)",
    )

    # ---- annotate ----------------------------------------------------------------
    annotate_parser = subparsers.add_parser(
        "annotate",
        help="Manage per-program annotations (e.g. mark programs as known AnyDice-side bugs so verify can re-bucket them as divergence:anydice-bug instead of mismatch:values).",
    )
    annotate_subparsers = annotate_parser.add_subparsers(
        dest="annotate_command", required=True
    )

    annotate_add_parser = annotate_subparsers.add_parser(
        "add",
        help="Add or update an annotation on a program.",
    )
    annotate_add_parser.add_argument(
        "hex_id", metavar="HEX_ID", help="hex program ID to annotate"
    )
    annotate_add_parser.add_argument(
        "--kind",
        default="anydice-bug",
        choices=sorted(_ANNOTATION_KINDS),
        help="annotation kind (default: anydice-bug)",
    )
    annotate_add_parser.add_argument(
        "--note",
        default=None,
        help="free-text rationale; pass `-` to read from stdin",
    )

    annotate_list_parser = annotate_subparsers.add_parser(
        "list",
        help="List existing annotations.",
    )
    annotate_list_parser.add_argument(
        "ids",
        metavar="HEX_ID",
        nargs="*",
        help="hex program ID(s) to filter by (default: all)",
    )
    annotate_list_parser.add_argument(
        "--kind",
        default=None,
        choices=sorted(_ANNOTATION_KINDS),
        help="filter by annotation kind (default: all kinds)",
    )

    annotate_remove_parser = annotate_subparsers.add_parser(
        "remove",
        help="Remove an annotation.",
    )
    annotate_remove_parser.add_argument(
        "hex_id", metavar="HEX_ID", help="hex program ID"
    )
    annotate_remove_parser.add_argument(
        "--kind",
        default="anydice-bug",
        choices=sorted(_ANNOTATION_KINDS),
        help="annotation kind (default: anydice-bug)",
    )

    args = parser.parse_args()

    if args.command == "fetch":
        cmd_fetch(args.urls, args.db, debug=args.debug, allow_remote=args.allow_remote)
    elif args.command == "link":
        if args.fake_id is not None:
            if args.fake_id >= 0:
                parser.error(
                    "--fake-id must be < 0 to avoid colliding with AnyDice-assigned IDs"
                )
            if len(args.programs) != 1:
                parser.error("--fake-id requires exactly one program argument")
        cmd_link(
            args.programs,
            args.db,
            debug=args.debug,
            allow_remote=args.allow_remote,
            fake_auto=args.fake,
            fake_id=args.fake_id,
        )
    elif args.command == "recanon":
        cmd_recanon(args.db, debug=args.debug)
    elif args.command == "compute":
        if args.ids and args.all_missing:
            parser.error("HEX_ID arguments and --all are mutually exclusive")
        cmd_compute(
            args.ids,
            args.db,
            all_missing=args.all_missing,
            force=args.force,
            delay=args.delay,
            debug=args.debug,
            allow_remote=args.allow_remote,
            timeout=args.timeout,
        )
    elif args.command == "show":
        cmd_show(args.programs, args.db)
    elif args.command == "compare":
        cmd_compare(args.ids, args.db, timeout_s=args.timeout)
    elif args.command == "run":
        if args.file is not None and args.source is not None:
            parser.error("--file and SOURCE are mutually exclusive")
        if args.file is None and args.source is None:
            parser.error("provide a SOURCE argument or --file FILE")
        if args.file is not None:
            source = Path(args.file).read_text(encoding="utf-8")
        elif args.source == "-":
            source = sys.stdin.read()
        else:
            source = args.source
        cmd_run(
            source,
            timeout_s=args.timeout,
            short=args.short,
            width=args.width,
        )
    elif args.command == "verify":
        if args.ids and args.all_rows:
            parser.error("HEX_ID arguments and --all are mutually exclusive")
        # Resolve isolated-workers default: explicit value wins; otherwise
        # auto-default to os.cpu_count() with --all, 0 without.
        if args.isolated_workers is None:
            isolated_workers = (os.cpu_count() or 1) if args.all_rows else 0
        else:
            isolated_workers = args.isolated_workers
        cmd_verify(
            args.ids,
            args.db,
            all_rows=args.all_rows,
            summary_only=args.summary_only,
            show_max=args.show_max,
            builtins_report=args.builtins_report,
            timeout_s=args.timeout,
            debug=args.debug,
            isolated_workers=isolated_workers,
            rlimit_mb=args.rlimit_mb,
            maxtasksperchild=args.maxtasksperchild,
        )
    elif args.command == "annotate":
        if args.annotate_command == "add":
            note = args.note
            if note == "-":
                note = sys.stdin.read()
            cmd_annotate_add(args.hex_id, args.kind, note, args.db)
        elif args.annotate_command == "list":
            cmd_annotate_list(args.ids, args.kind, args.db)
        elif args.annotate_command == "remove":
            cmd_annotate_remove(args.hex_id, args.kind, args.db)


if __name__ == "__main__":
    main()
