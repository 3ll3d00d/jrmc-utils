import csv
import sys
import pandas as pd
from collections import defaultdict
from pathlib import Path

if __name__ == '__main__':
    real_p = sys.argv[1]
    df = pd.read_csv(Path(real_p) / 'crop_analysis.csv')
    df = df.drop(columns=['diff', 'no ffmpeg crop', 'no mc crop', 'no crop'])
    f_crop = df['ffmpeg_crop'].str.split('x', expand=True).astype(int)
    df['ffmpeg_w'] = f_crop[2] - f_crop[0]
    df['ffmpeg_h'] = f_crop[3] - f_crop[1]
    df['ffmpeg_ar'] = df['ffmpeg_w'] / df['ffmpeg_h']
    m_crop = df['mc_crop'].str.split('x', expand=True).astype(int)
    df['mc_w'] = m_crop[2] - m_crop[0]
    df['mc_h'] = m_crop[3] - m_crop[1]
    df['w'] = m_crop[2] + m_crop[0]
    df['h'] = m_crop[3] + m_crop[1]
    df['mc_ar'] = df['mc_w'] / df['mc_h']

    w_tolerance_px = 16
    h_tolerance_px = 16

    df['w_delta'] = (df['ffmpeg_w'] - df['mc_w']).abs()
    df['h_delta'] = (df['ffmpeg_h'] - df['mc_h']).abs()

    df['w_ok'] = df['w_delta'] <= w_tolerance_px
    df['h_ok'] = df['h_delta'] <= h_tolerance_px

    matches = []
    mismatches = []
    sensitive_to = {}
    resolution = {}
    for name, values in df.groupby('name'):
        res = f'{values["w"].iloc[0]}x{values["h"].iloc[0]}'
        resolution[name] = res
        if values['w_ok'].all() == True and values['h_ok'].all() == True:
            matches.append(name)
        else:
            mismatches.append(name)
            unique_crops = values.drop_duplicates(subset='ffmpeg_crop')
            sensitive_to[name] = []
            if len(unique_crops) == 1:
                continue
            if len(unique_crops['limit'].unique()) > 1:
                sensitive_to[name].append('limit')
            if len(unique_crops['skip'].unique()) > 1:
                sensitive_to[name].append('skip')

    print(f'{len(matches)} are ok')
    print(f'{len(mismatches)} are not')

    for i, v in sensitive_to.items():
        print(f'[{resolution[i]}] {i} - {v}')

    limits = len([x for x in sensitive_to.values() if 'limit' in x])
    skips = len([x for x in sensitive_to.values() if 'skip' in x])
    both = len([x for x in sensitive_to.values() if len(x) == 2])
    none = len([x for x in sensitive_to.values() if len(x) == 0])
    print(f'limit: {limits} ')
    print(f'skip: {skips} ')
    print(f'both: {both}')
    print(f'neither: {none}')