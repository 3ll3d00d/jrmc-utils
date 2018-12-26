#!/bin/bash
if [ -n "${1}" ]
then
    echo "Loading sync config from ${1}"
    set -a
    source "${1}"
    set +a
else
    echo "No sync config, exiting"
    exit 1
fi

source "${JRMC_UTILS_DIR}/functions.sh"

authenticate
get_playlist_id
get_playlist_as_m3u
# TODO config this
unixify_m3u "Z:"
create_source_device
create_target_device
do_sync
