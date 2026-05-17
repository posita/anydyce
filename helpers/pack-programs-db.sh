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
    -o pipefail

PROG_NAME="$( basename "${0}" )"
PROG_DIR="$( cd "$( dirname "${0}" )" && pwd )"
if [ "${#}" -eq 0 ] ; then
    dbs=( "${PROG_DIR}/anydice-programs.db" )
else
    dbs=( "${@}" )
fi

for db in "${dbs[@]}" ; do
    if ! [ -e "${db}" ] ; then
        echo 1>&2 "${PROG_NAME}: ignoring nonexistent file (${db})"
        continue
    elif [ "${db%.db}" = "${db}" ] ; then
        echo 1>&2 "${PROG_NAME}: ignoring non-database file (${db})"
        continue
    fi
    if [ -f "${db}.sha256" ] \
            && ( cd "$( dirname "${db}" )" &&
                sha256sum --check "$( basename "${db}.sha256" )" ) ; then
        echo "${PROG_NAME}: sha256sum matches; nothing to do"
        continue
    elif ! [ -f "${db}.sha256" ] ; then
        echo 1>&2 "${PROG_NAME}: sha256sum file missing, recompressing"
    else
        echo 1>&2 "${PROG_NAME}: sha256sum mismatch, recompressing"
    fi
    # This trusts the current stamp of the .db file, which may not reflect its true
    # modification time (e.g., for a newly inflated .db), but we only honor it hashes
    # don't match (signaling an edit), or if we're missing hashes (where we have to
    # trust *something*), but this is certainly good enough for our purposes.
    new_db_gz="${db%.db}-$( date -r "${db}" +%Y-%m-%dT%H:%M:%S%z ).db.gz"
    set -o xtrace
    gzip --best --rsyncable --stdout "${db}" >"${new_db_gz}.part"
    mv "${new_db_gz}.part" "${new_db_gz}"
    ln --force --no-dereference --symbolic "$( basename "${new_db_gz}" )" "${db}.gz"
    ( cd "$( dirname "${db}" )" &&
        sha256sum >"$( basename "${db}.sha256" )" "$( basename "${db}" )" "$( basename "${db}.gz" )" )
    set +o xtrace
done
