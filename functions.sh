# Global variables
#     JRMC_HOST: the jrmc hostname
#     JRMC_PORT: the port jrmc is listening on
#     MCWS_AUTH_TOKEN: a current auth token obtained via MCWS Authenticate
#     JRMC_CREDS: a .credentials file from which JRMC_USER and JRMC_PASS can be read
#     JRMC_USER: username for JRMC MCWS connection
#     JRMC_PASS: password for JRMC MCWS connection
#

# loads JRMC_USER and JRMC_PASS from JRMC_CREDS
# returns 0 if creds are set by the end of the call
function load_creds {
    if [[ -z "${JRMC_USER}" || -z "${JRMC_PASS}" ]]
    then
        if [ -e "${JRMC_CREDS}" ]
        then
	    source "${JRMC_CREDS}"
	else
	    echo "Creds file ${JRMC_CREDS} does not exist"
	    return 1
        fi
    fi
    [[ -z "${JRMC_USER}" || -z "${JRMC_PASS}" ]] && return 1 || return 0
}

# Obtains an authentication token if one does not exist already
function authenticate {
    if [ -z "${MCWS_AUTH_TOKEN}" ]
    then
        load_creds
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
    rsync -rtv${1} --modify-window=1 ${2} ${3}
}
