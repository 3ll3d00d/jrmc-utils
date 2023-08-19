import csv
import sys
from pathlib import Path

from mediaserver import MediaServer

if __name__ == '__main__':
    mc = MediaServer(sys.argv[1], (sys.argv[2], sys.argv[3]))
    lib_p = sys.argv[4]
    real_p = sys.argv[5]
    fields = 'Filename (path),Filename (name),Name,Dimensions,Year,Video Crop'
    results = mc.search('[Dimensions]=[1920 x 1080],[3840 x 2160] -[Video Crop]=[],[0x0x0x0]', fields)

    in_file = Path(real_p) / 'crop_analysis.csv'
    out_file = Path(real_p) / 'crop_analysis_28.csv'

    with in_file.open(mode='r') as f1:
        with out_file.open(mode='w') as f2:
            csvf = csv.writer(f2)
            idx = -1
            for i, r in enumerate(csv.reader(f1)):
                if i == 0:
                    idx = r.index('mc_crop')
                else:
                    match = next((res for res in results if res.get('Name', '') == r[0] and res.get('Dimensions', '') == r[1]),
                                 None)
                    if match:
                        r[idx] = match['Video Crop']
                    else:
                        print(f'Failed to find {r[0]}')
                csvf.writerow(r)
