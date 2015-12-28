# JRMC Variables, typically loaded from ~/.jrmc-utils
#     JRMC_HOST: the jrmc hostname
#     JRMC_PORT: the port jrmc is listening on
#     JRMC_USER: username for JRMC MCWS connection
#     JRMC_PASS: password for JRMC MCWS connection
#     MCWS_AUTH_TOKEN: a current auth token obtained via MCWS Authenticate
#
# Cache Variables
#     MEDIA_SRC_DIR: the dir containing the source material
#     MEDIA_CACHE_DIR: the dir containing the converted copies of the source material
#   
# Device Variables, typically set by the sourcing script
#     JRMC_PLAYLIST_PATH: the playlist path that defines the contents we will sync to the device
#     HANDHELD_MOUNT: the mount point for the device
#     HANDHELD_TARGET_DIR: the dir within the device to sync to (optional)
#
# Operational Variables
#     ENCODER_MODE: mp3
#     MP3_CONVERTER: lame, flac2all
#     ENCODER_OPTS: -preset medium

trap "clean_cache" EXIT

function clean_cache {
    if [[ -d "${CACHE_DIR}" && "${CLEAN_ON_EXIT}" -eq 1 ]] 
    then
	rm -Rf "${CACHE_DIR}"
    fi
}

# verifies that all required config is loaded
function validate_props {
    local MISSING_PROPS=()
    # check we can access JRMC
    [[ -z "${JRMC_HOST}" ]] && MISSING_PROPS+=("JRMC_HOST")
    [[ -z "${JRMC_PORT}" ]] && MISSING_PROPS+=("JRMC_PORT")
    # check we have something to sync
    [[ -z "${JRMC_PLAYLIST_PATH}" ]] && MISSING_PROPS+=("JRMC_PLAYLIST_PATH")
    [[ -z "${HANDHELD_MOUNT}" ]] && MISSING_PROPS+=("HANDHELD_MOUNT")
    # check we have some files
    [[ -z "${MEDIA_SRC_DIR}" ]] && MISSING_PROPS+=("MEDIA_SRC_DIR")
    [[ -z "${MEDIA_CACHE_DIR}" ]] && MISSING_PROPS+=("MEDIA_CACHE_DIR")
    # check we have chosen a mode
    [[ -z "${ENCODER_MODE}" ]] && MISSING_PROPS+=("ENCODER_MODE")
    [[ -z "${ENCODER_OPTS}" ]] && MISSING_PROPS+=("ENCODER_OPTS")
    [[ -z "${FLAC2ALL_DIR}" ]] && MISSING_PROPS+=("FLAC2ALL_DIR")
    
    if [ "${#MISSING_PROPS[@]}" -gt 0 ]
    then
	echo "Unable to continue, missing properties are ${MISSING_PROPS[@]}"
	exit 1
    fi
}

function validate_tools {
    hash xmlstarlet 2>/dev/null || (echo "xmlstarlet is required" && exit 1)
    [[ -d "${FLAC2ALL_DIR}" && -e "${FLAC2ALL_DIR}/flac2all.py" ]] || (echo "flac2all is required" && exit 1)
    hash python 2>/dev/null || (echo "python is required" && exit 1)
    if hash wakeonlan 2>/dev/null && -n "${JRMC_MAC}"
    then
	export NO_WOL=0
    else
	echo "wakeonlan is not available"
	export NO_WOL=1
    fi
}

function validate_mounts {
    [[ ! -d "${MEDIA_SRC_DIR}" ]] && (echo "Media Dir ${MEDIA_SRC_DIR} does not exist" && exit 1)
    [[ ! -d "${MEDIA_CACHE_DIR}" ]] && (echo "Cache Dir ${MEDIA_CACHE_DIR} does not exist" && exit 1)
    mountpoint -q "${HANDHELD_MOUNT}" 2>/dev/null || (echo "Handheld mount ${HANDHELD_MOUNT} does not exist" && exit 1)
    [[ ! -d "${HANDHELD_MOUNT}/${HANDHELD_TARGET_DIR}" ]] && echo "Handheld target dir ${HANDHELD_MOUNT}/${HANDHELD_TARGET_DIR} does not exist"
}

# Obtains an authentication token if one does not exist already
function authenticate {
    ensure_jrmc_alive
    if [ -z "${MCWS_AUTH_TOKEN}" ]
    then
        export MCWS_AUTH_TOKEN="$(curl -s -u ${JRMC_USER}:${JRMC_PASS} http://${JRMC_HOST}:${JRMC_PORT}/MCWS/v1/Authenticate | xmllint --xpath '/Response[@Status="OK"]/Item[@Name="Token"]/text()' - 2>/dev/null)"
	return $?
    else
	return 0
    fi
}

function ensure_jrmc_alive {
    local COUNTER=0
    local PING_HIT=0
    while [[ "${COUNTER}" -lt 30 && "${PING_HIT}" -eq 0 ]]
    do
	local RESULTS="$(ping -W 1 -c 1 "${JRMC_HOST}" 2>/dev/null)"
	if [[ $? -ne 0 && ${COUNTER} -eq 0 ]]
	then
	    echo "Unable to ping ${JRMC_HOST}"
	fi
        local PING_HIT=$(echo "${RESULTS}" | grep "from ${JRMC_HOST}" | wc -l)
	if [ "${PING_HIT}" -eq 0 ]
	then
	    [[ $((COUNTER%5)) -eq 0 ]] && do_wol
	fi
	COUNTER=$((COUNTER+1))
    done
}

