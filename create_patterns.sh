#!/bin/bash 
function colour_name {
    if [[ ${1} =~ ([[:digit:]]{1,5}),([[:digit:]]{1,5}),([[:digit:]]{1,5}) ]]
    then
      local R=${BASH_REMATCH[1]}
      local G=${BASH_REMATCH[2]}
      local B=${BASH_REMATCH[3]}
      if [[ ${R} == ${G} ]] && [[ ${G} == ${B} ]]
      then
        # grey scale (assume gamma ramp)
        echo "$(printf %.0f%% $(echo "${R}/${SCALE} * 100"| bc -l))"
      else
        echo "${1}"
      fi
    else 
        echo "${1}"
    fi  
}


function check_output {
    if [[ ${1} != ${2} ]]
    then
        local TXT="E ${1} vs A ${2}"
        local EXPECTED_SUM=$(tr ',' '+' <<< ${1} | bc)
        local ACTUAL_SUM=$(tr ',' '+' <<< ${2} | bc)
        local DELTA=$((ACTUAL_SUM-EXPECTED_SUM))
        local STATUS=0
        local ALLOWED=$(echo "2 ^ (${BIT_DEPTH} - 8)" | bc)
        [[ ${DELTA#-} -le ${ALLOWED} ]] && STATUS=1 || STATUS=2
        if [[ ${STATUS} -eq 1 ]]
        then
            echo "ROUNDING! ${TXT}"
        else
            echo "ERROR! Off by ${DELTA} (${TXT})"
        fi
    else
        echo "OK!"
    fi
}

function gen {
    local IMG_IDX=${1}
    local IMG_COLOUR=${2}
    local IMG_DURATION=${3}
    local IMG_FILE=${4}
    local COLOUR_NAME=$(colour_name ${IMG_COLOUR})
    echo -e "${IMG_IDX}\t${IMG_COLOUR}\t${COLOUR_NAME}\t${IMG_DURATION}\t${IMG_FILE}"
    LFN=$(basename ${IMG_FILE})
    MP4_NAME=MP4/"${LFN%.*}".mp4
    if [[ ${DRY_RUN} -eq 0 ]]
    then
        local ENABLE_EXPR=""
        if [[ ${IMG_DURATION} -gt 10 ]]
        then
          ENABLE_EXPR=":enable='between(t,0,8)'"
        fi
        local TXT_COLOUR="Gray"
        # Gray in ffmpeg is 50% so if we have a direct match then avoid it
        [[ "${COLOUR_NAME}" == "50%" ]] && TXT_COLOUR="0x696969"
        convert -resize 1920x1080\! "${IMG_FILE}" "PNG48:HD/${LFN}"
        local OVERLAY="${IMG_IDX} - ${COLOUR_NAME}"
        local START=$(date +%s.%3N)
        ffmpeg -y -loop 1 -i "HD/${LFN}" -c:v libx265 -t ${IMG_DURATION} -vf "colorspace=all=bt709:iall=bt601-6-625:fast=1:format=yuv420p10, drawtext=text='${OVERLAY}':fontcolor=${TXT_COLOUR}:x=40:y=h-th-40${ENABLE_EXPR}:expansion=none:fontsize=36" -colorspace 1 -color_primaries 1 -color_trc 1 -sws_flags "accurate_rnd+full_chroma_int" "${MP4_NAME}" >> ffmpeg_debug.txt 2>&1
        local END=$(date +%s.%3N)
        local ENCODE_TIME_SECS=$(echo "${END} - ${START}" | bc -l)
        echo "Encode time: ${ENCODE_TIME_SECS}s"
        if [[ $? -ne 0 ]]
        then
            echo "Failed to encode ${MP4_NAME}"
        else
            local CHECK_PNG="checker/${LFN%%.*}.png"
            ffmpeg -y -i "${MP4_NAME}" -frames:v 1 -vf scale=out_color_matrix=srgb=full_chroma_int+accurate_rnd,format=rgb48le ${CHECK_PNG} >> ffmpeg_debug.txt 2>&1
            local VID_RGB=$(convert ${CHECK_PNG} -crop 1x1+960+540 -depth ${BIT_DEPTH} -format "%[fx:int(${SCALE}*r+.5)],%[fx:int(${SCALE}*g+.5)],%[fx:int(${SCALE}*b+.5)]" info:-)
            echo -e "${MP4_NAME}\t${CHECK_PNG}\t${VID_RGB}\t${IMG_COLOUR}\t${ENCODE_TIME_SECS}" >> checker/verify.txt
            check_output ${IMG_COLOUR} ${VID_RGB}
        fi
    fi
    echo "file '${MP4_NAME}'" >> ffmpeg_input.txt
}

DRY_RUN=1
EXTRA_SECS=2
BIT_DEPTH=12

while getopts ":ine:s:" opt; do
  case ${opt} in
    n )
      echo "Switching off dry run mode"
      DRY_RUN=0
      ;;
    i )
      echo "Running in incremental mode"
      DRY_RUN=2
      ;;
    e )
      if [[ -n ${OPTARG} ]]
      then
        echo "Adding ${OPTARG}s to duration"
        EXTRA_SECS=${OPTARG}
      fi
      ;;
    s )
      if [[ -n ${OPTARG} ]]
      then
        echo "Verifying in ${OPTARG} bits"
        BIT_DEPTH=${OPTARG}
      fi
      ;;
    \? )
      echo "Invalid option: ${OPTARG}" 1>&2
      ;;
    : )
      echo "Invalid option: ${OPTARG} requires an argument" 1>&2
      ;;
  esac
