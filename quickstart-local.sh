#!/usr/bin/env bash

_MY_DIR="$( cd "$( dirname "${0}" )" && pwd )"
_VENVSETUP_DIR="${_MY_DIR}/.venv"

_venvsetup() {
    (
        set -ex

        if [ ! -e "${_VENVSETUP_DIR}/bin/tox" ] ; then
            if [ -z "${PYTHON}" ] ; then
                echo 1>&2 'PYTHON not set; trying to find Python >=3.8'

                for python in python python3 python3.10 python3.9 python3.8 ; do
                    if "${python}" 2>/dev/null -c 'import sys ; sys.exit(sys.version_info < (3, 8))' ; then
                        PYTHON="${python}"
                        break
                    fi
                done

                if [ -z "${PYTHON}" ] ; then
                    echo 1>&2 "${0}: can't find Python >=3.8 (override by setting PYTHON); giving up"

                    return 1
                fi
            fi

            "${PYTHON}" -m venv "${_VENVSETUP_DIR}"
            "${_VENVSETUP_DIR}/bin/pip" install --upgrade tox
        fi
   ) \
        || return "${?}"
}

_venvsetup \
    && "${_VENVSETUP_DIR}/bin/tox" -e jupyter -- --notebook-dir="${_MY_DIR}/docs/notebooks" "${@}"
