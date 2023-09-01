from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image
from colour.models import eotf_ST2084, eotf_inverse_ST2084

files = [
    # (None, '/home/matt/dev/github/3ll3d00d/jrmc-utils/greyscale/greyscale_100_1000.png', 10000),
    # (2.2, '/media/home-media/docs/calibration/tonemapping/greyscale/greyscale_jrvr_spline0.5_peak1000_3dlut_none.png', 1000),
    # (2.2, '/home/matt/Pictures/orient_express.png', 1000),
    (2.2, '/home/matt/Pictures/orient_express_full.png', 1000),
    # (2.2, '/media/home-media/showhorses.png', 1000),
    # (None, '/media/home-media/showhorses.png', 1000),
    # (2.2, '/home/matt/Downloads/adl5.png')
]
data = []
for gamma, f, max_cll in files:
    im = np.array(Image.open(f).convert('RGB'))
    rgb = (im / 255)
    linear_rgb = rgb ** gamma if gamma else rgb
    luminance = np.dot(linear_rgb[..., :3], [0.2126, 0.7152, 0.0722])
    luminance = luminance[luminance > 0]
    nits_luminance = eotf_ST2084(luminance)

    apl = np.mean(luminance) * 100

    fall = np.mean(nits_luminance)
    pq_fall = eotf_ST2084(np.mean(luminance))

    p9995 = np.percentile(nits_luminance, 99.95)

    def estimate_percentile(histo, lim):
        histo_lim = int(luminance.size * (lim / 100))
        histo_cumsum = np.cumsum(histo[0])
        pos = np.argmax(histo_cumsum >= histo_lim)
        lower_bound, upper_bound = histo[1][pos:pos+2]
        bin_size = histo[0][pos]
        bin_width = upper_bound - lower_bound
        bin_pos = (histo_cumsum[pos] - histo_lim) / bin_size
        return bin_width * bin_pos + lower_bound

    def estimate_mean(histo):
        midpoints = (histo[1] + (histo[1][1] - histo[1][0])/2)[:-1]
        fx = histo[0] * midpoints
        return np.sum(fx) / np.sum(histo[0])


    nits_histo = np.histogram(nits_luminance, bins=64)
    estimated_p9995 = estimate_percentile(nits_histo, 99.95)
    est_fall = estimate_mean(nits_histo)

    pq_p9995 = eotf_ST2084(np.percentile(luminance, 99.95))
    pq_histo = np.histogram(luminance, bins=64)
    estimated_pq_p9995 = eotf_ST2084(estimate_percentile(pq_histo, 99.95))
    est_pq_fall = eotf_ST2084(estimate_mean(pq_histo))

    max_nits = np.max(nits_luminance)
    # max_xy = list(reversed(np.unravel_index(luminance.argmax(), luminance.shape)))
    data.append([Path(f).name, np.max(im), apl, fall, est_fall, pq_fall, est_pq_fall, p9995, estimated_p9995, pq_p9995, estimated_pq_p9995, max_nits])

df = pd.DataFrame(data, columns=['Name', 'max(RGB)', 'APL %', 'FALL', 'EST FALL', 'PQ FALL', 'EST PQ FALL', 'P99.95', 'EST P99.95', 'PQ P99.95', 'EST PQ P99.95', 'MAX'])
df