# -*- coding: utf-8 -*-
"""按 总体使用规则.md 第 14 条组装最终成片。

只读 完成分段 里的 mp4，按 补齐生成用/原始帧数.txt 裁到原始帧数后按编号拼接。
标「原片」的段直接用 补齐生成用 里的源片。
交付配乐读取delivery_audio.json；生成输入仍保留原段音轨。
少一段就停，不跳过、不拿别的段补。
"""
import os
import json
import subprocess
import sys
import argparse
from collections import Counter
from audio_delivery import resolve_audio, audio_options, sha256
from quality_review import validate_final

ROOT = os.path.dirname(os.path.abspath(__file__))
CLIPS = os.path.join(ROOT, "完成分段")
SRC = os.path.join(ROOT, "补齐生成用")
TABLE = os.path.join(SRC, "原始帧数.txt")
AUDIO_SETTING = None
AUDIO = None
OUTDIR = os.path.join(CLIPS, "最终组装")
OUT_NAME = "非凡之爱_final_Made-by-wuwukasi.mp4"
# 优先用项目里自带的便携版，没有才退回 PATH
_BIN = os.path.join(ROOT, "ffmpeg")
FFMPEG = os.path.join(_BIN, "ffmpeg.exe")
FFPROBE = os.path.join(_BIN, "ffprobe.exe")
if not (os.path.isfile(FFMPEG) and os.path.isfile(FFPROBE)):
    FFMPEG, FFPROBE = "ffmpeg", "ffprobe"


def source_path(name):
    """补齐生成用 里的源文件带帧数（如 004 56.mp4），按编号前缀找唯一一个。"""
    num = name[:3]
    hits = [f for f in os.listdir(SRC)
            if f.startswith(num + " ") and f.endswith(".mp4")]
    if len(hits) != 1:
        return None
    return os.path.join(SRC, hits[0])


def probe(path, *args):
    r = subprocess.run(
        [FFPROBE, "-v", "error", *args, path],
        capture_output=True, text=True, check=True)
    return r.stdout.strip()


def load_cast():
    """补齐后帧数.txt 第三列；「原片」表示这一段不生成、直接用源片。"""
    path = os.path.join(SRC, "补齐后帧数.txt")
    cast = {}
    if not os.path.isfile(path):
        return cast
    with open(path, encoding="utf-8-sig") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 3 and parts[0].endswith(".mp4"):
                cast[parts[0][:3]] = parts[2].strip()
    return cast


