#!/bin/bash
function gen {
    echo -e "${1}\t${2}\t${3}"
    LFN=$(basename ${3})
    MP4_NAME=MP4/"${LFN%.*}".mp4
    if [[ ${DRY_RUN} -eq 0 ]]
    then
        convert -resize 1920x1080\! "${3}" "PNG48:HD/${LFN}"
        ffmpeg -y -loop 1 -i "HD/${LFN}" -pix_fmt yuv420p10le -c:v libx264 -t ${2} -vf scale=out_color_matrix=bt709:flags=full_chroma_int+accurate_rnd,format=yuv420p "${MP4_NAME}" >> ffmpeg_debug.txt 2>&1
        local CHECK_PNG="checker/${LFN%%.*}.png"
        ffmpeg -y -i "${MP4_NAME}" -frames:v 1  -pix_fmt rgb48le -vf scale=out_color_matrix=srgb=full_chroma_int+accurate_rnd,format=rgb48le ${CHECK_PNG} >> ffmpeg_debug.txt 2>&1
        local VID_RGB=$(convert ${CHECK_PNG} -scale 1x1\! -format '%[fx:int(1023*r+.5)],%[fx:int(1023*g+.5)],%[fx:int(1023*b+.5)]' info:-)
        echo -e "${MP4_NAME}\t${CHECK_PNG}\t${VID_RGB}\t${1}" >> checker/verify.txt
        if [[ ${VID_RGB} != ${1} ]]
        then
            echo -e "WARNING! ${VID_RGB} != ${1}"
        else
            echo "Verified!"
        fi
    fi
    echo "file '${MP4_NAME}'" >> ffmpeg_input.txt
}

DRY_RUN=1
[[ -n ${2} ]] && DRY_RUN=0
pushd ${1} >/dev/null 2>&1 
mkdir -p HD
mkdir -p checker
mkdir -p MP4
echo "" > ffmpeg_debug.txt
echo -e "file\tactual\texpected" > checker/verify.txt
echo "# mp4 concat $(pwd)" > ffmpeg_input.txt
echo -e "file\trgb" > debug.txt
LAST_IMG_COLOUR=
LAST_FILE_NAME=
IMG_DURATION=0
for i in $(find ./input -maxdepth 1 -mindepth 1 -type f -name \*.png |sort)
do
    IMG_COLOUR=$(convert ${i}  -scale 1x1\! -format '%[fx:int(1023*r+.5)],%[fx:int(1023*g+.5)],%[fx:int(1023*b+.5)]' info:- )
    if [[ -n ${LAST_IMG_COLOUR} ]] && [[ ${LAST_IMG_COLOUR} != ${IMG_COLOUR} ]]
    then
        gen ${LAST_IMG_COLOUR} ${IMG_DURATION} "${LAST_FILE_NAME}"
        IMG_DURATION=0
    fi
    IMG_DURATION=$((IMG_DURATION + 1))
    LAST_IMG_COLOUR=${IMG_COLOUR}
    LAST_FILE_NAME=${i}
    echo -e "${i}\t${IMG_COLOUR}" >> debug.txt
done
gen ${LAST_IMG_COLOUR} ${IMG_DURATION} ${LAST_FILE_NAME}

if [[ ${DRY_RUN} -eq 0 ]]
then
    echo "Concatenating all files into final output"
    ffmpeg -y -f concat -safe 0 -i ffmpeg_input.txt -c copy patterns.mp4  >> ffmpeg_debug.txt 2>&1
fi

popd  >/dev/null 2>&1 
