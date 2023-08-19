import colour
import numpy as np

bd = 10
d = (2 ** bd) - 1
rgb = np.array((235 * 4, 16 * 4, 16 * 4))
rgb_in = rgb / d

cs = colour.models.RGB_COLOURSPACE_DISPLAY_P3
os = colour.models.RGB_COLOURSPACE_BT2020

rgb_out = colour.RGB_to_RGB(rgb_in,
                            cs,
                            os,
                            'Bradford',
                            apply_cctf_decoding=True,
                            apply_cctf_encoding=True)
print(f'out {np.round(rgb)}')
print(f'out {np.round(rgb_out * (d + 1))}')
