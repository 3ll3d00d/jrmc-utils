# JRMC Variables, typically loaded from ~/.jrmc-utils
#     JRMC_HOST: the jrmc hostname
#     JRMC_PORT: the port jrmc is listening on
#     JRMC_USER: username for JRMC MCWS connection
#     JRMC_PASS: password for JRMC MCWS connection
#     MCWS_AUTH_TOKEN: a current auth token obtained via MCWS Authenticate
#
# Cache Variables
#     MEDIA_DIR: the dir containing the source material
#     CACHE_DIR: the dir containing the converted copies of the source material
#   
# Device Variables, typically set by the sourcing script
#     JRMC_PLAYLIST_PATH: the playlist path that defines the contents we will sync to the device
#     HANDHELD_DEVICE: the device name
#     HANDHELD_MOUNT: the mount point for the device
#     HANDHELD_TARGET_DIR: the dir within the device to sync to (optional)
#
# Operational Variables
#     ENCODER_MODE: mp3
#     MP3_CONVERTER: lame, flac2all
#     ENCODER_OPTS: -preset medium

# verifies that all required config is loaded
function validate_props {
    local MISSING_PROPS=()
    # check we can access JRMC
    [[ -z "${JRMC_HOST}" ]] && MISSING_PROPS += ("JRMC_HOST")
    [[ -z "${JRMC_PORT}" ]] && MISSING_PROPS += ("JRMC_PORT")
    # check we have something to sync
    [[ -z "${JRMC_PLAYLIST_PATH}" ]] && MISSING_PROPS += ("JRMC_PLAYLIST_PATH")
    [[ -z "${HANDHELD_DEVICE}" ]] && MISSING_PROPS += ("HANDHELD_DEVICE")
    [[ -z "${HANDHELD_MOUNT}" ]] && MISSING_PROPS += ("HANDHELD_MOUNT")
    # check we have some files
    [[ -z "${MEDIA_DIR}" ]] && MISSING_PROPS += ("MEDIA_DIR")
    # check we have chosen a mode
    [[ -z "${ENCODER_MODE}" ]] && MISSING_PROPS += ("ENCODER_MODE")
    [[ -z "${ENCODER_OPTS}" ]] && MISSING_PROPS += ("ENCODER_OPTS")
    
    if [ "${#MISSING_PROPS[@]}" -gt 0 ]
    then
	echo "Unable to continue, missing properties are ${MISSING_PROPS[@]}"
	exit 1
    fi
}

function validate_tools {
    # use hash to test that lame etc are present
}

function validate_mounts {
    [[ ! -d "${MEDIA_DIR}" ]] && echo "Media Dir (${MEDIA_DIR}) does not exist" && exit 1
    [[ ! -d "${CACHE_DIR}" ]] && echo "Cache Dir (${CACHE_DIR}) does not exist" && exit 1
}

# Obtains an authentication token if one does not exist already
function authenticate {
    if [ -z "${MCWS_AUTH_TOKEN}" ]
    then
        MCWS_AUTH_TOKEN="$(curl -s -u ${JRMC_USER}:${JRMC_PASS} http://${JRMC_HOST}:${JRMC_PORT}/MCWS/v1/Authenticate | xmllint --xpath '/Response[@Status="OK"]/Item[@Name="Token"]/text()' - 2>/dev/null)"
    fi
}

# calls mcws to list playlists and extracts the ID of a playlist with the given path
function get_playlist_id {
    authenticate
    PLAYLIST_ID=$(curl -s "http://${JRMC_HOST}:${JRMC_PORT}/MCWS/v1/Playlists/List?Token=${MCWS_AUTH_TOKEN}" | xmlstarlet sel -t -m "/Response/Item/Field[@Name=\"Path\"][text()=\"${PLAYLIST_PATH}\"]/../Field[@Name=\"ID\"]" -v 'text()')
    echo "${PLAYLIST_ID}"
}

# calls mcws to get the files in a given playlist id and dumps that as an m3u
function get_playlist_as_m3u {
    mkdir -p /tmp/${1}
    curl -s "http://${JRMC_HOST}:${JRMC_PORT}/MCWS/v1/Playlist/Files?Playlist=${PLAYLIST_ID}&Fields=Filename&Token=${MCWS_AUTH_TOKEN}" | xmlstarlet sel -t -m '/MPL/Item/Field[@Name="Filename"]' -v "text()" -n - > /tmp/${1}/mcws.m3u
}

# converts the mcws.m3u to unix format
# args; 1 the playlist id, 2 the mcws library path prefix, 3 the actual path prefix to the files
function unixify_m3u {
    pushd /tmp/${1} > /dev/null 2>&1
    sed "s~${2}~${3}~g" /tmp/${1}/mcws.m3u | sed 's~\\~\/~g' > /tmp/${1}/unix.m3u
    popd > /dev/null 2>&1
}

# converts the m3u to a dir full of symlinks
function create_source_device {
    mkdir /tmp/${1}/source
    pushd /tmp/${1}/source > /dev/null 2>&1
    while IFS='' read -r m3u_entry || [[ -n "${m3u_entry}" ]]
    do
        ln -s "${m3u_entry}"
    done < "unix.m3u"
    local BROKEN_LINKS=$(find . -xtype l | wc -l)
    local TOTAL_LINKS=$(find . -type l | wc -l)
    [[ "${BROKEN_LINKS}" -gt 0 ]] && echo "${BROKEN_LINKS} files are missing" || echo "${TOTAL_LINKS} files to sync"
    popd > /dev/null 2>&1
}

# converts the source device to the output format
function create_target_device {
    mkdir /tmp/${1}/target
    pushd /tmp/${1}/target > /dev/null 2>&1
    for source_file in $(ls ../source/*.flac | xargs basename)
    do
	local CACHED_FILE="${CACHE_DIR}/${source_file/flac/mp3}"
        if [ ! -e "${CACHED_FILE}" ]
        then
	    convert_to_mp3 "${source_file}" "${CACHED_FILE}"
	fi
        ln -s "${CACHED_FILE}"
    done
    popd > /dev/null 2>&1
}

# converts the target device to mp3
function convert_to_mp3 {
    # TODO allow user to override the mp3 encoding params
    lame --preset medium "${1}" "${2}"
}

function do_dryrun_sync {
    do_sync "n" "${1}" "${2}"
}

function do_sync {
    rsync -rtv${1} --modify-window=1 "${2}" "${3}"
}

# set/load default values 
[[ -z "${JRMC_CONF_FILE}" ]] && "${HOME}/.jrmc-utils"
[[ -e "${JRMC_CONF_FILE}" ]] && source "${JRMC_CONF_FILE}"
[[ -z "${JRMC_PORT}" ]] && JRMC_PORT=52199
[[ -z "${CACHE_DIR}" ]] && CACHE_DIR="/tmp/$$" && mkdir -p "/tmp/$$"
[[ -z "${ENCODER_MODE}" ]] && ENCODER_MODE="mp3"
[[ -z "${ENCODER_OPTS}" ]] && ENCODER_OPTS="-preset medium"

validate_props
validate_tools
validate_mounts
