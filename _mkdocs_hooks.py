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

import importlib.metadata
import json
import logging
import os
import re
import shutil
import subprocess  # noqa: S404
import sys
import tomllib
import urllib.request
from collections.abc import Iterable, Iterator, Sequence
from pathlib import Path
from urllib.parse import urlsplit

_LOGGER = logging.getLogger("mkdocs.hooks")

_RAW_VERSION = importlib.metadata.version("anydyce")
# Dev/dirty builds (e.g. "0.1.0.dev5+gabcdef") fall back to "main"
_IS_RELEASE = "+" not in _RAW_VERSION and ".dev" not in _RAW_VERSION
_GIT_REF = f"v{_RAW_VERSION}" if _IS_RELEASE else "main"
# mike deploys under "major.minor"; dev builds link to "latest"
_parts = _RAW_VERSION.split(".")
_DOCS_VERSION = f"{_parts[0]}.{_parts[1]}" if _IS_RELEASE else "latest"
del _parts
_BUNDLED_PKG_NAMES = ("dyce", "lark", "optype")
# ipywidgets and its dependencies (see uv pip tree)
_JUPYTER_BUNDLED_PKG_NAMES = ("ipywidgets", "jupyterlab-widgets", "widgetsnbextension")


def on_page_markdown(markdown: str, **_kwargs: object) -> str:
    markdown = re.sub(
        r"<!-- mkdocs:hide:start -->.*?<!-- mkdocs:hide:end -->",
        "",
        markdown,
        flags=re.DOTALL,
    )
    return markdown.replace("{anydyce_git_ref}", _GIT_REF)


def on_pre_build(**_kwargs: object) -> None:
    readme = Path("README.md").read_text("utf_8")
    index = readme
    # Replace 'main' with the version-specific git ref in GitHub source URLs
    index = re.sub(
        r"(https?://(?:raw\.githubusercontent\.com|github\.com)/posita/anydyce/(?:blob/|tree/)?)main\b",
        rf"\g<1>{_GIT_REF}",
        index,
    )
    # Replace 'latest' with the docs version in docs site URLs
    index = index.replace(
        "https://posita.github.io/anydyce/latest/",
        f"https://posita.github.io/anydyce/{_DOCS_VERSION}/",
    )
    # For release builds, restore version-specific shields.io badge URLs and PyPI link
    if _IS_RELEASE:
        index = re.sub(
            r"(https://img\.shields\.io/pypi/[^/]+/anydyce)(\.svg)",
            rf"\g<1>/{_RAW_VERSION}\g<2>",
            index,
        )
        index = re.sub(
            r"(https://pypi\.org/project/anydyce/)(?=\))",
            rf"\g<1>{_RAW_VERSION}/",
            index,
        )
    index_path = Path("docs/index.md")
    # Only write if changed to avoid a feedback loop with `mkdocs serve --livereload`
    if not index_path.exists() or index_path.read_text("utf_8") != index:
        index_path.write_text(index, "utf_8")

    # Use copy2 to preserve modification times to avoid a feedback loop with `mkdocs
    # serve --livereload`
    shutil.copy2("LICENSE", "docs/license.md")

    _uv_run(("make", "-C", "docs"))


def on_post_build(config: dict, **_kwargs: object) -> None:
    cmd = ["uv", "build", "--wheel"]
    _LOGGER.info("running %s", " ".join(cmd))
    subprocess.run(cmd, check=True)  # noqa: S603

    cmd = [
        "jupyter",
        "lite",
        "build",
        "--debug",
        "--output-dir",
        f"{config['site_dir']}/jupyter",
    ]
    wheels: list[Path | str] = [_get_latest_pkg_wheel_from_dist()]
    wheels.extend(_bundled_wheel_urls(_BUNDLED_PKG_NAMES))
    wheels.extend(_bundled_wheel_urls(_JUPYTER_BUNDLED_PKG_NAMES))
    # Fuck you, Jupyter Lite, for costing me hours to work through your lies. (See
    # <https://github.com/jupyterlite/jupyterlite/issues/1563>.)
    for wheel in wheels:
        cmd.extend(("--piplite-wheels", str(wheel)))
    _uv_run(cmd)
    # TODO(posita): # noqa: TD003 - At this point, all commonly-needed wheels should be
    # downloaded to site/jupyter/pypi/... if we ever wanted to just use those instead
    _bundle_playground_with_wheels_and_index(Path(config["site_dir"]))


def _bundle_playground_with_wheels_and_index(site_dir: Path) -> None:
    r"""
    Download wheels and ship uv.lock-pinned dependencies with the playground for
    reliability/consistency/performance. Serve same-origin to avoid CORS issues.
    """
    src = Path("playground")
    dst = site_dir / src.name

    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(
        src,
        dst,
        ignore=shutil.ignore_patterns(
            # Dev only bits
            "node_modules",
            "package.json",
            "test",
        ),
    )

    wheels_dir = dst / "wheels"
    wheels_dir.mkdir(parents=True, exist_ok=True)
    names: list[str] = []
    for url in _bundled_wheel_urls(_BUNDLED_PKG_NAMES):
        _LOGGER.info("downloading %s", url)
        parts = urlsplit(url)
        filename = Path(parts.path).name
        urllib.request.urlretrieve(url, wheels_dir / filename)  # noqa: S310
        names.append(filename)
    pkg_whl = _get_latest_pkg_wheel_from_dist()
    shutil.copy2(pkg_whl, wheels_dir / pkg_whl.name)
    names.append(pkg_whl.name)
    (wheels_dir / "index.json").write_text(json.dumps(names, indent=2) + "\n", "utf_8")

    _LOGGER.info("bundled playground -> %s (%d wheels)", dst, len(names))


def _bundled_wheel_urls(pkg_names: Iterable[str]) -> Iterator[str]:
    uv_lock_path = Path("uv.lock")
    for pkg_name in pkg_names:
        with uv_lock_path.open("rb") as f:
            uv_lock = tomllib.load(f)
        pkg = next(p for p in uv_lock["package"] if p["name"] == pkg_name)
        try:
            yield next(
                w["url"]
                for w in pkg.get("wheels", [])
                if re.search(r"\bnone-any\b", w["url"])
            )
        except StopIteration:
            raise RuntimeError(
                f"no none-any wheel for {pkg!r} found in {uv_lock_path}"
            ) from None


def _get_latest_pkg_wheel_from_dist() -> Path:
    return max(Path("dist").glob("anydyce*-none-any.whl"), key=os.path.getmtime)


def _uv_run(cmd: Sequence[str]) -> None:
    uv_cmd = ["uv", "run", "--group", "docs"]
    venv_path = Path(os.getenv("VIRTUAL_ENV", "")).resolve()
    mkdocs_path = Path(sys.argv[0]).resolve()
    if venv_path.stem.startswith(".venv") and mkdocs_path.is_relative_to(venv_path):
        uv_cmd.append("--active")
    uv_cmd.extend(cmd)
    _LOGGER.info("running %s", " ".join(uv_cmd))
    subprocess.run(uv_cmd, check=True)  # noqa: S603
