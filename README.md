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

*Copyright and other protections apply.
Please see the accompanying ``LICENSE`` file for rights and restrictions governing use of this software.
All rights not expressly waived or licensed are reserved.
If that file is missing or appears to be modified from its original, then please contact the author before viewing or using this software in any capacity.*

[![Tests](https://github.com/posita/anydyce/actions/workflows/unit-tests.yaml/badge.svg)](https://github.com/posita/anydyce/actions/workflows/unit-tests.yaml)
[![Version](https://img.shields.io/pypi/v/anydyce/0.1.1.svg)](https://pypi.org/project/anydyce/0.1.1/)
[![Development Stage](https://img.shields.io/pypi/status/anydyce/0.1.1.svg)](https://pypi.org/project/anydyce/0.1.1/)
[![License](https://img.shields.io/pypi/l/anydyce/0.1.1.svg)](http://opensource.org/licenses/MIT)
[![Supported Python Versions](https://img.shields.io/pypi/pyversions/anydyce/0.1.1.svg)](https://pypi.org/project/anydyce/0.1.1/)
[![Supported Python Implementations](https://img.shields.io/pypi/implementation/anydyce/0.1.1.svg)](https://pypi.org/project/anydyce/0.1.1/)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)
[![``dyce``-powered!](https://raw.githubusercontent.com/posita/dyce/latest/docs/dyce-powered.svg)](https://posita.github.io/dyce/)
[![``numerary``-encumbered](https://raw.githubusercontent.com/posita/numerary/latest/docs/numerary-encumbered.svg)](https://posita.github.io/numerary/)
[![Bear-ified™](https://raw.githubusercontent.com/beartype/beartype-assets/main/badge/bear-ified.svg)](https://beartype.rtfd.io/)

# ``anydyce`` – visualization tools for [``dyce``](https://posita.github.io/dyce/)

``anydyce`` exposes an interactive interface to [``dyce``](https://posita.github.io/dyce/) (the dice mechanic modeling library) in [Jupyter](https://jupyter.org/) similar to [AnyDice](https://anydice.com/).

``anydyce`` is licensed under the [MIT License](https://opensource.org/licenses/MIT).
See the accompanying ``LICENSE`` file for details.
Non-experimental features should be considered stable.
See the [release notes](https://posita.github.io/anydyce/0.1/notes/) for a summary of version-to-version changes.
Source code is [available on GitHub](https://github.com/posita/anydyce).

If you find it lacking in any way, please don’t hesitate to [bring it to my attention](https://posita.github.io/anydyce/0.1/contrib/).

## Design philosophy

``anydyce`` (currently) targets Matplotlib (both alone and within Jupyter).
Support for additional visualization tools may be added in the future.
It is intended as a convenience layer for those who benefit from simple interfaces with reasonable defaults and limited configurability.
If you find they are too restrictive, or have any requests or ideas for improvements, [let me know](https://posita.github.io/anydyce/0.1/contrib/#starting-discussions-and-filing-issues)![^1]

[^1]:

    At some point this devolves into an exercise in chasing a diversity of very specific preferences.
    If you have a very specific need, [``dyce``](https://posita.github.io/dyce/) is fairly low level and should be able to integrate directly with whatever visualization context or package you prefer.
    That being said, I am always on the lookout for more intuitive or accessible visualizations and will eagerly [explore ideas with you](https://posita.github.io/anydyce/0.1/contrib/#starting-discussions-and-filing-issues).

If used within Jupyter, ``anydyce`` provides [a high-level, interactive interface](https://posita.github.io/anydyce/0.1/anydyce/#anydyce.viz.jupyter_visualize) with functionality that echos AnyDice.

### Comparison to AnyDice

| Feature | ``anydyce`` | AnyDice |
|---|:---:|:---:|
| Shareable session URLs | ⚠️ Via third party[^2] | ✅ Yes |
| Modeling language | 🐍 [Python](https://www.python.org/) | Proprietary |
| Computation time limit | ✅ No limit | ❌ 5 seconds |
| Configurable plots<br>(including “burst” graphs) | ✅ Yes | ❌ No |
| Install and use third party libraries | ✅ Yes | ❌ No |
| Open source<br>(install, run, and modify locally) | ✅ Yes | ❌ No |
| Advanced language features<br>(memoization, nested functions, etc.) | ✅ Yes | ❌ No |

[^2]:

    Relies on external depedencies.
    Notebooks that are published via GitHub Gists or in Git repositories can be auto-loaded via Binder.
    (See [Interactive quick start](#interactive-quick-start).)
    However, edits are not persisted.
    Notebooks can also be downloaded and shared as ``.ipynb`` files.

## Installation and use

``anydyce`` is available [as a PyPI package](https://pypi.python.org/pypi/anydyce/) and [as source](https://github.com/posita/anydyce).

### Interactive quick start

Probably the _easiest_ way to start tinkering with ``anydyce`` is via Binder.
[![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gist/posita/f65800898aa0ad08b8c927246bf32c0f/30993b3ee6aa7176765a2337c2c02e932fd03a68?labpath=anydyce_intro.ipynb)

!!! danger "Binder will not save your work!"

    After a period of inactivity, Binder is configured to destroy all instances and delete any associated data.
    Be careful to download any notebooks you wish to keep before that happens.

``anydyce`` also makes it relatively easy to spool up your own local Jupyter instance.

``` sh
% git clone https://github.com/posita/anydyce.git
% cd anydyce
% ./quickstart-local.sh
…
```

The [``quickstart-local.sh`` script](https://github.com/posita/anydyce/blob/v0.1.1/quickstart-local.sh) will create a local [virtual environment](https://docs.python.org/3/library/venv.html) to bootstrap a local Jupyter server with ``anydice`` installed and open a web browser to the [introduction notebook](https://gist.github.com/posita/f65800898aa0ad08b8c927246bf32c0f/30993b3ee6aa7176765a2337c2c02e932fd03a68#file-anydyce_intro-ipynb).

You can also [create your own binders](https://mybinder.org/) from Gists or other sources.
Running the following in your notebook will bootstrap[^3] ``anydyce`` if it is not already installed:

``` python
import warnings
with warnings.catch_warnings():
  warnings.simplefilter("ignore")
  try:
    import anydyce
  except (ImportError, ModuleNotFoundError):
    import sys
    !{sys.executable} -m pip install --upgrade pip
    !{sys.executable} -m pip install 'https://gist.githubusercontent.com/posita/f65800898aa0ad08b8c927246bf32c0f/raw/30993b3ee6aa7176765a2337c2c02e932fd03a68/requirements.txt'
    import anydyce
```

### Additional interfaces

[``anydyce.viz``](https://posita.github.io/anydyce/0.1/anydyce.viz/) also provides some rudimentary conveniences if it detects that ``#!python matplotlib`` is installed.
One such convenience enables creation of “burst” charts (``anydyce``’s take on donut charts).

``` python
>>> import matplotlib.pyplot  # doctest: +SKIP
>>> from dyce import H
>>> from anydyce.viz import plot_burst
>>> ax = matplotlib.pyplot.axes() # doctest: +SKIP
>>> plot_burst(ax, 2@H(6))  # doctest: +SKIP
>>> matplotlib.pyplot.show()  # doctest: +SKIP

```

<!-- Should match any title of the corresponding plot title -->
<picture>
  <source srcset="https://raw.githubusercontent.com/posita/anydyce/v0.1.1/docs/assets/plot_burst_1_dark.png" media="(prefers-color-scheme: dark)">
  <img alt="Plot: Basic plot_burst example" src="https://raw.githubusercontent.com/posita/anydyce/v0.1.1/docs/assets/plot_burst_1_light.png#gh-light-mode-only"><span style="display: none"><img alt="Plot: Taking the lowest or highest die of 2d6" src="https://raw.githubusercontent.com/posita/anydyce/v0.1.1/docs/assets/plot_burst_1_dark.png#gh-dark-mode-only"></span>
</picture>

<details>
<summary>Source: <a href="https://raw.githubusercontent.com/posita/anydyce/v0.1.1/docs/assets/plot_burst_1.py"><code>plot_burst_1.py</code></a></summary>

``` python
--8<-- "docs/assets/plot_burst_1.py"
```
</details>

The outer ring can also be used to compare two histograms directly.
Ever been curious how your four shiny new fudge dice stack up against your trusty ol’ double six-siders?
Well wonder no more!
``anydyce`` abides.

``` python
>>> df_4 = 4@H((-1, 0, 1))
>>> d6_2 = 2@H(6)
>>> ax = matplotlib.pyplot.axes() # doctest: +SKIP
>>> plot_burst(
...   ax,
...   df_4, d6_2,
...   inner_color="turbo",
...   alpha=1.0,
... )  # doctest: +SKIP
>>> matplotlib.pyplot.show()  # doctest: +SKIP

```

<!-- Should match any title of the corresponding plot title -->
<picture>
  <source srcset="https://raw.githubusercontent.com/posita/anydyce/v0.1.1/docs/assets/plot_burst_2_dark.png" media="(prefers-color-scheme: dark)">
  <img alt="Plot: 2d6 vs. 4dF plot_burst example" src="https://raw.githubusercontent.com/posita/anydyce/v0.1.1/docs/assets/plot_burst_2_light.png#gh-light-mode-only"><span style="display: none"><img alt="Plot: Taking the lowest or highest die of 2d6" src="https://raw.githubusercontent.com/posita/anydyce/v0.1.1/docs/assets/plot_burst_2_dark.png#gh-dark-mode-only"></span>
</picture>

<details>
<summary>Source: <a href="https://raw.githubusercontent.com/posita/anydyce/v0.1.1/docs/assets/plot_burst_2.py"><code>plot_burst_2.py</code></a></summary>

``` python
--8<-- "docs/assets/plot_burst_2.py"
```
</details>

Labels can even be overridden for interesting, at-a-glance displays.
Overrides apply counter-clockwise, starting from the 12 o’clock position.

``` python
>>> def d20formatter(outcome, probability, h) -> str:
...   vals = {
...     -2: "crit. fail.",
...     -1: "fail.",
...     1: "succ.",
...     2: "crit. succ.",
...   }
...   return vals[outcome]

>>> d20 = H(20)
>>> ax = matplotlib.pyplot.axes() # doctest: +SKIP
>>> plot_burst(ax, h_inner=d20, h_outer=H({
...   -2: d20.le(1)[1],
...   -1: d20.within(2, 14)[0],
...   1: d20.within(15, 19)[0],
...   2: d20.ge(20)[1],
... }), inner_color="RdYlBu_r", outer_formatter=d20formatter)  # doctest: +SKIP
>>> matplotlib.pyplot.show()  # doctest: +SKIP

```

<!-- Should match any title of the corresponding plot title -->
<picture>
  <source srcset="https://raw.githubusercontent.com/posita/anydyce/v0.1.1/docs/assets/plot_burst_3_dark.png" media="(prefers-color-scheme: dark)">
  <img alt="Plot: Advanced plot_burst example" src="https://raw.githubusercontent.com/posita/anydyce/v0.1.1/docs/assets/plot_burst_3_light.png#gh-light-mode-only"><span style="display: none"><img alt="Plot: Taking the lowest or highest die of 2d6" src="https://raw.githubusercontent.com/posita/anydyce/v0.1.1/docs/assets/plot_burst_3_dark.png#gh-dark-mode-only"></span>
</picture>

<details>
<summary>Source: <a href="https://raw.githubusercontent.com/posita/anydyce/v0.1.1/docs/assets/plot_burst_3.py"><code>plot_burst_3.py</code></a></summary>

``` python
--8<-- "docs/assets/plot_burst_3.py"
```
</details>

### Requirements

``anydyce`` requires a relatively modern version of Python:

* [CPython](https://www.python.org/) (3.7+)
* [PyPy](http://pypy.org/) (CPython 3.7+ compatible)

It has the following runtime dependencies:

* [``dyce``](https://pypi.org/project/dyce/) for dice mechanic modeling [![``dyce``-powered!](https://raw.githubusercontent.com/posita/dyce/latest/docs/dyce-powered.svg)](https://posita.github.io/dyce/)
* [``numerary``](https://pypi.org/project/numerary/) for ~~proper~~ *best-effort hacking around deficiencies in* static and runtime numeric type-checking [![``numerary``-encumbered](https://raw.githubusercontent.com/posita/numerary/latest/docs/numerary-encumbered.svg)](https://posita.github.io/numerary/)

``anydyce`` will opportunistically use the following, if available at runtime:

* [``beartype``](https://pypi.org/project/beartype/) for yummy runtime type-checking goodness (0.8+) [![Bear-ified™](https://raw.githubusercontent.com/beartype/beartype-assets/main/badge/bear-ified.svg)](https://beartype.rtfd.io/)
* [``ipywidgets``](https://ipywidgets.readthedocs.io/) for interactivity in Jupyter
* [``matplotlib``](https://matplotlib.org/) for visualizing [histograms and pools](https://posita.github.io/dyce/latest/countin/)

``anydyce`` (and ``dyce``) leverage ``numerary`` for its opportunistic use of ``beartype``. If you use ``beartype`` for type checking your code, but don’t want ``anydyce``, ``dyce``, or ``numerary`` to use it internally, disable it with [``numerary``’s ``NUMERARY_BEARTYPE`` environment variable](https://posita.github.io/numerary/latest/#requirements).

See the [hacking quick-start](https://posita.github.io/anydyce/0.1/contrib/#hacking-quick-start) for additional development and testing dependencies.

## License

``anydyce`` is licensed under the [MIT License](https://opensource.org/licenses/MIT).
See the included [``LICENSE``](https://posita.github.io/anydyce/0.1/license/) file for details.
Source code is [available on GitHub](https://github.com/posita/anydyce).

## Customers [![``dyce``-powered!](https://raw.githubusercontent.com/posita/dyce/latest/docs/dyce-powered.svg)](https://posita.github.io/dyce/)

* This could be _you_! 👋

Do you have a project that uses ``dyce``?
[Let me know](https://posita.github.io/anydyce/0.1/contrib/#starting-discussions-and-filing-issues), and I’ll promote it here!

And don’t forget to do your part in perpetuating gratuitous badge-ification!

``` markdown
<!-- Markdown -->
As of version 1.1, HighRollin is
[![dyce-powered](https://raw.githubusercontent.com/posita/dyce/latest/docs/dyce-powered.svg)][dyce-powered]!
[dyce-powered]: https://posita.github.io/dyce/ "dyce-powered!"
```

``` rst
..
    reStructuredText - see https://docutils.sourceforge.io/docs/ref/rst/directives.html#image

As of version 1.1, HighRollin is |dyce-powered|!

.. |dyce-powered| image:: https://raw.githubusercontent.com/posita/dyce/latest/docs/dyce-powered.svg
   :align: top
   :target: https://posita.github.io/dyce/
   :alt: dyce-powered
```

``` html
<!-- HTML -->
As of version 1.1, HighRollin is <a href="https://posita.github.io/dyce/"><img
  src="https://raw.githubusercontent.com/posita/dyce/latest/docs/dyce-powered.svg"
  alt="dyce-powered"
  style="vertical-align: middle;"></a>!
```