def parse_table():
    rows = []
    with open(TABLE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("合计"):
                continue
            parts = line.split()
            if len(parts) < 2 or not parts[0].endswith(".mp4"):
                continue
            rows.append((parts[0], int(parts[1])))
    return rows


def selected_clip(name, cast):
    manifest_path = os.path.join(ROOT, "制作分析", "delivery_selection.json")
    if os.path.isfile(manifest_path):
        with open(manifest_path, encoding="utf-8") as f:
            selected = json.load(f).get("segments", {}).get(name[:3])
        if selected:
            if selected.get("status") != "static_passed":
                raise SystemExit("候选尚未通过检查：" + name)
            path = os.path.realpath(selected["path"])
            if os.path.normcase(os.path.commonpath([path, ROOT])) != os.path.normcase(ROOT):
                raise SystemExit("候选必须位于本次制作目录：" + name)
            if not selected.get('sha256') or sha256(path)!=selected['sha256']:
                raise SystemExit('候选文件与选片哈希不一致：'+name)
            return path
        raise SystemExit("选片清单缺少已复核段，禁止回退到根目录旧同名片：" + name)
    if cast.get(name[:3]) == "原片":
        return source_path(name)
    raise SystemExit("缺少delivery_selection.json已复核选片清单，不组装：" + name)


def color_filter(name):
    if name[:3]!='019':return ''
    path=os.path.join(ROOT,'delivery_visual.json')
    cfg=json.load(open(path,encoding='utf-8')) if os.path.isfile(path) else {}
    mode=cfg.get('shot019_color')
    if mode=='monochrome':return ',hue=s=0'
    if mode=='generated_verified':return ''
    raise SystemExit('019色彩尚未确认：检查本次参考红配件后设置delivery_visual.json的shot019_color为monochrome或generated_verified。')


def render_homogeneous_once(rows, cast, output):
    """Encode matching24fps inputs once, avoiding a second lossy encode."""
    paths = [selected_clip(name, cast) for name, _ in rows]
    inputs, filters, sizes = [], [], []
    for i, ((name, keep), path) in enumerate(zip(rows, paths)):
        info = json.loads(probe(path, "-select_streams", "v:0", "-count_frames",
                                "-show_streams", "-of", "json"))["streams"][0]
        if info.get("r_frame_rate") != "24/1":
            return False
        width, height = info["width"], info["height"]
        target = (width * 9 // 16) // 2 * 2
        if not 0 <= height - target <= 16:
            return False
        if int(info.get("nb_read_frames") or 0) < keep:
            raise SystemExit("输入帧数不足，不补帧：" + name)
        sizes.append((width, target))
        inputs += ["-threads", "1", "-i", path]
        color = color_filter(name)
        filters.append(f"[{i}:v]trim=end_frame={keep},setpts=PTS-STARTPTS,"
                       f"crop={width}:{target}:0:(ih-oh)/2,setsar=1{color}[v{i}]")
    if len(set(sizes)) != 1:
        return False
    filters.append("".join(f"[v{i}]" for i in range(len(rows))) +
                   f"concat=n={len(rows)}:v=1:a=0[vout]")
    with open(os.path.join(ROOT, "LICENSE.txt"), encoding="utf-8") as f:
        license_text = f.read().strip()
    metadata = ["-metadata", "title=非凡之爱_final (Made by wuwukasi)",
                "-metadata", "artist=wuwukasi", "-metadata", "comment=Made by wuwukasi",
                "-metadata", "copyright=Made by wuwukasi",
                "-metadata", "description=" + license_text]
    audio_inputs, audio_codec = audio_options(FFPROBE, AUDIO_SETTING, sum(k for _, k in rows)/24)
    subprocess.run([FFMPEG, "-v", "error", "-n", *inputs, *audio_inputs,
                    "-filter_complex_threads", "2", "-filter_complex", ";".join(filters),
                    "-map", "[vout]", "-map", f"{len(rows)}:a:0", "-map_metadata", "-1",
                    "-c:v", "libx264", "-crf", "10", "-pix_fmt", "yuv420p",
                    "-r", "24", "-threads", "8", *audio_codec,
                    "-t", f"{sum(k for _, k in rows)/24:.9f}", "-movflags", "+faststart",
                    *metadata, output], check=True)
    print(f"wrote {output} (1417 frames,24fps,one encode,selected delivery music)", flush=True)
    return True


def main():
    global AUDIO_SETTING, AUDIO
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only', action='store_true', help='仅验证选片、问题和联合复核记录，不合片。')
    args = parser.parse_args()
    rows = parse_table()
    issues_path = os.path.join(ROOT, "制作分析", "issues.json")
    if os.path.isfile(issues_path):
        with open(issues_path, encoding="utf-8") as f:
            issues = json.load(f)
        unresolved = [n for n, issue in issues.items()
                      if n.isdigit() and issue.get("status") != "resolved"]
        if unresolved:
            raise SystemExit("已知问题尚未修复并选片，不合片：" + ", ".join(unresolved))
    manifest_path = os.path.join(ROOT, '制作分析', 'delivery_selection.json')
    if not os.path.isfile(manifest_path):
        raise SystemExit('缺少正式选片清单，不合片。')
    try:
        with open(manifest_path, encoding='utf-8') as f:
            validate_final(ROOT, rows, json.load(f))
    except (ValueError, OSError) as e:
        raise SystemExit(str(e))
    if args.check_only:
        print('正式选片与联合复核记录通过；未启动编码或生成。', flush=True)
        return
    AUDIO_SETTING = resolve_audio(ROOT)
    AUDIO = AUDIO_SETTING['path']
    cast = load_cast()
    missing = []
    for name, _ in rows:
        path = selected_clip(name, cast)
        if not path or not os.path.isfile(path):
            missing.append(name)
    if missing:
        print("停：完成分段里缺这些文件，不组装：")
        for n in missing:
            print(" ", n)
        sys.exit(1)
    if not os.path.isfile(AUDIO):
        print(f"停：缺少原片音轨 {AUDIO}")
        sys.exit(1)

    os.makedirs(OUTDIR, exist_ok=True)
    if os.path.exists(os.path.join(OUTDIR, OUT_NAME)):
        raise SystemExit("成片已存在；先保存历史版本再制作新版本，禁止静默覆盖。")
    if render_homogeneous_once(rows, cast, os.path.join(OUTDIR, OUT_NAME)):
        return
    work = os.path.join(OUTDIR, "_work")
    os.makedirs(work, exist_ok=True)

    sizes = []
    trimmed = []
    for name, keep in rows:
        src = selected_clip(name, cast)
        frames = int(probe(src, "-select_streams", "v:0",
                           "-count_frames", "-show_entries",
                           "stream=nb_read_frames", "-of", "csv=p=0"))
        if frames < keep:
            print(f"停：{name} 实际 {frames} 帧，少于原始帧数 {keep}，不补帧。")
            sys.exit(1)
        fps = probe(src, "-select_streams", "v:0",
                    "-show_entries", "stream=r_frame_rate", "-of", "csv=p=0")
        dest = os.path.join(work, name)
        width, height = map(int, probe(src, "-select_streams", "v:0",
                    "-show_entries", "stream=width,height", "-of", "csv=p=0").split(","))
        target_height = (width * 9 // 16) // 2 * 2
        filters = f"trim=end_frame={keep},setpts=PTS-STARTPTS"
        # The workflow rounds its 16:9 result to codec-aligned 1920x1088.
        # Remove only those extra border lines, never distort facial geometry.
        if 0 < height - target_height <= 16:
            filters += f",crop={width}:{target_height}:0:(ih-oh)/2,setsar=1"
        filters += color_filter(name)
        subprocess.run([
            FFMPEG, "-y", "-i", src,
            "-vf", filters,
            "-an", "-c:v", "libx264", "-crf", "10", "-pix_fmt", "yuv420p",
            "-r", fps, dest
        ], check=True, capture_output=True)
        w, h = probe(dest, "-select_streams", "v:0",
                     "-show_entries", "stream=width,height",
                     "-of", "csv=p=0").split(",")
        sizes.append((int(w), int(h)))
        trimmed.append(dest)
        print(f"trim {name} -> {keep} frames {w}x{h}", flush=True)

    (tw, th), n = Counter(sizes).most_common(1)[0]
    print(f"majority size {tw}x{th} ({n}/{len(sizes)})", flush=True)

    scaled = []
    for src, size in zip(trimmed, sizes):
        if size == (tw, th):
            scaled.append(src)
            continue
        dest = src.replace(".mp4", "_s.mp4")
        subprocess.run([
            FFMPEG, "-y", "-i", src,
            "-vf", f"scale={tw}:{th}:flags=lanczos",
            "-an", "-c:v", "libx264", "-crf", "10", "-pix_fmt", "yuv420p",
            dest
        ], check=True, capture_output=True)
        scaled.append(dest)
        print(f"scale {os.path.basename(src)} {size[0]}x{size[1]} -> {tw}x{th}",
              flush=True)

    concat = os.path.join(work, "concat.txt")
    with open(concat, "w", encoding="utf-8") as f:
        for p in scaled:
            f.write("file '" + p.replace("\\", "/") + "'\n")
    silent = os.path.join(work, "silent.mp4")
    subprocess.run([
        FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", concat,
        "-c:v", "libx264", "-crf", "10", "-pix_fmt", "yuv420p",
        "-an", silent
    ], check=True, capture_output=True)

    # 分段按 24fps 生成；如果原片帧率不同，重新计时到原片帧率，不增帧、不减帧。
    target_fps = "24/1"
    cur_fps = probe(silent, "-select_streams", "v:0",
                    "-show_entries", "stream=r_frame_rate", "-of", "csv=p=0")

    def fps_value(rate):
        num, den = rate.split("/")
        return float(num) / float(den)

    factor = fps_value(cur_fps) / fps_value(target_fps)
    if abs(factor - 1.0) > 1e-6:
        timed = os.path.join(work, "silent_timed.mp4")
        subprocess.run([
            FFMPEG, "-y", "-i", silent,
            "-vf", f"setpts=PTS*{factor:.9f}",
            "-r", target_fps, "-an",
            "-c:v", "libx264", "-crf", "10", "-pix_fmt", "yuv420p",
            timed
        ], check=True, capture_output=True)
        silent = timed
        print(f"retime {cur_fps} -> {target_fps} (x{factor:.6f})", flush=True)

    dur = float(probe(silent, "-show_entries", "format=duration", "-of", "csv=p=0"))
    out = os.path.join(OUTDIR, OUT_NAME)
    # LICENSE.txt 全文写进文件 metadata（description），只在文件内部，不显示在画面上
    lic_path = os.path.join(ROOT, "LICENSE.txt")
    lic_text = ""
    if os.path.isfile(lic_path):
        with open(lic_path, encoding="utf-8") as f:
            lic_text = f.read().strip()
    meta = [
        "-metadata", "title=非凡之爱_final (Made by wuwukasi)",
        "-metadata", "artist=wuwukasi",
        "-metadata", "comment=Made by wuwukasi",
        "-metadata", "copyright=Made by wuwukasi",
    ]
    if lic_text:
        meta += ["-metadata", "description=" + lic_text]
    audio_inputs, audio_codec = audio_options(FFPROBE, AUDIO_SETTING, dur)
    subprocess.run([
        FFMPEG, "-y", "-i", silent, *audio_inputs,
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "copy", *audio_codec, "-movflags", "+faststart",
        *meta,
        "-t", f"{dur:.6f}",
        out
    ], check=True, capture_output=True)
    print(f"wrote {out} ({dur:.3f}s)", flush=True)


if __name__ == "__main__":
    main()
