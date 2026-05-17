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
[![`dyce`-powered!](https://raw.githubusercontent.com/posita/dyce/latest/docs/dyce-powered.svg)](https://posita.github.io/dyce/)
[![Bear-ified™](https://raw.githubusercontent.com/beartype/beartype-assets/main/badge/bear-ified.svg)](https://beartype.rtfd.io/)

# `anydyce` – Interactivity tools for [`dyce`](https://posita.github.io/dyce/)

**💥 *Now 100% [Bear-ified™](https://beartype.rtfd.io/)!* 👌🏾🐻**
([Details](#requirements) below.)

`anydyce` exposes interactive interfaces to [`dyce`](https://posita.github.io/dyce/) (the dice mechanic modeling library) in the spirit of [AnyDice](https://anydice.com/).

If you find it lacking in any way, please don’t hesitate to [bring it to my attention](https://posita.github.io/anydyce/latest/contrib/).

## Interactive quick start

`anydyce` is available [as a PyPI package](https://pypi.python.org/pypi/anydyce/) and [as source](https://github.com/posita/anydyce).


Probably the _easiest_ way to start tinkering with `anydyce` is with [JupyterLite](https://jupyterlite.readthedocs.io/):
[![Try dyce](https://jupyterlite.readthedocs.io/en/latest/_static/badge.svg)](https://posita.github.io/anydyce/latest/jupyter/lab/?path=anydyce_intro.ipynb)

[Binder](https://mybinder.org/) is another great resource that you can use to share notebooks from your Git repositories (including [Gists](https://gist.github.com/)):
[![Try dyce](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/posita/anydyce/HEAD?labpath=docs%2Fnotebooks%2Fanydyce_intro.ipynb)

You can even run your own.
The [`quickstart-local.sh` script](https://github.com/posita/anydyce/blob/main/quickstart-local.sh) will create a local [virtual environment](https://docs.python.org/3/library/venv.html) to bootstrap a local Jupyter server with `anydyce` installed.
Once loaded open a web browser to the [introduction notebook](http://127.0.0.1:8000/jupyter/lab/?path=anydyce_intro.ipynb).

```sh
% git clone https://github.com/posita/anydyce.git anydyce && ./anydyce/quickstart-local.sh
...
INFO    -  Documentation built in 4.84 seconds
INFO    -  [20:39:05] Serving on http://127.0.0.1:8000/
```

!!! danger "JupyterLite and Binder may not save your work!"

    JupyterLite attempts to make use of your browser’s local storage for saving notebook changes.
    Browser environments vary, including how long local storage is persisted.
    Further, Binder loses all state once its instances shut down after a period of inactivity.
    Be careful to download any notebooks you wish to keep.

When creating your own notebooks, including and running the following will bootstrap `anydyce` if it is not already installed:

```python
# Install additional requirements if necessary
import warnings
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    try:
        import anydyce
    except (ImportError, ModuleNotFoundError):
        requirements = ["anydyce"]
        try:
            # For JupyterLite
            import piplite ; await piplite.install(requirements)
        except ImportError:
            # For Jupyter
            import pip ; pip.main(["install"] + requirements)
    import anydyce
```

### Requirements

`anydyce` requires a relatively modern version of Python:

- [CPython](https://www.python.org/) (3.11+)
- [PyPy](http://pypy.org/) (CPython 3.11+ compatible)

It has the following runtime dependencies:

- [`dyce`](https://pypi.org/project/dyce/) for dice mechanic modeling [![`dyce`-powered!](https://raw.githubusercontent.com/posita/dyce/latest/docs/dyce-powered.svg)](https://posita.github.io/dyce/)
- [Matplotlib](https://matplotlib.org/) for visualizing [histograms and pools](https://posita.github.io/dyce/latest/countin/)
- [`Jupyter Widgets`](https://ipywidgets.readthedocs.io/) for interactivity in Jupyter

## Design philosophy

`anydyce` (currently) offers:

- An opinionated, [high-level interface](https://posita.github.io/anydyce/latest/anydyce/#anydyce.viz.jupyter_visualize) for presenting interactive Matplotlib plots in Jupyter notebooks; and
- A (mostly[^1]) compatible pure-Python AnyDice language interpreter

[^1]:

    It is not bug-compatible, instead including fixes for several longstanding implementation errors in AnyDice itself. Further, it does not support AnyDice’s `legacy "..."` syntax.

Support for additional visualization tools may be added in the future.
If you find the existing set too restrictive, or have any requests or ideas for improvements, [let me know](https://posita.github.io/anydyce/latest/contrib/#starting-discussions-and-filing-issues)![^2]

[^2]:

    At some point this devolves into an exercise in chasing a diversity of very specific preferences.
    If you have a very specific need, [`dyce`](https://posita.github.io/dyce/) is fairly low level and should be able to integrate directly with whatever visualization context or package you prefer.
    That being said, I am always on the lookout for more intuitive or accessible visualizations and will eagerly [explore ideas with you](https://posita.github.io/anydyce/latest/contrib/#starting-discussions-and-filing-issues).

## A taste

[`anydyce.viz`](https://posita.github.io/anydyce/latest/anydyce.viz/) provides some rudimentary conveniences such as “burst” charts (`anydyce`’s take on donut charts).

The following compares two mechanics with similar distributions via `dyce`’s take on a bar chart (`dyce.viz.plot_bar`), a line chart (`dyce.viz.plot_line`), and a “burst” chart (`dyce.viz.plot_burst` which is `dyce`’s take on a donut chart).

```python
--8<-- "docs/assets/plot_anydyce_intro.py:core"
```

<!-- Should match any title of the corresponding plot title -->
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="/assets/plot_anydyce_intro_dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="/assets/plot_anydyce_intro_light.svg">
  <img alt="Plot: 2d10 vs. d8+d12, bar, line, and burst charts" src="/assets/plot_anydyce_intro_light.svg">
</picture>

## Customers [![`dyce`-powered!](https://raw.githubusercontent.com/posita/dyce/latest/docs/dyce-powered.svg)](https://posita.github.io/dyce/)

- This could be _you_! 👋

Do you have a project that uses `dyce`?
[Let me know](https://posita.github.io/anydyce/latest/contrib/#starting-discussions-and-filing-issues), and I’ll promote it here!

And don’t forget to do your part in perpetuating gratuitous badge-ification!

```markdown
<!-- Markdown -->
As of version 1.1, HighRollin is
[![dyce-powered](https://raw.githubusercontent.com/posita/dyce/latest/docs/dyce-powered.svg)][dyce-powered]!
[dyce-powered]: https://posita.github.io/dyce/ "dyce-powered!"
```

```rst
..
    reStructuredText - see https://docutils.sourceforge.io/docs/ref/rst/directives.html#image

As of version 1.1, HighRollin is |dyce-powered|!

.. |dyce-powered| image:: https://raw.githubusercontent.com/posita/dyce/latest/docs/dyce-powered.svg
   :align: top
   :target: https://posita.github.io/dyce/
   :alt: dyce-powered
```

```html
<!-- HTML -->
As of version 1.1, HighRollin is <a href="https://posita.github.io/dyce/"><img
  src="https://raw.githubusercontent.com/posita/dyce/latest/docs/dyce-powered.svg"
  alt="dyce-powered"
  style="vertical-align: middle;"></a>!
```

## License

`anydyce` is licensed under the [MIT License](https://opensource.org/licenses/MIT).
See the included [`LICENSE`](https://posita.github.io/anydyce/latest/license/) file for details.
Source code is [available on GitHub](https://github.com/posita/anydyce).
