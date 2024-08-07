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

[![Tests](https://github.com/posita/anydyce/actions/workflows/on-push.yaml/badge.svg)](https://github.com/posita/anydyce/actions/workflows/on-push.yaml)
[![Version](https://img.shields.io/pypi/v/anydyce/0.4.6.svg)](https://pypi.org/project/anydyce/0.4.6/)
[![Development Stage](https://img.shields.io/pypi/status/anydyce/0.4.6.svg)](https://pypi.org/project/anydyce/0.4.6/)
[![License](https://img.shields.io/pypi/l/anydyce/0.4.6.svg)](http://opensource.org/licenses/MIT)
[![Supported Python Versions](https://img.shields.io/pypi/pyversions/anydyce/0.4.6.svg)](https://pypi.org/project/anydyce/0.4.6/)
[![Supported Python Implementations](https://img.shields.io/pypi/implementation/anydyce/0.4.6.svg)](https://pypi.org/project/anydyce/0.4.6/)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)
[![``dyce``-powered!](https://raw.githubusercontent.com/posita/dyce/latest/docs/dyce-powered.svg)](https://posita.github.io/dyce/)
[![``numerary``-encumbered](https://raw.githubusercontent.com/posita/numerary/latest/docs/numerary-encumbered.svg)](https://posita.github.io/numerary/)
[![Bear-ified™](https://raw.githubusercontent.com/beartype/beartype-assets/main/badge/bear-ified.svg)](https://beartype.rtfd.io/)

# ``anydyce`` – visualization tools for [``dyce``](https://posita.github.io/dyce/)

``anydyce`` exposes an interactive interface to [``dyce``](https://posita.github.io/dyce/) (the dice mechanic modeling library) in [Jupyter](https://jupyter.org/) similar to [AnyDice](https://anydice.com/).

``anydyce`` is licensed under the [MIT License](https://opensource.org/licenses/MIT).
See the accompanying ``LICENSE`` file for details.
Non-experimental features should be considered stable.
See the [release notes](https://posita.github.io/anydyce/0.4/notes/) for a summary of version-to-version changes.
Source code is [available on GitHub](https://github.com/posita/anydyce).

If you find it lacking in any way, please don’t hesitate to [bring it to my attention](https://posita.github.io/anydyce/0.4/contrib/).

## Design philosophy

``anydyce`` (currently) targets Matplotlib (both alone and within Jupyter).
Support for additional visualization tools may be added in the future.
It is intended as a convenience layer for those who benefit from simple interfaces with reasonable defaults and limited configurability.
If you find they are too restrictive, or have any requests or ideas for improvements, [let me know](https://posita.github.io/anydyce/0.4/contrib/#starting-discussions-and-filing-issues)![^1]

[^1]:

    At some point this devolves into an exercise in chasing a diversity of very specific preferences.
    If you have a very specific need, [``dyce``](https://posita.github.io/dyce/) is fairly low level and should be able to integrate directly with whatever visualization context or package you prefer.
    That being said, I am always on the lookout for more intuitive or accessible visualizations and will eagerly [explore ideas with you](https://posita.github.io/anydyce/0.4/contrib/#starting-discussions-and-filing-issues).

If used within Jupyter, ``anydyce`` provides [a high-level, interactive interface](https://posita.github.io/anydyce/0.4/anydyce/#anydyce.viz.jupyter_visualize) with functionality that echos AnyDice.

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

    Relies on external depedencies such as [Binder](https://mybinder.org/) or [JupyterLite](https://jupyterlite.readthedocs.io/en/latest/).
    (See [Interactive quick start](#interactive-quick-start).)
    However, edits are not persisted.
    Notebooks can also be downloaded and shared as ``.ipynb`` files.

### Interactive quick start

Probably the _easiest_ way to start tinkering with ``anydyce`` is with [JupyterLite](https://jupyterlite.readthedocs.io/):
[![Try dyce](https://jupyterlite.readthedocs.io/en/latest/_static/badge.svg)](https://posita.github.io/anydyce/0.4/jupyter/lab/?path=anydyce_intro.ipynb)

The [``quickstart-local.sh`` script](https://github.com/posita/anydyce/blob/v0.4.6/quickstart-local.sh) will create a local [virtual environment](https://docs.python.org/3/library/venv.html) to bootstrap a local Jupyter server with ``anydyce`` installed and open a web browser to the [introduction notebook](https://github.com/posita/anydyce/blob/v0.4.6/docs/notebooks/anydyce_intro-ipynb).

[Binder](https://mybinder.org/) is another great resource that you can use to share notebooks from your Git repositories (including [Gists](https://gist.github.com/)):
[![Try dyce](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/posita/anydyce/HEAD?labpath=docs%2Fnotebooks%2Fanydyce_intro.ipynb)

!!! danger "JupyterLite and Binder may not save your work!"

    JupyterLite attempts to make use of your browser’s local storage for saving notebook changes.
    Browser environments vary, including how long local storage is persisted.
    Further, Binder loses all state once its instances shut down after a period of inactivity.
    Be careful to download any notebooks you wish to keep.

When creating your own notebooks, including and running the following will bootstrap ``anydyce`` if it is not already installed:

``` python
# Install additional requirements if necessary
import warnings
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    try:
        import anydyce
    except (ImportError, ModuleNotFoundError):
        requirements = ["anydyce~=0.2"]
        try:
            import piplite ; await piplite.install(requirements)
        except ImportError:
            import pip ; pip.main(["install"] + requirements)
    import anydyce
```

## Installation and use

``anydyce`` is available [as a PyPI package](https://pypi.python.org/pypi/anydyce/) and [as source](https://github.com/posita/anydyce).

[``anydyce.viz``](https://posita.github.io/anydyce/0.4/anydyce.viz/) provides some rudimentary conveniences such as “burst” charts (``anydyce``’s take on donut charts).

``` python
>>> import matplotlib.pyplot
>>> from dyce import H
>>> from anydyce.viz import plot_burst
>>> ax = matplotlib.pyplot.axes()
>>> plot_burst(ax, 2@H(6))
>>> matplotlib.pyplot.show()  # doctest: +SKIP

```

<!-- Should match any title of the corresponding plot title -->
<picture>
  <source srcset="https://raw.githubusercontent.com/posita/anydyce/v0.4.6/docs/assets/plot_burst_1_dark.png" media="(prefers-color-scheme: dark)">
  <img alt="Plot: Basic plot_burst example" src="https://raw.githubusercontent.com/posita/anydyce/v0.4.6/docs/assets/plot_burst_1_light.png#gh-light-mode-only"><span style="display: none"><img alt="Plot: Taking the lowest or highest die of 2d6" src="https://raw.githubusercontent.com/posita/anydyce/v0.4.6/docs/assets/plot_burst_1_dark.png#gh-dark-mode-only"></span>
</picture>

<details>
<summary>Source: <a href="https://raw.githubusercontent.com/posita/anydyce/v0.4.6/docs/assets/plot_burst_1.py"><code>plot_burst_1.py</code></a></summary>

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
>>> ax = matplotlib.pyplot.axes()
>>> plot_burst(
...   ax,
...   df_4, d6_2,
...   inner_cmap="turbo",
...   alpha=1.0,
... )
>>> matplotlib.pyplot.show()  # doctest: +SKIP

```

<!-- Should match any title of the corresponding plot title -->
<picture>
  <source srcset="https://raw.githubusercontent.com/posita/anydyce/v0.4.6/docs/assets/plot_burst_2_dark.png" media="(prefers-color-scheme: dark)">
  <img alt="Plot: 2d6 vs. 4dF plot_burst example" src="https://raw.githubusercontent.com/posita/anydyce/v0.4.6/docs/assets/plot_burst_2_light.png#gh-light-mode-only"><span style="display: none"><img alt="Plot: Taking the lowest or highest die of 2d6" src="https://raw.githubusercontent.com/posita/anydyce/v0.4.6/docs/assets/plot_burst_2_dark.png#gh-dark-mode-only"></span>
</picture>

<details>
<summary>Source: <a href="https://raw.githubusercontent.com/posita/anydyce/v0.4.6/docs/assets/plot_burst_2.py"><code>plot_burst_2.py</code></a></summary>

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
>>> ax = matplotlib.pyplot.axes()
>>> plot_burst(ax, h_inner=d20, h_outer=H({
...   -2: d20.le(1)[1],
...   -1: d20.within(2, 14)[0],
...   1: d20.within(15, 19)[0],
...   2: d20.ge(20)[1],
... }), inner_cmap="RdYlBu_r", outer_formatter=d20formatter)
>>> matplotlib.pyplot.show()  # doctest: +SKIP

```

<!-- Should match any title of the corresponding plot title -->
<picture>
  <source srcset="https://raw.githubusercontent.com/posita/anydyce/v0.4.6/docs/assets/plot_burst_3_dark.png" media="(prefers-color-scheme: dark)">
  <img alt="Plot: Advanced plot_burst example" src="https://raw.githubusercontent.com/posita/anydyce/v0.4.6/docs/assets/plot_burst_3_light.png#gh-light-mode-only"><span style="display: none"><img alt="Plot: Taking the lowest or highest die of 2d6" src="https://raw.githubusercontent.com/posita/anydyce/v0.4.6/docs/assets/plot_burst_3_dark.png#gh-dark-mode-only"></span>
</picture>

<details>
<summary>Source: <a href="https://raw.githubusercontent.com/posita/anydyce/v0.4.6/docs/assets/plot_burst_3.py"><code>plot_burst_3.py</code></a></summary>

``` python
--8<-- "docs/assets/plot_burst_3.py"
```
</details>

### Requirements

``anydyce`` requires a relatively modern version of Python:

* [CPython](https://www.python.org/) (3.9+)
* ~~[PyPy](http://pypy.org/) (CPython 3.9+ compatible)~~ *See [beartype/beartype#324](https://github.com/beartype/beartype/issues/324)*

It has the following runtime dependencies:

* [``dyce``](https://pypi.org/project/dyce/) for dice mechanic modeling [![``dyce``-powered!](https://raw.githubusercontent.com/posita/dyce/latest/docs/dyce-powered.svg)](https://posita.github.io/dyce/)
* [``ipywidgets``](https://ipywidgets.readthedocs.io/) for interactivity in Jupyter
* [``matplotlib``](https://matplotlib.org/) for visualizing [histograms and pools](https://posita.github.io/dyce/latest/countin/)

``anydyce`` (and ``dyce``) leverage ``numerary`` for its opportunistic use of ``beartype``. If you use ``beartype`` for type checking your code, but don’t want ``anydyce``, ``dyce``, or ``numerary`` to use it internally, disable it with [``numerary``’s ``NUMERARY_BEARTYPE`` environment variable](https://posita.github.io/numerary/latest/#requirements).

See the [hacking quick-start](https://posita.github.io/anydyce/0.4/contrib/#hacking-quick-start) for additional development and testing dependencies.

## License

``anydyce`` is licensed under the [MIT License](https://opensource.org/licenses/MIT).
See the included [``LICENSE``](https://posita.github.io/anydyce/0.4/license/) file for details.
Source code is [available on GitHub](https://github.com/posita/anydyce).

## Customers [![``dyce``-powered!](https://raw.githubusercontent.com/posita/dyce/latest/docs/dyce-powered.svg)](https://posita.github.io/dyce/)

* This could be _you_! 👋

Do you have a project that uses ``dyce``?
[Let me know](https://posita.github.io/anydyce/0.4/contrib/#starting-discussions-and-filing-issues), and I’ll promote it here!

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
