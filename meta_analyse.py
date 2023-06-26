import csv
import sys
from collections import defaultdict
from pathlib import Path

if __name__ == '__main__':
    real_p = sys.argv[1]
    with (Path(real_p) / 'crop_analysis.csv').open(mode='r') as f:
        name = None
        crops = set()
        crops_by_limit = defaultdict(set)
        crops_by_skip = defaultdict(set)
        for i, r in enumerate(csv.reader(f)):
            if i == 0:
                continue
            n = r[0]
            if n != name:
                if name:
                    for k, c in crops_by_limit.items():
                        if len(c) > 1:
                            print(f'SKIP {name}')
                            break
                    for k, c in crops_by_skip.items():
                        if len(c) > 1:
                            print(f'LIMIT {name}')
                            break
                    crops = set()
                    crops_by_limit = defaultdict(set)
                    crops_by_skip = defaultdict(set)
                name = n
            crops_by_limit[r[1]].add(r[3])
            crops_by_skip[r[2]].add(r[3])
            crops.add(r[3])
    if len(crops) > 1:
        print(f'SENSITIVE {n}')
