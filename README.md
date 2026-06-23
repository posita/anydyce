<!---
  !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
  !!!!!!!!!!!!!!! IMPORTANT: READ THIS BEFORE EDITING! !!!!!!!!!!!!!!!
  !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
  Please keep each sentence on its own unwrapped line.
  It looks like crap in a text editor, but it has no effect on rendering, and it allows much more useful diffs.
  Thank you!

  WARNING: THIS DOCUMENT MUST BE SELF-CONTAINED.
  ALL LINKS MUST BE ABSOLUTE.
  This file is used on GitHub and PyPi (via setup.cfg).
  There is no guarantee that other docs/resources will be available where this content is displayed.
-->

<!-- mkdocs:hide:start -->
*Copyright and other protections apply.
Please see the accompanying `LICENSE` file for rights and restrictions governing use of this software.
All rights not expressly waived or licensed are reserved.
If that file is missing or appears to be modified from its original, then please contact the author before viewing or using this software in any capacity.*
<!-- mkdocs:hide:end -->

[![Tests](https://github.com/posita/anydyce/actions/workflows/tests.yaml/badge.svg)](https://github.com/posita/anydyce/actions/workflows/tests.yaml)
[![Coverage](https://codecov.io/gh/posita/anydyce/branch/main/graph/badge.svg)](https://app.codecov.io/gh/posita/anydyce)
[![Version](https://img.shields.io/pypi/v/anydyce.svg)](https://pypi.org/project/anydyce/)
![Development Stage](https://img.shields.io/pypi/status/anydyce.svg)
[![License](https://img.shields.io/pypi/l/anydyce.svg)](http://opensource.org/licenses/MIT)
![Supported Python Versions](https://img.shields.io/pypi/pyversions/anydyce.svg)
![Supported Python Implementations](https://img.shields.io/pypi/implementation/anydyce.svg)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)
[![`dyce`-powered!](https://posita.github.io/dyce/latest/dyce-powered.svg)](https://posita.github.io/dyce/)
[![Bear-ified™](https://raw.githubusercontent.com/beartype/beartype-assets/main/badge/bear-ified.svg)](https://beartype.rtfd.io/)

# `anydyce` – Application experiments for [`dyce`](https://posita.github.io/dyce/)

`anydyce` is a testing ground for various interactive interfaces to [`dyce`](https://posita.github.io/dyce/) (the dice mechanic modeling library).
Currently, it includes:

1. A [JupyterLite](https://jupyterlite.readthedocs.io/) graphing widget using [Matplotlib](https://matplotlib.org/) and [`Jupyter Widgets`](https://ipywidgets.readthedocs.io/) for visualizing [histograms and pools](https://posita.github.io/dyce/latest/countin/):
    * Try it! 👉 [![Try dyce](https://jupyterlite.readthedocs.io/en/latest/_static/badge.svg)](https://posita.github.io/anydyce/latest/jupyter/lab/?path=anydyce_intro.ipynb)  👈
1. 💥 ***New!*** 💥 A fully functioning, (mostly[^1]) compatible, pure-Python [AnyDice](https://anydice.com/) language interpreter and interactive playground.
   [Quite a bit of detail is provided](anydice.md) on how it was built, how it differs from the original, and all the pitfalls and nuances discovered along the way.
    * Try it! 👉 [![Try the AnyDice-compatible playground](https://posita.github.io/anydyce/latest/anydice-playground.svg)](https://posita.github.io/anydyce/latest/playground/) 👈

!!! danger "JupyterLite may not save your work!"

    JupyterLite attempts to make use of your browser’s local storage for saving notebook changes.
    Browser environments vary, including how long local storage is persisted.
    Further, Binder loses all state once its instances shut down after a period of inactivity.
    Be careful to download any notebooks you wish to keep.

If you find anything lacking in any way, please don’t hesitate to [bring it to my attention](https://posita.github.io/anydyce/latest/contrib/).

[^1]:

    It is not bug-compatible, instead including fixes for several longstanding implementation errors in AnyDice itself. Further, it does not support AnyDice’s `legacy "..."` syntax.

## Running locally

`anydyce` is also available [as a PyPI package](https://pypi.python.org/pypi/anydyce/) and [as source](https://github.com/posita/anydyce).
To try it on your own hardware, use the [`quickstart-local.sh` script](https://github.com/posita/anydyce/blob/main/quickstart-local.sh) to create a local [virtual environment](https://docs.python.org/3/library/venv.html) and bootstrap a local copy.

```sh
% git clone https://github.com/posita/anydyce.git anydyce && ./anydyce/quickstart-local.sh
...
INFO    -  Documentation built in 4.84 seconds
INFO    -  [20:39:05] Serving on http://127.0.0.1:8000/
```

Once loaded, try the following:

* Introduction Jupyter Lite notebook - [http://127.0.0.1:8000/jupyter/lab/?path=anydyce_intro.ipynb](http://127.0.0.1:8000/jupyter/lab/?path=anydyce_intro.ipynb)
* AnyDice-compatible playground - [http://127.0.0.1:8000/playground/](http://127.0.0.1:8000/playground/)

### Requirements

`anydyce` requires a relatively modern version of Python:

- [CPython](https://www.python.org/) (3.11+)
- [PyPy](http://pypy.org/) (CPython 3.11+ compatible)

It has the following runtime dependencies:

- [`dyce`](https://pypi.org/project/dyce/) for dice mechanic modeling [![`dyce`-powered!](https://raw.githubusercontent.com/posita/dyce/latest/docs/dyce-powered.svg)](https://posita.github.io/dyce/)
- [Lark](https://github.com/lark-parser/lark) for the [AnyDice interpreter](anydice.md)
- [Matplotlib](https://matplotlib.org/) (optional) for visualizing [histograms and pools](https://posita.github.io/dyce/latest/countin/)
- [`Jupyter Widgets`](https://ipywidgets.readthedocs.io/) (optional) for interactivity in Jupyter

`anydyce` is proudly 100% [Bear-ified™](https://beartype.rtfd.io/)! 👌🏾🐻

## License

`anydyce` is licensed under the [MIT License](https://opensource.org/licenses/MIT).
See the included [`LICENSE`](https://posita.github.io/anydyce/latest/license/) file for details.
Source code is [available on GitHub](https://github.com/posita/anydyce).
