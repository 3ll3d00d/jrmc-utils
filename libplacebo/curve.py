from matplotlib import pyplot as plt
import numpy as np
from colour.models import eotf_inverse_ST2084, eotf_ST2084

s_contrast = 0.5

contrast_ratio = 30000
d_max_nits = 100
d_min_nits = d_max_nits / contrast_ratio

s_max_nits = 1000

s_min = 0.0
s_avg = 0.3
s_max = eotf_inverse_ST2084(s_max_nits)

d_max = eotf_inverse_ST2084(d_max_nits)
d_min = eotf_inverse_ST2084(d_min_nits)

k_adaptation = 0.7
k_min = 0.1
k_max = 0.8

t_strength = 1.5
t_offset = 0.2

t_knee = max(min(((s_avg - s_min) / (s_max - s_min)), k_max), k_min)
s_knee = t_knee * (s_max - s_min) + s_min

d_pre = t_knee * (d_max - d_min) + d_min
d_kmin = k_min * d_max + (1 - k_min) * d_min
d_kmax = k_max * d_max + (1 - k_max) * d_min

d_knee = k_adaptation * d_pre + (1 - k_adaptation) * s_knee

m_slope = (d_knee - d_min) / (s_knee - s_min)

r = s_max / d_max - 1
r_tuned = min(max(t_strength * r, t_offset), t_offset + 1)

g_slope = 1 - s_contrast

m = m_slope ** (g_slope * r_tuned)

i_min = s_min - s_knee
i_max = s_max - s_knee

o_min = d_min - d_knee
o_max = d_max - d_knee

p_a = (o_min - (m * i_min)) / (i_min * i_min)
p_b = m

t = 2 * i_max * i_max

q_a = (m * i_max - o_max) / (i_max * t)
q_b = -3 * ((m * i_max - o_max) / t)
q_c = m

upper_range = np.arange(s_knee, s_max + 0.001, 0.001)
upper_delta = upper_range - s_knee
d_upper_1 = q_a * (upper_delta ** 3)
d_upper_2 = q_b * (upper_delta ** 2)
d_upper_3 = q_c * upper_delta
d_upper = d_upper_1 + d_upper_2 + d_upper_3 + d_knee

lower_range = np.arange(s_min, s_knee, 0.001)
lower_delta = lower_range - s_knee
d_lower_1 = p_a * (lower_delta ** 2)
d_lower_2 = p_b * lower_delta
d_lower = d_lower_1 + d_lower_2 + d_knee

input_signal = np.concatenate((lower_range, upper_range))
output_signal = np.concatenate((d_lower, d_upper))

input_min = 0.0
input_max = 0.8

input_pq = eotf_inverse_ST2084(np.arange(0, 1, 0.001))
input_nits_min = eotf_ST2084(input_min)
input_nits_max = eotf_ST2084(input_max)