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

import base64
import csv
import io
import re
from collections.abc import Iterable, Sequence
from itertools import chain

from dyce import H

__all__ = ("csv_base64",)


def csv_base64(hs: Sequence[tuple[str, H, H | None]]) -> str:
    unique_outcomes = sorted(set(chain.from_iterable(h.outcomes() for _, h, _ in hs)))
    labels = [label for label, _, _ in hs]
    raw_buffer = io.BytesIO()
    csv_buffer = io.TextIOWrapper(
        raw_buffer, encoding="utf-8", newline="", write_through=True
    )
    csv_writer = csv.DictWriter(csv_buffer, fieldnames=["Outcome", *labels])
    csv_writer.writeheader()

    for outcome in unique_outcomes:
        row = {"Outcome": outcome}
        row.update({label: h[outcome] / h.total for label, h, _ in hs if outcome in h})
        csv_writer.writerow(row)

    return base64.standard_b64encode(raw_buffer.getvalue()).decode()


def csv_filename(labels: Iterable[str]) -> str:
    labels_sanitized = [re.sub(r'["\*\/\:\<\>\?\|\\]', "_", label) for label in labels]

    # Inspiration: <https://medium.com/@charles2588/how-to-upload-download-files-to-from-notebook-in-my-local-machine-6a4e65a15767>
    csv_name = "-".join(labels_sanitized)
    csv_name = csv_name if len(csv_name) <= 32 else (csv_name[:29] + "...")

    return f"{csv_name}.csv"
