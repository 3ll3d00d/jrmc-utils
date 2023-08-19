import csv
import logging
import os
import shlex
import subprocess
import sys
from pathlib import Path

from mediaserver import MediaServer

if __name__ == '__main__':
    mc = MediaServer(sys.argv[1], (sys.argv[2], sys.argv[3]))
    lib_p = sys.argv[4]
    real_p = sys.argv[5]
    skip = 24
    limit = 18
    fields = 'File Type,Filename (path),Filename (name),Video Crop,Aspect Ratio,Dimensions,CropAR,Name,IMDb ID,Duration'
    results = mc.search('[Dimensions]=[1920 x 1080],[3840 x 2160] -[Video Crop]=[],[0x0x0x0]', fields)
    for res in results:
        if 'Aspect Ratio' not in res:
            continue

        if 'IMDb ID' not in res:
            continue

        res['Filename (path)'] = res['Filename (path)'].replace(lib_p, real_p).replace('\\', '/')

        output_file = Path(res['Filename (path)']) / f'crop_{limit}_{skip}.csv'
        if not output_file.exists():
            continue

        rows = []
        with output_file.open(mode='r') as f:
            for i, r in enumerate(csv.reader(f)):
                if i == 0:
                    continue
                if not r[2]:
                    r[2] = res['IMDb ID']
                rows.append(r)
        with output_file.open(mode='w') as f:
            csvf = csv.writer(f)
            csvf.writerow('key,name,imdbid,ts,w,h,x,y,crop,ar,mc_crop,mc_ar,match'.split(','))
            csvf.writerows(rows)
