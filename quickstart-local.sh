#!/usr/bin/env bash

set \
    -o errexit \
    -o nounset \
    -o pipefail

PROG_NAME="$( basename "${0}" )"
PROG_DIR="$( cd "$( dirname "${0}" )" && pwd )"
PYTHON="${PYTHON:-}"
VIRTUAL_ENV="${PROG_DIR}/.venv"

if [ -z "${PYTHON}" ] ; then
    echo 1>&2 'PYTHON not set; trying to find Python >=3.11'

    for python in python python3 python3.14 python3.13 python3.12 python 3.11 ; do
        if "${python}" 2>/dev/null -c 'import sys ; sys.exit(sys.version_info < (3, 11))' ; then
            PYTHON="${python}"
            break
        fi
    done

    if [ -z "${PYTHON}" ] ; then
        echo 1>&2 "${0}: can't find Python >=3.11 (override by setting PYTHON); giving up"

        return 1
    fi
fi

set -o xtrace

[ -x "${VIRTUAL_ENV}/bin/python3" ] \
    || "${PYTHON}" -m venv "${VIRTUAL_ENV}"
[ -x "${VIRTUAL_ENV}/bin/uv" ] \
    || "${VIRTUAL_ENV}/bin/pip" install uv
exec uv run --group docs --no-dev mkdocs serve "${@}"
