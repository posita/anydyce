#!/usr/bin/env bash
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