done
shift "$((OPTIND-1))"

if [[ ! "${EXTRA_SECS}" =~ ^[0-9]+$ ]]
then 
    echo "error: -e must be a number not ${EXTRA_SECS}" >&2
    exit 1 
fi
SCALE=$(echo "2^${BIT_DEPTH} - 1" | bc)

if [[ -n "${1}" ]]
then
    pushd ${1} >/dev/null 2>&1 
fi
if [[ ! -d "input" ]]
then
    echo "error: $(pwd) has no input directory"
fi

mkdir -p HD
mkdir -p checker
mkdir -p MP4

echo "" > ffmpeg_debug.txt
echo -e "mp4\tsample\tactual\texpected\tencode_time" > checker/verify.txt
echo "# mp4 concat $(pwd)" > ffmpeg_input.txt
echo -e "file\trgb" > debug.txt
LAST_IMG_COLOUR=
LAST_FILE_NAME=
IMG_DURATION=0
IMG_COUNT=0
for i in $(find ./input -maxdepth 1 -mindepth 1 -type f -name \*.png |sort)
do
    IMG_COLOUR=$(convert ${i} -crop 1x1+0+0 -depth ${BIT_DEPTH} -format "%[fx:int(${SCALE}*r+.5)],%[fx:int(${SCALE}*g+.5)],%[fx:int(${SCALE}*b+.5)]" info:- )
    if [[ -n ${LAST_IMG_COLOUR} ]] && [[ ${LAST_IMG_COLOUR} != ${IMG_COLOUR} ]]
    then
        IMG_COUNT=$((IMG_COUNT + 1))
        IMG_DURATION=$((IMG_DURATION + EXTRA_SECS))
        gen ${IMG_COUNT} ${LAST_IMG_COLOUR} ${IMG_DURATION} "${LAST_FILE_NAME}"
        IMG_DURATION=0
    fi
    IMG_DURATION=$((IMG_DURATION + 1))
    LAST_IMG_COLOUR=${IMG_COLOUR}
    LAST_FILE_NAME=${i}
    echo -e "${i}\t${IMG_COLOUR}" >> debug.txt
done

IMG_COUNT=$((IMG_COUNT + 1))
gen ${IMG_COUNT} ${LAST_IMG_COLOUR} ${IMG_DURATION} ${LAST_FILE_NAME}

if [[ ${DRY_RUN} -eq 0 ]]
then
    echo "Concatenating all files into final output"
    ffmpeg -y -f concat -safe 0 -i ffmpeg_input.txt -c copy patterns.mp4  >> ffmpeg_debug.txt 2>&1
fi

if [[ -n "${1}" ]]
then
    popd  >/dev/null 2>&1 
fi
