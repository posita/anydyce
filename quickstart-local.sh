#!/usr/bin/env bash
# ======================================================================================
# Copyright and other protections apply. Please see the accompanying LICENSE file for
# rights and restrictions governing use of this software. All rights not expressly
# waived or licensed are reserved. If that file is missing or appears to be modified
# from its original, then please contact the author before viewing or using this
# software in any capacity.
# ======================================================================================
set \
    -o errexit \
    -o nounset \
    -o pipefail \
    -o xtrace

PROG_DIR="$( cd "$( dirname "${0}" )" && pwd )"
QS_VENV_DIR="${PROG_DIR}/.venv-quickstart"
QS_UV_CMD="${QS_VENV_DIR}/bin/uv"
[ -d "${QS_VENV_DIR}/bin" ] \
    || python3 -m venv "${QS_VENV_DIR}"
[ -x "${QS_UV_CMD}" ] \
    || "${QS_VENV_DIR}/bin/pip" install uv
source "${QS_VENV_DIR}/bin/activate"
"${QS_UV_CMD}" sync --active --only-group quickstart --no-dev
exec "${QS_UV_CMD}" run mkdocs serve "${@}"
