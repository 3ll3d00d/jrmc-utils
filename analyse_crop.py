import csv
import sys
from collections import defaultdict
from pathlib import Path

from mediaserver import MediaServer

if __name__ == '__main__':
    mc = MediaServer(sys.argv[1], (sys.argv[2], sys.argv[3]))
    lib_p = sys.argv[4]
    real_p = sys.argv[5]
    fields = 'Filename (path),Filename (name),Name'
    results = mc.search('[Dimensions]=[1920 x 1080],[3840 x 2160] -[Video Crop]=[],[0x0x0x0]', fields)
    out_cols = 'name,limit,skip,ffmpeg_crop,mc_crop'
    print(out_cols)
    out_data = []
    for res in results:
        res['Filename (path)'] = res['Filename (path)'].replace(lib_p, real_p).replace('\\', '/')

        crops = [p for p in Path(res['Filename (path)']).glob('crop*.csv')]
        if not crops:
            continue

        for crop in crops:
            t = crop.name[:-4].split('_')
            limit = t[1]
            skip = t[2]
            with crop.open(mode='r') as f:
                unique_crop_counts = defaultdict(int)
                mc_crop = None
                for i, r in enumerate(csv.reader(f)):
                    if i == 0:
                        cols = {c: i for i, c in enumerate(r)}
                    else:
                        unique_crop_counts[r[cols['crop']]] = unique_crop_counts[r[cols['crop']]] + 1
                        if not mc_crop:
                            mc_crop = r[cols['mc_crop']]
                popular_crops = sorted(unique_crop_counts.items(), key=lambda x: x[1], reverse=True)
                if popular_crops:
                    out_data.append([res["Name"], limit, skip, popular_crops[0][0], mc_crop])
                    print(','.join(out_data[-1]))
                else:
                    print(f"No Crops in {crop}")

        with (Path(real_p) / 'crop_analysis.csv').open(mode='w') as f:
            csvf = csv.writer(f)
            csvf.writerow(out_cols.split(','))
            csvf.writerows(out_data)
