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

import colour
import numpy as np

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


def process_patch(idx: int, r: float, g: float, b: float, cache_dir: Path, frame_count: int, force: bool, hdr: str) -> \
        Tuple[str, Tuple[float, ...], str]:
    gamma_percent = greyscale_percent(r, g, b)
    r_in_10 = round(r * 1023)
    g_in_10 = round(g * 1023)
    b_in_10 = round(b * 1023)

    if hdr and hdr == 'p3':
        cs = colour.models.RGB_COLOURSPACE_DISPLAY_P3
        os = colour.models.RGB_COLOURSPACE_BT2020

        rgb_in = np.array([r, g, b])
        displayp3_in_2020 = colour.RGB_to_RGB(rgb_in,
                                              cs,
                                              os,
                                              'Bradford',
                                              apply_cctf_decoding=True,
                                              apply_cctf_encoding=True)
        r, g, b = displayp3_in_2020
        r_in_10, g_in_10, b_in_10 = np.round(displayp3_in_2020 * 1023)
        logger.info(
            f'Generating patch {idx} using p3 in 2020 {np.round(rgb_in * 1023)} -> {np.round(displayp3_in_2020 * 1023)} ({rgb_in} -> {displayp3_in_2020})')
    else:
        logger.info(f'Generating patch {idx} {r_in_10},{g_in_10},{b_in_10}')

    grey = as_grey(r, g, b)

    scale = 100.0
    im_colour = f'{r * scale:.3f}%,{g * scale:.3f}%,{b * scale:.3f}%'

    logger.info(f'Generate patch {idx} : {im_colour}')

    # 10 bit for cache reference
    patch_cache_dir = cache_dir / f'{r_in_10}_{g_in_10}_{b_in_10}'
    patch_cache_dir.mkdir(exist_ok=True)
    patch_file = patch_cache_dir / f'{r_in_10}_{g_in_10}_{b_in_10}.patch.png'
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
    patch_vid = patch_cache_dir / f'{r_in_10}_{g_in_10}_{b_in_10}.mp4'

    duration = chapter_duration(frame_count, FPS)

    def do_it(f):
        if hdr:
            x265_params = "crf=12:colorprim=bt2020:transfer=smpte2084:colormatrix=bt2020nc:master-display=\"G(13250,34500)B(7500,3000)R(34000,16000)WP(15635,16450)L(10000000,1)\":max-cll=\"1000,400\""
            vf_params = f"scale=out_color_matrix=bt2020:out_h_chr_pos=0:out_v_chr_pos=0,format=yuv420p10,loop=-1:1"
            text_params = f",drawtext=text='{text_overlay}':fontcolor={text_colour}:x=40:y=h-th-40:expansion=none:fontsize=36"
            text_params = ''
            cmd = f"ffmpeg -y -framerate {FPS} -i {patch_file_abs} -c:v libx265 -x265-params \"{x265_params}\" -t {duration} -vf \"{vf_params}{text_params}\" {f}"
        else:
            cmd = f"ffmpeg -y -framerate {FPS} -i {patch_file_abs} -c:v libx265 -x265-params \"lossless=1\" -t {duration} -vf \"colorspace=all=bt709:iall=bt601-6-625:fast=1:format=yuv420p10,drawtext=text='{text_overlay}':fontcolor={text_colour}:x=40:y=h-th-40:expansion=none:fontsize=36,loop=-1:1\" -colorspace 1 -color_primaries 1 -color_trc 1 -sws_flags accurate_rnd+full_chroma_int {f}"
        before = time.time()
        run_it('MP4 generation', cmd)
        after = time.time()
        logger.info(f'Created {f} in {round(after - before, 3)}s')

    patch_vid_abs = run_if_necessary(patch_vid, force, do_it)

    # check duration
    resp = run_it('duration',
                  f"ffprobe -v error -select_streams v:0 -show_entries stream=duration -of default=noprint_wrappers=1:nokey=1 {patch_vid_abs}",
                  capture_output=True)
    d = float(resp.stdout.decode().replace('\n', '').strip())
    if not math.isclose(d, duration):
        logger.error(f"{patch_vid_abs} should be {duration} but is {d}")

    # convert back to png
    patch_check = patch_cache_dir / f'{r_in_10}_{g_in_10}_{b_in_10}.check.png'
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

        delta_r = check_r_10 - r_in_10
        delta_g = check_g_10 - g_in_10
        delta_b = check_b_10 - b_in_10

        delta_sum = abs(delta_r) + abs(delta_g) + abs(delta_b)

        if delta_sum == 0:
            logger.info(f'RESULT: MATCHED: {r_in_10},{g_in_10},{b_in_10}')
        elif delta_sum < 4:
            logger.info(
                f'RESULT: ROUNDING {delta_sum}: {check_r_10},{r_in_10},{check_g_10},{g_in_10},{check_b_10},{b_in_10}')
        else:
            logger.warning(
                f'RESULT: ERROR {delta_sum}: {check_r_10},{r_in_10},{check_g_10},{g_in_10},{check_b_10},{b_in_10}')
        return patch_vid_abs, (r_in_10, g_in_10, b_in_10, check_r_10, check_g_10, check_b_10, delta_sum), text_overlay
    else:
        raise ValueError(f'Failed to read RGB from {patch_check_abs}')


