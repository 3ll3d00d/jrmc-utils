import csv
import logging
import os
import shlex
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from mediaserver import MediaServer

logging.basicConfig()
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


def run_it(name: str, cmd: str, **kwargs) -> subprocess.CompletedProcess[str]:
    logger.debug(f'Executing {cmd}')
    try:
        return subprocess.check_output(shlex.split(cmd), **kwargs)
    except subprocess.CalledProcessError as e:
        logger.exception(f'{name} failed')
        raise e
    except Exception as e:
        logger.exception(f'{name} Unexpected failure')
        raise e


def find_largest(res):
    sz = 0
    fn = None
    with os.scandir(str((Path(res['Filename (path)']) / 'STREAM').absolute())) as it:
        for f in it:
            if f.is_file() and f.name.endswith('m2ts'):
                f_sz = f.stat().st_size
                if f_sz > sz:
                    sz = f_sz
                    fn = f
    return sz, fn


def crop(res, skip, limit):
    crop_info = []
    for i in [5, 12, 22, 38, 42]:
        pad_i = f'0{i}' if i < 10 else i
        lines = run_it('cropdetect',
                       f'ffmpeg -ss 00:{pad_i}:00 -t 2 -i "{fn.path}" -vf cropdetect=skip={skip}:limit={limit/255} -f null -',
                       stderr=subprocess.STDOUT).decode().split('\n')
        crops = [l.split(' ') for l in lines if 'crop' in l]
        if crops:
            for c in crops:
                ts = float(c[-3][2:]) + (i * 60)
                crop = [int(i) for i in c[-1][5:].split(':')]
                crop_info.append({
                    'ts': ts,
                    'w': crop[0],
                    'h': crop[1],
                    'x': crop[2],
                    'y': crop[3],
                    'crop': f'{crop[2]}x{crop[3]}x{crop[2] + crop[0]}x{crop[3] + crop[1]}',
                    'ar': f'{crop[0] / crop[1]:.2f}' if crop[1] else '0'
                })
        else:
            logger.warning(f'[{res["Name"]}] No crop info found in {fn.path} at 00:{pad_i}:00')
    return crop_info


def dump_output(crop_info, res, output_file):
    all_match = True
    with output_file.open(mode='w') as f:
        csvf = csv.writer(f)
        csvf.writerow('key,name,imdbid,ts,w,h,x,y,crop,ar,mc_crop,mc_ar,match'.split(','))
        for c in crop_info:
            matches = c['crop'] == res['Video Crop']
            if not matches:
                all_match = False
            csvf.writerow(
                [res['Key'], res["Name"], res.get("IMDb ID", ''), c['ts'], c['w'],
                 c['h'], c['x'], c['y'], c['crop'], c['ar'], res['Video Crop'], res['Aspect Ratio'],
                 matches]
            )
    if all_match:
        logger.info(f'[{res["Name"]}] matches!')
    else:
        logger.error(f'[{res["Name"]}] MISMATCH!')


if __name__ == '__main__':
    mc = MediaServer(sys.argv[1], (sys.argv[2], sys.argv[3]))
    lib_p = sys.argv[4]
    real_p = sys.argv[5]
    fields = 'File Type,Filename (path),Filename (name),Video Crop,Aspect Ratio,Dimensions,CropAR,Name,IMDb ID,Duration'
    results = mc.search('[Dimensions]=[1920 x 1080],[3840 x 2160] -[Video Crop]=[],[0x0x0x0]', fields)
    skips = [24, 8]
    limits = [18, 25]
    min_mtime = float(datetime(2023, 6, 26, 16, 0, 0).strftime('%s'))

    for res in results:
        if 'Aspect Ratio' not in res:
            logger.info(f'Ignoring {res}')
            continue

        res['Filename (path)'] = res['Filename (path)'].replace(lib_p, real_p).replace('\\', '/')

        for skip in skips:
            for limit in limits:
                output_file = Path(res['Filename (path)']) / f'crop_{limit}_{skip}.csv'
                if output_file.exists():
                    mtime = output_file.stat().st_mtime
                    delta = mtime - min_mtime
                    if delta > 0:
                        logger.info(f'Skipping {res["Filename (path)"]}, recent crop data already present')
                        continue
                    else:
                        logger.info(f'Overwriting {output_file}, last modified at {datetime.fromtimestamp(mtime).strftime("%c")}')

                try:
                    if res['File Type'] == 'bdmv':
                        sz, fn = find_largest(res)
                        if fn:
                            logger.info(f'[{res["Name"]}] Largest file is {fn.path}')
                            crop_info = crop(res, skip, limit)
                            if crop_info:
                                dump_output(crop_info, res, output_file)
                            else:
                                logger.warning(f'[{res["Name"]}] No crop info found in any segment')
                        else:
                            logger.error(f'[{res["Name"]}] No files found')
                except:
                    logger.exception(f'[{res["Name"]} Unexpected failure')

    logger.info(f'Processed {len(results)} tracks')
