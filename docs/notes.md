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

# `anydyce` release notes

## [0.5.0](https://github.com/posita/anydyce/releases/tag/v0.5.0)

!!! warning "Breaking changes"

    Some of the following changes are not backward compatible.
    Please review before upgrading.

- Drops support for 3.9 and 3.10 and extends support to 3.14
<!-- TODO(posita): Fill this out -->
- Removes the following (analogies now live in [`dyce==0.7.0`](https://github.com/posita/dyce/releases/tag/v0.7.0).
  - `anydyce.viz.alphasize`
  - `anydyce.viz.cumulative_probability_formatter`
  - `anydyce.viz.graph_colors`
  - `anydyce.viz.outcome_name_formatter`
  - `anydyce.viz.outcome_name_probability_formatter`
  - `anydyce.viz.plot_bar`
  - `anydyce.viz.plot_burst_subplot`
  - `anydyce.viz.plot_burst`
  - `anydyce.viz.plot_line`
  - `anydyce.viz.plot_scatter`
  - `anydyce.viz.probability_formatter`

  <!-- - `anydyce.viz.limit_for_display` -->
  <!-- - `anydyce.viz.values_xy_for_graph_type` -->
  <!-- - `anydyce.viz.` -->

## [0.4.6](https://github.com/posita/anydyce/releases/tag/v0.4.6)

- Relaxed `ipywidgets` dependency to `>=7.5,<9` to better accommodate JupyterLite after prior version crashed and burned

## [0.4.5](https://github.com/posita/anydyce/releases/tag/v0.4.5)

- Stabilized Jupyter Lite installation
- Adjusted typing slightly
- Defaulted to collapsed installation cells
- Acknowledged removal of PyPy support ([beartype/beartype#324](https://github.com/beartype/beartype/issues/324))

## [0.4.4](https://github.com/posita/anydyce/releases/tag/v0.4.4)

- Added `SettingsDict["burst_columns"]` and related widget.
- Added `None` as an acceptable item value for `histogram_specs` parameter to [`HPlotterChooser` initializer][anydyce.viz.HPlotterChooser], [`HPlotterChooser.update_hs`][anydyce.viz.HPlotterChooser.update_hs], and [`jupyter_visualize`][anydyce.viz.jupyter_visualize].

## [0.4.3](https://github.com/posita/anydyce/releases/tag/v0.4.3)

- Restored [rich display](https://ipython.readthedocs.io/en/stable/config/integrating.html#integrating-rich-display) hook methods accidentally removed from `anydyce.viz.Image` in [v0.4.2](#042).

## [0.4.2](https://github.com/posita/anydyce/releases/tag/v0.4.2)

!!! bug

    ***Do not use!***
    This release inadvertently removed [rich display](https://ipython.readthedocs.io/en/stable/config/integrating.html#integrating-rich-display) hook methods from `anydyce.viz.Image`.
    That broke the ability to display interactive plots.
    (Fixed in [v0.4.3](#043).)

- Allows *true* cutoff disablement (not merely a small default).

## [0.4.1](https://github.com/posita/anydyce/releases/tag/v0.4.1)

- Adds transparency as well as PNG and SVG output and download selections.
- Fixes display inconsistencies between Jupyter Lab and Jupyter Lite.

## [0.4.0](https://github.com/posita/anydyce/releases/tag/v0.4.0)

- Adds [`HPlotterChooser`][anydyce.viz.HPlotterChooser] implementation and substantially refactors [`jupyter_visualize`][anydyce.viz.jupyter_visualize] in terms thereof.

## [0.3.2](https://github.com/posita/anydyce/releases/tag/v0.3.2)

- Works around [jupyterlite/jupyterlite#838](https://github.com/jupyterlite/jupyterlite/issues/838) to fix docs.

## [0.3.1](https://github.com/posita/anydyce/releases/tag/v0.3.1)

- Fixes badges in docs.
- Migrates to `jupyterlite==0.1.0b13`.
- Un-breaks 0.3.0 in JupyterLite.

## [0.3.0](https://github.com/posita/anydyce/releases/tag/v0.3.0)

- Migrates to `ipywidgets~=8.0`.

## [0.2.0](https://github.com/posita/anydyce/releases/tag/v0.2.0)

- Completes update to `dyce~=0.6`.
- Migrates from [`setuptools_scm`](https://pypi.org/project/setuptools-scm/) to [`versioningit`](https://pypi.org/project/versioningit/) for more flexible version number formatting.
- Allows deployments to PyPI from CI based on tags.

## [0.1.6](https://github.com/posita/anydyce/releases/tag/v0.1.6)

- `ipywidgets` and `matplotlib` are now required dependencies.
- Minor corrections to required Python version.

## [0.1.4](https://github.com/posita/anydyce/releases/tag/v0.1.4)

- Prepares for breaking changes in future release of `dyce~=0.6`.
- Adds experimental [`values_xy_for_graph_type`][anydyce.viz.values_xy_for_graph_type] function and exposes new “at least” and “at most” graph types via [`jupyter_visualize`][anydyce.viz.jupyter_visualize] interface.

## [0.1.3](https://github.com/posita/anydyce/releases/tag/v0.1.3)

- Turns data limiting off by default in [`jupyter_visualize`][anydyce.viz.jupyter_visualize].

## [0.1.2](https://github.com/posita/anydyce/releases/tag/v0.1.2)

- Adds [`limit_for_display`][anydyce.viz.limit_for_display] and updates [`jupyter_visualize`][anydyce.viz.jupyter_visualize].

## [0.1.1](https://github.com/posita/anydyce/releases/tag/v0.1.1)

- Removes use of `numerary.types.…SCU` types.
- Links to an external (Gist) repository for example notebook.
- Adds comparison table to AnyDice to `README.md`.

## [0.1.0](https://github.com/posita/anydyce/releases/tag/v0.1.0)

`anydyce` goes live!
Non-experimental features should be considered stable.
