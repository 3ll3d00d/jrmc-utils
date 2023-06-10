#!/bin/bash 
BIT_DEPTH=10
SCALE=1023

function seed_cache {
    if [[ ! -e ${COLOUR_DIR}/${IMG_COLOUR}.${1}.${3} ]]
    then
        if [[ -e ${2}/${4} ]]
        then
            if [[ ! -e ${COLOUR_DIR}/${IMG_COLOUR}.${1}.${3} ]]
            then
                echo "${IMG_COLOUR} :: Adding ${1} ${3}"
                cp ${2}/${4} ${COLOUR_DIR}/${IMG_COLOUR}.${1}.${3}
                return 1
            fi
        fi
    fi
    return 0
}


function do_it {
    PATCH_SET=${1}
    echo "Searching ${PATCH_SET}"
    pushd ${PATCH_SET}/.. > /dev/null 2>&1
    for PATCH in $(find input -type f -name \*.png | sort)
    do
        IMG_COLOUR=$(convert ${PATCH} -crop 1x1+0+0 -depth ${BIT_DEPTH} -format "%[fx:int(${SCALE}*r+.5)]_%[fx:int(${SCALE}*g+.5)]_%[fx:int(${SCALE}*b+.5)]" info:- )
        COLOUR_DIR="${CACHE_DIR}/${IMG_COLOUR}"
        FILE_NAME=$(basename ${PATCH})
        mkdir -p ${COLOUR_DIR}
        local ADDED=0
        if [[ ! -e ${COLOUR_DIR}/${IMG_COLOUR}.patch.png ]]
        then
            echo "New cache entry ${IMG_COLOUR}"
            cp ${PATCH} ${COLOUR_DIR}/${IMG_COLOUR}.patch.png
            ADDED=$((ADDED + 1))
        fi
        seed_cache "scaled" "HD" "png" ${FILE_NAME}
        ADDED=$((ADDED + $?))
        seed_cache "1s" "MP4" "mp4" "${FILE_NAME%.*}.mp4"
        ADDED=$((ADDED + $?))
        seed_cache "check" "checker" "png" ${FILE_NAME}
        ADDED=$((ADDED + $?))
        
        if [[ ${ADDED} -eq 0 ]]
        then
            echo "${IMG_COLOUR} :: Exists"
        fi
    done
    popd > /dev/null 2>&1
}

CACHE_DIR=/media/home-media/docs/calibration/cache/10
mkdir -p ${CACHE_DIR}

do_it 3dlut/112/input
do_it 3dlut/407/input
do_it 3dlut/1519/input
do_it 3dlut/2647/input
do_it gamma/10pt/input
do_it gamma/20pt/input