function do_wol {
    if [[ "${NO_WOL}" -eq 0 ]]
    then
	wakeonlan "${JRMC_MAC}"
    fi
}

# calls mcws to list playlists and extracts the ID of a playlist with the given path
function get_playlist_id {
    export JRMC_PLAYLIST_ID=$(curl -s "http://${JRMC_HOST}:${JRMC_PORT}/MCWS/v1/Playlists/List?Token=${MCWS_AUTH_TOKEN}" | xmlstarlet sel -t -m "/Response/Item/Field[@Name=\"Path\"][text()=\"${JRMC_PLAYLIST_PATH}\"]/../Field[@Name=\"ID\"]" -v 'text()')
    return $?
}

# calls mcws to get the files in a given playlist id and dumps that as an m3u
function get_playlist_as_m3u {
    curl -s "http://${JRMC_HOST}:${JRMC_PORT}/MCWS/v1/Playlist/Files?Playlist=${JRMC_PLAYLIST_ID}&Fields=Filename&Token=${MCWS_AUTH_TOKEN}" | xmlstarlet sel -t -m '/MPL/Item/Field[@Name="Filename"]' -v "text()" -n - > "${CACHE_DIR}/mcws.m3u"
    return $?
}

# converts the mcws.m3u to unix format
# args; 1 the mcws library path prefix
function unixify_m3u {
    pushd "${CACHE_DIR}" > /dev/null 2>&1
    # TODO convert this to handle multiple paths
    sed "s~${1}~${MEDIA_SRC_DIR}~g" "${CACHE_DIR}/mcws.m3u" | sed 's~\\~\/~g' > "${CACHE_DIR}/unix.m3u"
    popd > /dev/null 2>&1
}

# converts the m3u to a dir full of symlinks
function create_source_device {
    mkdir "${CACHE_DIR}/source"
    pushd "${CACHE_DIR}/source" > /dev/null 2>&1
    while IFS='' read -r m3u_entry || [[ -n "${m3u_entry}" ]]
    do
	local RELATIVE_PATH="${m3u_entry/${MEDIA_SRC_DIR}\//}"
	local DIR_NAME="${RELATIVE_PATH%/*}"
	local FILE_NAME="${RELATIVE_PATH##*/}"
	mkdir -p "${DIR_NAME}"
        ln -s "${m3u_entry}" "${RELATIVE_PATH}"
    done < "../unix.m3u"
    local BROKEN_LINKS=$(find . -xtype l | wc -l)
    local TOTAL_LINKS=$(find . -type l | wc -l)
    [[ "${BROKEN_LINKS}" -gt 0 ]] && echo "${BROKEN_LINKS} files are missing" || echo "${TOTAL_LINKS} files to sync"
    popd > /dev/null 2>&1
}

# converts the source device to the output format
function create_target_device {
    mkdir "${CACHE_DIR}/target"
    pushd "${CACHE_DIR}/target" > /dev/null 2>&1
    populate_conversion_cache
    create_target_device_links
    popd > /dev/null 2>&1
}

# converts the target device to the output format using flac2all for max powah
function populate_conversion_cache {
    python "${FLAC2ALL_DIR}"/flac2all.py mp3 ../source -l"${ENCODER_OPTS}" -o "${MEDIA_CACHE_DIR}"
}

# creates the target device from the cache dir
function create_target_device_links {
    for RELATIVE_SOURCE_FILE in $(find ../source -name \*.flac | sed 's~../source/~~g' )
    do
	local RELATIVE_TARGET_FILE="${RELATIVE_SOURCE_FILE/flac/mp3}"
	local SOURCE_FILE="${MEDIA_SRC_DIR}/${RELATIVE_SOURCE_FILE}"
	local CACHED_FILE="${MEDIA_CACHE_DIR}/${RELATIVE_TARGET_FILE}"
        if [ ! -e "${CACHED_FILE}" ]
        then
            echo "ERROR! ${CACHED_FILE} does not exist"
	else
    	    mkdir -p "${RELATIVE_TARGET_FILE%/*}"
            ln -s "${CACHED_FILE}" "${RELATIVE_TARGET_FILE}"
	fi
    done
}

# rsyncs from A to B in dryrun mode
function do_dryrun_sync {
    do_sync "n" "${1}" "${2}"
}

# rsyncs from A to B
function do_sync {
    rsync -rtv${1} --modify-window=1 "${2}" "${3}"
}

function calculate_free_space {
    # TODO implement
    return 0
}

function calculate_required_space {
    # TODO implement
    return 0
}

function is_space_available {
    # TODO implement
    return 0
}

function load_defaults {
    # set/load default values
    [[ -z "${JRMC_CONF_FILE}" ]] && JRMC_CONF_FILE="${HOME}/.jrmc-utils"
    [[ -e "${JRMC_CONF_FILE}" ]] && source "${JRMC_CONF_FILE}"
    [[ -z "${JRMC_PORT}" ]] && export JRMC_PORT=52199
    [[ -z "${CACHE_DIR}" ]] && export CACHE_DIR="/tmp/$$" && mkdir -p "/tmp/$$"
    [[ -z "${ENCODER_MODE}" ]] && export ENCODER_MODE="flac2all"
    [[ -z "${ENCODER_OPTS}" ]] && export ENCODER_OPTS="-preset medium"
    [[ -z "${CLEAN_ON_EXIT}" ]] && export CLEAN_ON_EXIT=1
}

load_defaults
validate_props
validate_tools
validate_mounts
