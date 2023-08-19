import csv
import sys
from collections import defaultdict
from pathlib import Path

from mediaserver import MediaServer

if __name__ == '__main__':
    mc = MediaServer(sys.argv[1], (sys.argv[2], sys.argv[3]))
    lib_p = sys.argv[4]
    real_p = sys.argv[5]
    fields = 'Filename (path),Filename (name),Name,Dimensions,Year'
    results = mc.search('[Dimensions]=[1920 x 1080],[3840 x 2160] -[Video Crop]=[],[0x0x0x0]', fields)

    def c_name(l, s) -> str:
        return f'{l}_{s}_fcrop'

    # could be read from data but makes for annoying mess in resulting df
    skips = [8, 24]
    limits = [18, 25]
    out_cols = ['name', 'res', 'year', 'mc_crop']
    for skip in skips:
        for limit in limits:
            out_cols.append(c_name(limit, skip))
    out_cols.append('exact')
    out_data = []

    for res in results:
        res['Filename (path)'] = res['Filename (path)'].replace(lib_p, real_p).replace('\\', '/')

        crops = [p for p in Path(res['Filename (path)']).glob('crop*.csv')]
        if not crops:
            continue

        d = [''] * len(out_cols)
        d[0] = res['Name']
        d[1] = res['Dimensions']
        d[2] = str(res.get('Year', 0))
        for crop in crops:
            t = crop.name[:-4].split('_')
            f_crop_name = c_name(t[1],t[2])
            try:
                out_idx = out_cols.index(f_crop_name)
                with crop.open(mode='r') as f:
                    unique_crop_counts = defaultdict(int)
                    mc_crop = None
                    for i, r in enumerate(csv.reader(f)):
                        if i == 0:
                            cols = {c: i for i, c in enumerate(r)}
                        else:
                            unique_crop_counts[r[cols['crop']]] = unique_crop_counts[r[cols['crop']]] + 1
                            if not d[3]:
                                d[3] = r[cols['mc_crop']]
                    popular_crops = sorted(unique_crop_counts.items(), key=lambda x: x[1], reverse=True)
                    if popular_crops:
                        d[out_idx] = popular_crops[0][0]
                    else:
                        print(f"No Crops in {crop}")
            except ValueError:
                print(f'{f_crop_name} is not known, ignoring')
                continue
        d[-1] = str(len(set(d[3:-1])) == 1)
        out_data.append(d)
        print('\t'.join(d))

    with (Path(real_p) / 'crop_analysis.csv').open(mode='w') as f:
        csvf = csv.writer(f)
        csvf.writerow(out_cols)
        csvf.writerows(out_data)