def generate_pattern(patchset: str, path: Path, vids: List[str], chapters: List[str], hdr: str):
    # create the ffmpeg concat
    fn = 'ffmpeg_input'
    if hdr:
        fn = f'{fn}_{hdr}'
    ffmpeg_concat = path / f'{fn}.txt'
    with ffmpeg_concat.open('w') as f:
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
    patchset_vid = (path / f'{patchset}{f"_{hdr}" if hdr else ""}.mp4').absolute()
    logger.info(f'Concatenating {len(vids)} patches into {patchset_vid}')
    run_it('Pattern gen',
           f'ffmpeg -y -f concat -safe 0 -i {ffmpeg_concat.absolute()} -i {ffmpeg_meta.absolute()} -map_chapters 1 -c copy {patchset_vid}')


def do_patch(idx: int, r: float, g: float, b: float, cache_dir: Path, frame_count: int, force: bool, vids: List[str],
             chapters: List[str], rgbs: List[Tuple[float, ...]], success: int, hdr: str) -> bool:
    try:
        vid, rgb, txt_overlay = process_patch(idx, r, g, b, cache_dir, frame_count, force, hdr)
        vids.append(vid)
        rgbs.append(rgb)
        chapters.append('[CHAPTER]')
        chapters.append('TIMEBASE=1/1000')
        chapters.append(f'START={success * (chapter_duration(frame_count, FPS) * 1000):.0f}')
        success = success + 1
        chapters.append(f'END={(success * (chapter_duration(frame_count, FPS) * 1000)) - 1:.0f}')
        chapters.append(f'title={success} - {txt_overlay}')
        chapters.append('')
        return True
    except:
        failed.append(idx)
        return False


def process_patchset(patchset_path: str, cachedir: str, frame_count: int, force: bool, hdr: str):
    logger.info(f'Processing patchset: {patchset_path}')
    path = Path(patchset_path)
    cache_dir = Path(cachedir)
    if hdr:
        cache_dir = cache_dir / hdr
    cache_dir.mkdir(parents=True, exist_ok=True)
    set_name = path.parts[-1]
    patch_def_name = f'{set_name}_100.csv'
    patch_def_file = path / patch_def_name
    patch_def_file.resolve(strict=True)
    failed: List[int] = []
    success = 0
    vids: List[str] = []
    rgbs: List[Tuple[float, ...]] = []
    chapters: List[str] = []
    is_verify = path.parent.name == 'verify'
    with patch_def_file.open() as f:
        patch_reader = csv.reader(f)
        extra_patches = 0
        for row in patch_reader:
            idx = int(row[0])
            r = float(row[1]) / 100.0
            g = float(row[2]) / 100.0
            b = float(row[3]) / 100.0
            is_white = math.isclose(r, 1.0) and math.isclose(g, 1.0) and math.isclose(b, 1.0)
            if idx == 0 and is_verify:
                extra_patches = 3 if is_white else 4
                for i in range(extra_patches):
                    if do_patch(i, 1.0, 1.0, 1.0, cache_dir, frame_count, force, vids, chapters, rgbs, success, hdr):
                        success = success + 1
            if do_patch(idx + extra_patches, r, g, b, cache_dir, frame_count, force, vids, chapters, rgbs, success,
                        hdr):
                success = success + 1

    if failed:
        raise ValueError(f'Failed to generate {len(failed)} mp4, {success} completed ok [{failed}]')
    else:
        fn = 'verify'
        if hdr:
            fn = f'{fn}_{hdr}'
        with (path / f'{fn}.csv').open(mode='w') as f:
            v_csv = csv.writer(f)
            v_csv.writerow(['idx', 'in_r', 'in_g', 'in_b', 'out_r', 'out_g', 'out_b', 'delta'])
            for i, rgb in enumerate(rgbs):
                v_csv.writerow([i] + list(rgb))

        generate_pattern(set_name, path, vids, chapters, hdr)
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
    parser.add_argument('-f', '--force', help='Overwrite files even if they exist', action='store_true')
    parser.add_argument('--hdr',
                        help='Generates patterns with HDR metadata in a HDR colourspace (DisplayP3 or Rec2020)',
                        nargs='?',
                        choices=['p3', '2020'])

    args = parser.parse_args()

    failed = []
    for ps in args.patchsets:
        try:
            process_patchset(ps, args.cache_dir, args.fps, args.force, args.hdr)
        except:
            logger.exception(f'Patchset failed: {ps}')
            failed.append(ps)
    if failed:
        logger.warning(f'{len(failed)} patch sets failed: {", ".join(failed)}')
        sys.exit(1)
    else:
        sys.exit(0)
