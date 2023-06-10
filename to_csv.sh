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
    local FN=$(basename $(pwd))_${BIT_DEPTH}.csv
    local IDX=0
    local LAST_IMG_COLOUR=x
    rm -f ${FN}
    touch ${FN}
    for PATCH in $(find input -type f -name \*.png | sort)
    do
        IMG_COLOUR=$(convert ${PATCH} -crop 1x1+0+0 -depth ${BIT_DEPTH} -format "%[fx:int(${SCALE}*r+.5)],%[fx:int(${SCALE}*g+.5)],%[fx:int(${SCALE}*b+.5)]" info:- )
        if [[ ${LAST_IMG_COLOUR} != ${IMG_COLOUR} ]]
        then
            echo "${IDX},${IMG_COLOUR}" >> ${FN}
            IDX=$((IDX+1))
        fi
        LAST_IMG_COLOUR=${IMG_COLOUR}
    done
    if [[ ${LAST_IMG_COLOUR} != ${IMG_COLOUR} ]]
    then
        echo "${IDX},${IMG_COLOUR}" >> ${FN}
    fi
    
    popd > /dev/null 2>&1
}

do_it 3dlut/112/input
do_it 3dlut/407/input
do_it 3dlut/1519/input
do_it 3dlut/2647/input
do_it gamma/10pt/input
do_it gamma/20pt/input
