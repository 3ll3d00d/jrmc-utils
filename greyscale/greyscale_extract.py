import os
import shlex
import subprocess

import pandas as pd

bn = '/media/home-media/docs/calibration/tonemapping/greyscale/greyscale_'
steps = 100
width = 3840
height = 2160

panel_width = int(width / steps)
y = int(height / 4)
pngs = ['jrvr_spline0', 'jrvr_spline0.2', 'jrvr_spline0.5', 'jrvr_spline1.0', 'jrvr_spline1.5', 'madvr', 'madvr_sdr',
        'jrvr_sdr', 'jrvr_spline0.5_contrast0.5', 'jrvr_spline0.5_contrast1.0', 'jrvr_spline0.5_contrast20k',
        'jrvr_spline0.5_nits200', 'jrvr_spline0.5_peak1000', 'madvr_peak1000', 'jrvr_spline0.5_peak100',
        'madvr_peak100', 'jrvr_spline0.5_peak1000_3dlut_g24', 'jrvr_spline0.5_peak1000_3dlut_g22',
        'jrvr_spline0.5_peak1000_3dlut_bt1886', 'jrvr_spline0.5_peak1000_3dlut_none']
pngs = [
    # 'jrvr_spline0.5_peak1000_3dlut_bt1886',
    # 'jrvr_spline0.5_peak1000_3dlut_g22',
    # 'jrvr_spline0.5_peak1000_3dlut_g24',
    'jrvr_spline0.5_peak1000_3dlut_none'
]

columns = ['percent', 'r', 'g', 'b', 'avg', 'x_pos']
for spline in pngs:
    pkl = f'{bn}{spline}.pkl'
    # if os.path.exists(pkl):
    #     print(f'{pkl} exists, skipping')
    #     continue
    values = []
    for patch in range(steps + 1):
        v = [patch]
        x = int((panel_width / 2) + int(panel_width * patch))
        cmd = f"convert {bn}{spline}.png -crop '10x{y * 2}+{x - 5}+{y}' -format '%[fx:r],%[fx:g],%[fx:b]' info:-"
        print(f'>>> {patch} {cmd}')
        shlex.split(cmd)
        res = subprocess.run(shlex.split(cmd), check=True, capture_output=True)
        out = res.stdout.decode().splitlines()
        rgb = [float(f) for f in out[0].split(',')]
        v = v + rgb
        v.append(sum(rgb) / len(rgb))
        v.append(x)
        values.append(v)
    print(f'Pickling {pkl}')
    df = pd.DataFrame(data=values, columns=columns)
    df.to_pickle(pkl)
