import argparse
import csv
import logging
import math
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional, List, Tuple

logger = logging.getLogger()

FPS = 25


def as_grey(r: float, g: float, b: float) -> float:
    return round((0.299 * r) + (0.587 * g) + (0.114 * b), 3)


def greyscale_percent(r: float, g: float, b: float) -> Optional[float]:
    return r if math.isclose(r, b) and math.isclose(g, b) else None


def run_if_necessary(out_file: Path, force: bool, func: callable) -> str:
    create = True
    out_file_abs = out_file.absolute()
    if out_file.exists():
        create = force
        if create:
            logger.info(f'Recreating {out_file_abs}')
        else:
            logger.info(f'Reusing {out_file_abs}')
    else:
        logger.info(f'Creating {out_file_abs}')
    if create:
        func(out_file_abs)
        out_file.resolve(strict=True)
    return str(out_file_abs)


def run_it(name: str, cmd: str, **kwargs) -> subprocess.CompletedProcess[str]:
    shlex.split(cmd)
    logger.debug(f'Executing {cmd}')
    try:
        return subprocess.run(shlex.split(cmd), check=True, **kwargs)
    except subprocess.CalledProcessError as e:
        logger.exception(f'{name} failed')
        raise e
    except Exception as e:
        logger.exception(f'{name} Unexpected failure')
        raise e


def chapter_duration(frame_count, fps) -> float:
    return round(frame_count * (1.0 / fps), 3)


def process_patch(idx: int, r: float, g: float, b: float, cache_dir: Path, frame_count: int, force: bool) -> Tuple[str, Tuple[float, ...], str]:
    gamma_percent = greyscale_percent(r, g, b)
    grey = as_grey(r, g, b)

    scale = 100.0
    im_colour = f'{r * scale:.3f}%,{g * scale:.3f}%,{b * scale:.3f}%'

    logger.info(f'Generate patch {idx} : {im_colour}')

    # 10 bit for cache reference
    r_10 = round(r * 1023)
    g_10 = round(g * 1023)
    b_10 = round(b * 1023)
    patch_cache_dir = cache_dir / f'{r_10}_{g_10}_{b_10}'
    patch_cache_dir.mkdir(exist_ok=True)
    patch_file = patch_cache_dir / f'{r_10}_{g_10}_{b_10}.patch.png'
    patch_file_abs = str(patch_file.absolute())

    # create patch
    patch_file_abs = run_if_necessary(patch_file,
                                      force,
                                      lambda f: run_it('Patch generation',
                                                       f'convert -size 1920x1080 xc:rgb\({im_colour}\) PNG48:{f}'))

    # text overlay
    if gamma_percent:
        text_overlay = f'{round(gamma_percent * 100, 1):.4g}%'
    else:
        # 8 bit for text overlay
        r_8 = round(r * 255)
        g_8 = round(g * 255)
        b_8 = round(b * 255)

        text_overlay = f'{r_8},{g_8},{b_8}'

    # text colour
    if grey < 0.5:
        grey = grey + 0.3
    else:
        grey = grey - 0.3
    hex_grey = hex(round(grey * 255))
    text_colour = f'{hex_grey}{hex_grey[2:]}{hex_grey[2:]}'

    # create video
    patch_vid = patch_cache_dir / f'{r_10}_{g_10}_{b_10}.mp4'

    def do_it(f):
        cmd = f"ffmpeg -y -framerate {FPS} -i {patch_file_abs} -c:v libx265 -x265-params \"lossless=1\" -t {chapter_duration(frame_count, FPS)} -vf \"colorspace=all=bt709:iall=bt601-6-625:fast=1:format=yuv420p10,drawtext=text='{text_overlay}':fontcolor={text_colour}:x=40:y=h-th-40:expansion=none:fontsize=36,loop=-1:1\" -colorspace 1 -color_primaries 1 -color_trc 1 -sws_flags accurate_rnd+full_chroma_int {f}"
        before = time.time()
        run_it('MP4 generation', cmd)
        after = time.time()
        logger.info(f'Created {f} in {round(after - before, 3)}s')

    patch_vid_abs = run_if_necessary(patch_vid, force, do_it)

    # convert back to png
    patch_check = patch_cache_dir / f'{r_10}_{g_10}_{b_10}.check.png'
    patch_check_abs = run_if_necessary(patch_check,
                                       force,
                                       lambda f: run_it('Check png generation',
                                                        f'ffmpeg -y -i {patch_vid_abs} -frames:v 1 -vf scale=out_color_matrix=srgb=full_chroma_int+accurate_rnd,format=rgb48le {f}'))

    # read the patch
    res = run_it('Check png parse',
                 f"convert {patch_check_abs} -crop 1x1+960+540 -format '%[fx:r],%[fx:g],%[fx:b]' info:-",
                 capture_output=True)
    out = res.stdout.decode().splitlines()
    check_rgb = [float(f) for f in out[0].split(',')]

    # validate
    if check_rgb:
        check_r_10 = round(check_rgb[0] * 1023)
        check_g_10 = round(check_rgb[1] * 1023)
        check_b_10 = round(check_rgb[2] * 1023)

        delta_r = check_r_10 - r_10
        delta_g = check_g_10 - g_10
        delta_b = check_b_10 - b_10

        delta_sum = abs(delta_r) + abs(delta_g) + abs(delta_b)

        if delta_sum == 0:
            logger.info(f'RESULT: MATCHED: {r_10},{g_10},{b_10}')
        elif delta_sum < 4:
            logger.info(f'RESULT: ROUNDING {delta_sum}: {check_r_10},{r_10},{check_g_10},{g_10},{check_b_10},{b_10}')
        else:
            logger.warning(f'RESULT: ERROR {delta_sum}: {check_r_10},{r_10},{check_g_10},{g_10},{check_b_10},{b_10}')
        return patch_vid_abs, (r_10, g_10, b_10, check_r_10, check_g_10, check_b_10, delta_sum), text_overlay
    else:
        raise ValueError(f'Failed to read RGB from {patch_check_abs}')


