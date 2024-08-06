<!---
  Copyright and other protections apply. Please see the accompanying LICENSE file for
  rights and restrictions governing use of this software. All rights not expressly
  waived or licensed are reserved. If that file is missing or appears to be modified
  from its original, then please contact the author before viewing or using this
  software in any capacity.

  !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
  !!!!!!!!!!!!!!! IMPORTANT: READ THIS BEFORE EDITING! !!!!!!!!!!!!!!!
  !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
  Please keep each sentence on its own unwrapped line.
  It looks like crap in a text editor, but it has no effect on rendering, and it allows much more useful diffs.
  Thank you!
-->

# ``anydyce`` release notes

## [0.4.6](https://github.com/posita/anydyce/releases/tag/v0.4.6)

* TODO

## [0.4.5](https://github.com/posita/anydyce/releases/tag/v0.4.5)

* Stablized Jupyter Lite installation
* Adjusted typing slightly
* Defaulted to collapsed installation cells
* Acknowledged removal of PyPy support ([beartype/beartype#324](https://github.com/beartype/beartype/issues/324))

## [0.4.4](https://github.com/posita/anydyce/releases/tag/v0.4.4)

* Added ``#!python SettingsDict["burst_columns"]`` and related widget.
* Added ``#!python None`` as an acceptable item value for ``#!python histogram_specs`` parameter to [``HPlotterChooser`` initializer][anydyce.viz.HPlotterChooser], [``HPlotterChooser.update_hs``][anydyce.viz.HPlotterChooser.update_hs], and [``jupyter_visualize``][anydyce.viz.jupyter_visualize].

## [0.4.3](https://github.com/posita/anydyce/releases/tag/v0.4.3)

* Restored [rich display](https://ipython.readthedocs.io/en/stable/config/integrating.html#integrating-rich-display) hook methods accidentally removed from ``#!python anydyce.viz.Image`` in [v0.4.2](#042).

## [0.4.2](https://github.com/posita/anydyce/releases/tag/v0.4.2)

!!! bug

    ***Do not use!***
    This release inadvertently removed [rich display](https://ipython.readthedocs.io/en/stable/config/integrating.html#integrating-rich-display) hook methods from ``#!python anydyce.viz.Image``.
    That broke the ability to display interactive plots.
    (Fixed in [v0.4.3](#043).)

* Allows *true* cutoff disablement (not merely a small default).

## [0.4.1](https://github.com/posita/anydyce/releases/tag/v0.4.1)

* Adds transparency as well as PNG and SVG output and download selections.
* Fixes display inconsistencies between Jupyter Lab and Jupyter Lite.

## [0.4.0](https://github.com/posita/anydyce/releases/tag/v0.4.0)

* Adds [``HPlotterChooser``][anydyce.viz.HPlotterChooser] implementation and substantially refactors [``jupyter_visualize``][anydyce.viz.jupyter_visualize] in terms thereof.

## [0.3.2](https://github.com/posita/anydyce/releases/tag/v0.3.2)

* Works around [jupyterlite/jupyterlite#838](https://github.com/jupyterlite/jupyterlite/issues/838) to fix docs.

## [0.3.1](https://github.com/posita/anydyce/releases/tag/v0.3.1)

* Fixes badges in docs.
* Migrates to ``jupyterlite==0.1.0b13``.
* Un-breaks 0.3.0 in JupyterLite.

## [0.3.0](https://github.com/posita/anydyce/releases/tag/v0.3.0)

* Migrates to ``ipywidgets~=8.0``.

## [0.2.0](https://github.com/posita/anydyce/releases/tag/v0.2.0)

* Completes update to ``dyce~=0.6``.
* Migrates from [``setuptools_scm``](https://pypi.org/project/setuptools-scm/) to [``versioningit``](https://pypi.org/project/versioningit/) for more flexible version number formatting.
* Allows deployments to PyPI from CI based on tags.

## [0.1.6](https://github.com/posita/anydyce/releases/tag/v0.1.6)

* ``ipywidgets`` and ``matplotlib`` are now required dependencies.
* Minor corrections to required Python version.

## [0.1.4](https://github.com/posita/anydyce/releases/tag/v0.1.4)

* Prepares for breaking changes in future release of ``dyce~=0.6``.
* Adds experimental [``values_xy_for_graph_type``][anydyce.viz.values_xy_for_graph_type] function and exposes new “at least” and “at most” graph types via [``jupyter_visualize``][anydyce.viz.jupyter_visualize] interface.

## [0.1.3](https://github.com/posita/anydyce/releases/tag/v0.1.3)

* Turns data limiting off by default in [``jupyter_visualize``][anydyce.viz.jupyter_visualize].

## [0.1.2](https://github.com/posita/anydyce/releases/tag/v0.1.2)

* Adds [``limit_for_display``][anydyce.viz.limit_for_display] and updates [``jupyter_visualize``][anydyce.viz.jupyter_visualize].

## [0.1.1](https://github.com/posita/anydyce/releases/tag/v0.1.1)

* Removes use of ``#!python numerary.types.…SCU`` types.
* Links to an external (Gist) repository for example notebook.
* Adds comparison table to AnyDice to ``README.md``.

## [0.1.0](https://github.com/posita/anydyce/releases/tag/v0.1.0)

``anydyce`` goes live!
Non-experimental features should be considered stable.
