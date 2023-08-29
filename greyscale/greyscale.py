import os.path
import shlex
import subprocess
import png

from colour.models import eotf_inverse_ST2084


def encode(cmd: str, file_1: str, file_60: str):
    if not os.path.exists(file_1):
        print(f'Writing {file_1}')
        print(cmd)
        shlex.split(cmd)
        subprocess.run(shlex.split(cmd), check=True)

    if not os.path.exists(file_60):
        cmd = f"ffmpeg -y -stream_loop 60 -i {file_1} -c copy -map_chapters -1 {file_60}"
        print(f'Writing {file_60}')
        print(cmd)
        shlex.split(cmd)
        subprocess.run(shlex.split(cmd), check=True)


w = 3840
h = 2160

scale = 16
steps = 100
abs_max_nits = 10000
max_nits = 1000
abs_s_max = eotf_inverse_ST2084(abs_max_nits)
s_max = eotf_inverse_ST2084(max_nits)

rgb_max_value = (2 ** scale) - 1
max_value = int(rgb_max_value * s_max)
pixels = []

cols = list(range(0, steps + 1))
rows = 1

panel_width = int(w / len(cols))
width_padding = w - (panel_width * len(cols))

row = []
for patch_num in cols:
    pq_val = s_max / 100 * patch_num
    multiplier = rgb_max_value
    rgb_value = int(pq_val * multiplier)
    print(f'{patch_num},{rgb_value},{pq_val:.6g}')
    rgb_triplet = [rgb_value] * 3
    column_width = panel_width + (0 if patch_num != len(cols) - 1 else width_padding)
    pixels = rgb_triplet * column_width
    row.extend(pixels)
pixels = [row for _ in range(h)]

# one line version
# row = [v for g in cols for v in
#        [0 if g == 0 else int((g / 100) * max_value)] * 3 * (panel_width + (0 if g != len(cols) - 1 else width_padding))]

ramp_file = f'greyscale_{steps}_{max_nits}.png'

if not os.path.exists(ramp_file):
    print(f'Writing {ramp_file}')
    with open(ramp_file, 'wb') as f:
        w = png.Writer(w, h, greyscale=False, bitdepth=scale)
        w.write(f, pixels)

x265_params = "crf=12:colorprim=bt2020:transfer=smpte2084:colormatrix=bt2020nc:master-display=\"G(13250,34500)B(7500,3000)R(34000,16000)WP(15635,16450)L(10000000,1)\":max-cll=\"1000,400\""
vf_params = f"scale=out_color_matrix=bt2020:out_h_chr_pos=0:out_v_chr_pos=0,format=yuv420p10,loop=-1:1"
hdr_file_1 = f'greyscale_{steps}_{max_nits}_1.mkv'
cmd = f"ffmpeg -y -framerate 24000/1001 -i {ramp_file} -c:v libx265 -x265-params \"{x265_params}\" -t 1 -vf \"{vf_params}\" {hdr_file_1}"

encode(cmd, hdr_file_1,f'greyscale_{steps}_{max_nits}.mkv')

sdr_file_1 = f'greyscale_{steps}_{max_nits}_sdr_1.mkv'
cmd = f"ffmpeg -y -framerate 24000/1001 -i {ramp_file} -c:v libx265 -x265-params \"lossless=1\" -t 1 -vf \"colorspace=all=bt709:iall=bt601-6-625:fast=1:format=yuv420p10,loop=-1:1\" -colorspace 1 -color_primaries 1 -color_trc 1 -sws_flags accurate_rnd+full_chroma_int {sdr_file_1}"

encode(cmd, sdr_file_1,f'greyscale_{steps}_{max_nits}_sdr.mkv')