def generate_pattern(patchset: str, path: Path, vids: List[str], cache_dir: Path, chapters: List[str]):
    # create the ffmpeg concat
    ffmpeg_concat = path / 'ffmpeg_input.txt'
    is_verify = path.parent.name == 'verify'
    white = str((cache_dir / '1023_1023_1023/1023_1023_1023.mp4').absolute())
    white_patches = 4 if vids[0] != white else 3
    with ffmpeg_concat.open('w') as f:
        if is_verify:
            for _ in range(white_patches):
                f.write(f"file '{white}'\n")
        for vid in vids:
            f.write(f"file '{vid}'\n")
    # create the metadata
    ffmpeg_meta = path / 'ffmpeg_meta.txt'
    with ffmpeg_meta.open('w') as f:
        f.write(';FFMETADATA1')
        f.write(f'title={patchset}')
        f.write('artist=mk')
        for c in chapters:
            f.write(f'{c}\n')
    # create the vid
    patchset_vid = (path / f'{patchset}.mp4').absolute()
    logger.info(f'Concatenating {len(vids)} patches into {patchset_vid}')
    run_it('Pattern gen', f'ffmpeg -y -f concat -safe 0 -i {ffmpeg_concat.absolute()} -i {ffmpeg_meta.absolute()} -map_metadata 1 -c copy {patchset_vid}')


def process_patchset(patchset_path: str, cachedir: str, frame_count: int, force: bool):
    logger.info(f'Processing patchset: {patchset_path}')
    path = Path(patchset_path)
    cache_dir = Path(cachedir)
    set_name = path.parts[-1]
    patch_def_name = f'{set_name}_100.csv'
    patch_def_file = path / patch_def_name
    patch_def_file.resolve(strict=True)
    failed: List[int] = []
    success = 0
    vids: List[str] = []
    rgbs: List[Tuple[float, ...]] = []
    chapters: List[str] = []
    with patch_def_file.open() as f:
        patch_reader = csv.reader(f)
        for row in patch_reader:
            idx = int(row[0])
            r = float(row[1]) / 100.0
            g = float(row[2]) / 100.0
            b = float(row[3]) / 100.0
            try:
                vid, rgb, txt_overlay = process_patch(idx, r, g, b, cache_dir, frame_count, force)
                vids.append(vid)
                rgbs.append(rgb)
                chapters.append('[CHAPTER]')
                chapters.append('TIMEBASE=1/1000')
                chapters.append(f'START={success * (chapter_duration(frame_count, FPS) * 1000):.0f}')
                success = success + 1
                chapters.append(f'END={(success * (chapter_duration(frame_count, FPS) * 1000)) - 1:.0f}')
                chapters.append(f'title={success} - {txt_overlay}')
                chapters.append('')
            except:
                failed.append(idx)

    if failed:
        raise ValueError(f'Failed to generate {len(failed)} mp4, {success} completed ok [{failed}]')
    else:
        with (path / 'verify.csv').open(mode='w') as f:
            v_csv = csv.writer(f)
            v_csv.writerow(['idx', 'in_r', 'in_g', 'in_b', 'out_r', 'out_g', 'out_b', 'delta'])
            for i, rgb in enumerate(rgbs):
                v_csv.writerow([i] + list(rgb))

        generate_pattern(set_name, path, vids, cache_dir, chapters)
        logger.info(f'Processed patchset: {patchset_path}')


if __name__ == '__main__':
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    parser = argparse.ArgumentParser(prog='gen_pattern',
                                     description='Generates test pattern video to allow DisplayCAL to drive test patterns through JRiver Media Center')
    parser.add_argument('patchsets', nargs='+',
                        help='List of directory names containing defined patchsets, must minimally contain a <patchset>_100.csv file')
    parser.add_argument('-c', '--cache-dir', help='Generated patch cache directory, default is relative to cwd',
                        default='cache')
    parser.add_argument('-fps', help='No of frames to include in the final output', default=5, type=int)
    parser.add_argument('-f', '--force', help='Overwrite files even if they exist', default=False, type=bool)

    args = parser.parse_args()

    failed = []
    for ps in args.patchsets:
        try:
            process_patchset(ps, args.cache_dir, args.fps, args.force)
        except:
            logger.exception(f'Patchset failed: {ps}')
            failed.append(ps)
    if failed:
        logger.warning(f'{len(failed)} patch sets failed: {", ".join(failed)}')
        sys.exit(1)
    else:
        sys.exit(0)
