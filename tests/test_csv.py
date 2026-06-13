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

from dyce import H
from dyce.d import d6, d8, d12, h2d10

from anydyce.csv import csv_base64

__all__ = ()


def test_csv_base64_emtpy() -> None:
    empty_csv_html = csv_base64(())
    assert empty_csv_html == "T3V0Y29tZQ0K"


def test_csv_base64_single_histogram() -> None:
    d6_csv_html = csv_base64([("d6", d6, None)])
    assert (
        d6_csv_html
        == "T3V0Y29tZSxkNg0KMSwwLjE2NjY2NjY2NjY2NjY2NjY2DQoyLDAuMTY2NjY2NjY2NjY2NjY2NjYNCjMsMC4xNjY2NjY2NjY2NjY2NjY2Ng0KNCwwLjE2NjY2NjY2NjY2NjY2NjY2DQo1LDAuMTY2NjY2NjY2NjY2NjY2NjYNCjYsMC4xNjY2NjY2NjY2NjY2NjY2Ng0K"
    )


def test_csv_base64_secondary_histogram_ignored() -> None:
    d8d12_csv_html = csv_base64([("d8d12", d8 + H(12), None)])
    d8d12_vs_2d10_csv_html = csv_base64([("d8d12", d8 + d12, h2d10)])
    assert d8d12_csv_html == d8d12_vs_2d10_csv_html


def test_csv_base64_multiple_histograms() -> None:
    d6_and_d8_csv_html = csv_base64([("d6", d6, None), ("d8", d8, None)])
    assert (
        d6_and_d8_csv_html
        == "T3V0Y29tZSxkNixkOA0KMSwwLjE2NjY2NjY2NjY2NjY2NjY2LDAuMTI1DQoyLDAuMTY2NjY2NjY2NjY2NjY2NjYsMC4xMjUNCjMsMC4xNjY2NjY2NjY2NjY2NjY2NiwwLjEyNQ0KNCwwLjE2NjY2NjY2NjY2NjY2NjY2LDAuMTI1DQo1LDAuMTY2NjY2NjY2NjY2NjY2NjYsMC4xMjUNCjYsMC4xNjY2NjY2NjY2NjY2NjY2NiwwLjEyNQ0KNywsMC4xMjUNCjgsLDAuMTI1DQo="
    )
