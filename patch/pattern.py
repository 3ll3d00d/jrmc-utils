w = 1920
h = 1080

import csv

import png

patchlist = []
pixels = []

with open("/home/matt/Downloads/PriSec_2020_P32020_2.csv") as csv_file:
    reader = csv.reader(csv_file)
    for row_num, row in enumerate(reader):
        d = row[1:]


        def chunk():
            for i in range(0, len(d), 3):
                yield d[i:i + 3]


        patchlist.append(list(chunk()))

cols = len(patchlist[0])
rows = len(patchlist)

panel_width = int(w / cols)
width_padding = w - (panel_width * cols)

panel_height = int(h / rows)
height_padding = h - (panel_height * rows)

for row_num, row in enumerate(patchlist):
    row_data = ()
    for col_num, column in enumerate(row):
        d = (tuple([int(c) for c in column]) * (panel_width + (width_padding if col_num == 0 else 0)))
        row_data += d
    for i in range(panel_height + (height_padding if row_num == 0 else 0)):
        pixels.append(row_data)

with open('chart.png', 'wb') as f:
    w = png.Writer(w, h, greyscale=False)
    w.write(f, pixels)
