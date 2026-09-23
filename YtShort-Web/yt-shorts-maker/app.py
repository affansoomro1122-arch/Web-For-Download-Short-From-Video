"""
ShortsForge - turn a long YouTube video into multiple 60-90 second vertical Shorts.

Backend: Flask + yt-dlp (download) + ffmpeg (cut + 9:16 conversion).
Run:  python app.py   then open http://127.0.0.1:5000
"""
import io
import os
import re
import shutil
import subprocess
import threading
import time
import uuid
import zipfile
from urllib.parse import urlparse

import imageio_ffmpeg
import yt_dlp
from flask import Flask, abort, jsonify, request, send_file, send_from_directory

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JOBS_DIR = os.path.join(BASE_DIR, "jobs")
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

MIN_LEN_LIMIT = 60      # seconds
MAX_LEN_LIMIT = 90      # seconds
MAX_SOURCE_SECONDS = 3 * 60 * 60   # refuse videos longer than 3 hours
JOB_TTL_SECONDS = 3 * 60 * 60      # delete finished jobs after 3 hours

# YouTube often blocks cloud-server IPs. A cookies.txt exported from a logged-in
# browser gets around that. Set YTDLP_COOKIES_FILE, or drop cookies.txt next to app.py.
COOKIES_FILE = os.environ.get("YTDLP_COOKIES_FILE") or (
    os.path.join(BASE_DIR, "cookies.txt") if os.path.exists(os.path.join(BASE_DIR, "cookies.txt")) else None)

YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com",
                 "music.youtube.com", "youtu.be", "www.youtu.be"}

os.makedirs(JOBS_DIR, exist_ok=True)
app = Flask(__name__, static_folder="static", static_url_path="")

jobs = {}
jobs_lock = threading.Lock()


# --------------------------------------------------------------------------- helpers

def update(job_id, **fields):
    with jobs_lock:
        jobs[job_id].update(fields)


def is_youtube_url(url):
    try:
        host = (urlparse(url).hostname or "").lower()
    except ValueError:
        return False
    return host in YOUTUBE_HOSTS


def safe_name(text, fallback="video"):
    text = re.sub(r"[^\w\s-]", "", text or "", flags=re.UNICODE).strip()
    text = re.sub(r"[\s]+", "_", text)
    return text[:60].strip("_-") or fallback


def fmt_time(sec):
    sec = int(round(sec))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def cleanup_old_jobs():
    now = time.time()
    for name in os.listdir(JOBS_DIR):
        path = os.path.join(JOBS_DIR, name)
        if os.path.isdir(path) and now - os.path.getmtime(path) > JOB_TTL_SECONDS:
            shutil.rmtree(path, ignore_errors=True)
            with jobs_lock:
                jobs.pop(name, None)


def detect_silences(src):
    """Return midpoints (seconds) of silent gaps - natural places to cut."""
    cmd = [FFMPEG, "-hide_banner", "-nostats", "-i", src, "-vn",
           "-af", "silencedetect=noise=-30dB:d=0.35", "-f", "null", "-"]
    proc = subprocess.run(cmd, capture_output=True, text=True, errors="ignore")
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", proc.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", proc.stderr)]
    return [(s + e) / 2 for s, e in zip(starts, ends)]


def plan_segments(duration, min_len, max_len, silences, max_count):
    """Split [0, duration] into clips between min_len and max_len seconds,
    preferring to cut in silent gaps so sentences are not chopped in half."""
    target = (min_len + max_len) / 2
    segments = []
    pos = 0.0
    while duration - pos >= min_len and len(segments) < max_count:
        remaining = duration - pos
        if remaining <= max_len:
            segments.append((pos, duration))
            break
        lo, hi = pos + min_len, pos + max_len
        candidates = [t for t in silences if lo <= t <= hi]
        if candidates:
            cut = min(candidates, key=lambda t: abs(t - (pos + target)))
        else:
            cut = pos + target
        segments.append((pos, cut))
        pos = cut
    return segments


def run_ffmpeg(cmd, job_id, clip_len, base_progress, span):
    """Run ffmpeg while reporting progress into the job."""
    proc = subprocess.Popen(cmd + ["-progress", "pipe:1", "-nostats"],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, errors="ignore")
    stderr_chunks = []
    t = threading.Thread(target=lambda: stderr_chunks.append(proc.stderr.read()), daemon=True)
    t.start()
    for line in proc.stdout:
        if line.startswith("out_time_us=") or line.startswith("out_time_ms="):
            try:
                done = int(line.split("=")[1]) / 1_000_000
            except ValueError:
                continue
            frac = max(0.0, min(1.0, done / clip_len))
            update(job_id, progress=round(base_progress + span * frac, 1))
    proc.wait()
    t.join(timeout=5)
    if proc.returncode != 0:
        tail = "".join(stderr_chunks)[-800:]
        raise RuntimeError(f"ffmpeg failed: {tail}")


FONT_CANDIDATES = [
    os.environ.get("TITLE_FONT_FILE", ""),
    os.path.join(BASE_DIR, "fonts", "title.ttf"),
    "C:/Windows/Fonts/arialbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
]
FONT_FILE = next((f for f in FONT_CANDIDATES if f and os.path.exists(f)), None)


def source_size(src):
    """(width, height) of the first video stream, or (16, 9) if unknown."""
    proc = subprocess.run([FFMPEG, "-hide_banner", "-i", src],
                          capture_output=True, text=True, errors="ignore")
    m = re.search(r"Video:.*?(\d{2,5})x(\d{2,5})", proc.stderr)
    return (int(m.group(1)), int(m.group(2))) if m else (16, 9)


def title_filter(text, width, height, band):
    """drawtext for the 'PART N' label. `band` is the height of the blurred
    strip above the video; the label is centred in it when it fits."""
    if not FONT_FILE:
        return ""
    size = int(width * 0.085)
    pad = int(size * 0.35)
    box_h = size + 2 * pad
    if band >= box_h + 20:
        y = f"({band}-th)/2"                # centre of the top blur strip
    else:
        y = f"{int(height * 0.07)}"         # no room: near the top, over the video
    font = FONT_FILE.replace("\\", "/").replace(":", "\\:")
    return (f",drawtext=fontfile='{font}':text='{text}':fontsize={size}:"
            f"fontcolor=black:box=1:boxcolor=0xFFD400:boxborderw={pad}:"
            f"x=(w-tw)/2:y={y}")


def video_filter(mode, quality, src_size, title=""):
    # 1080 -> 1080x1920, 720 -> 720x1280 (true 9:16 vertical frame)
    width = quality
    height = quality * 16 // 9
    if mode == "crop":
        # Fill the whole 9:16 frame, cropping the sides (centre crop).
        return (f"scale={width}:{height}:force_original_aspect_ratio=increase,"
                f"crop={width}:{height},setsar=1"
                + (title_filter(title, width, height, 0) if title else ""))
    # "blur": full video in the middle on top of a blurred, zoomed copy.
    src_w, src_h = src_size
    fg_h = int(width * src_h / src_w) // 2 * 2
    if fg_h <= height:
        fg_scale, band = f"{width}:{fg_h}", (height - fg_h) // 2
    else:  # source taller than 9:16 - fit by height, no top strip
        fg_scale, band = f"-2:{height}", 0
    return (f"split=2[bg][fg];"
            f"[bg]scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},boxblur=20:2,eq=brightness=-0.08[bgb];"
            f"[fg]scale={fg_scale}[fgs];"
            f"[bgb][fgs]overlay=(W-w)/2:(H-h)/2,setsar=1"
            + (title_filter(title, width, height, band) if title else ""))


# --------------------------------------------------------------------------- worker

def process_job(job_id, url, opts):
    job_dir = os.path.join(JOBS_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)
    try:
        # ---- 1. inspect
        update(job_id, stage="Reading video info...", progress=1)
        base_ydl = {"quiet": True, "no_warnings": True, "noplaylist": True,
                    "ffmpeg_location": FFMPEG, "js_runtimes": {"node": {}, "deno": {}}}
        if COOKIES_FILE:
            base_ydl["cookiefile"] = COOKIES_FILE
        with yt_dlp.YoutubeDL(base_ydl) as ydl:
            info = ydl.extract_info(url, download=False)
        duration = float(info.get("duration") or 0)
        title = info.get("title") or "video"
        update(job_id, title=title, duration=duration,
               thumbnail=info.get("thumbnail"), channel=info.get("uploader") or "")
        if info.get("is_live"):
            raise RuntimeError("Live streams can't be converted. Try again after the stream ends.")
        if duration < opts["min_len"]:
            raise RuntimeError(f"This video is only {fmt_time(duration)} long. "
                               f"It must be at least {opts['min_len']} seconds to make a Short.")
        if duration > MAX_SOURCE_SECONDS:
            raise RuntimeError("Videos longer than 3 hours are not supported.")

        # ---- 2. download
        update(job_id, stage="Downloading video...", progress=3)

        def hook(d):
            if d.get("status") == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                if total:
                    update(job_id, progress=round(3 + 27 * d.get("downloaded_bytes", 0) / total, 1))

        h = opts["height"]
        ydl_opts = dict(base_ydl,
                        format=(f"bv*[height<={h}][ext=mp4]+ba[ext=m4a]/"
                                f"bv*[height<={h}]+ba/b[height<={h}]/b"),
                        merge_output_format="mp4",
                        outtmpl=os.path.join(job_dir, "source.%(ext)s"),
                        progress_hooks=[hook])
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        src = next((os.path.join(job_dir, f) for f in os.listdir(job_dir)
                    if f.startswith("source.") and not f.endswith(".part")), None)
        if not src:
            raise RuntimeError("Download failed - no video file was produced.")

        # ---- 3. find natural cut points
        update(job_id, stage="Finding the best cut points...", progress=31)
        silences = detect_silences(src)
        segments = plan_segments(duration, opts["min_len"], opts["max_len"],
                                 silences, opts["max_count"])
        if not segments:
            raise RuntimeError("Could not split this video into Shorts.")
        update(job_id, total=len(segments))

        # ---- 4. render each short
        base_name = safe_name(title)
        src_dims = source_size(src)
        span_each = 68 / len(segments)
        for i, (start, end) in enumerate(segments, 1):
            clip_len = end - start
            update(job_id, stage=f"Creating short {i} of {len(segments)}...")
            out_name = f"short_{i:02d}.mp4"
            thumb_name = f"short_{i:02d}.jpg"
            out_path = os.path.join(job_dir, out_name)
            vf = video_filter(opts["mode"], opts["height"], src_dims,
                              f"PART {i}" if opts["titles"] else "")
            cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
                   "-ss", f"{start:.3f}", "-i", src, "-t", f"{clip_len:.3f}",
                   "-filter_complex" if opts["mode"] == "blur" else "-vf", vf,
                   "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
                   "-pix_fmt", "yuv420p", "-r", "30",
                   "-c:a", "aac", "-b:a", "160k", "-ar", "44100",
                   "-movflags", "+faststart", out_path]
            run_ffmpeg(cmd, job_id, clip_len, 32 + span_each * (i - 1), span_each)

            subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-ss", "1", "-i", out_path,
                            "-frames:v", "1", "-vf", "scale=360:-2", "-q:v", "4",
                            os.path.join(job_dir, thumb_name)], capture_output=True)

            short = {
                "index": i,
                "file": out_name,
                "thumb": thumb_name if os.path.exists(os.path.join(job_dir, thumb_name)) else None,
                "start": round(start, 2),
                "end": round(end, 2),
                "range": f"{fmt_time(start)} - {fmt_time(end)}",
                "duration": round(clip_len, 1),
                "size_mb": round(os.path.getsize(out_path) / 1_048_576, 1),
                "download_name": f"{base_name}_short_{i:02d}.mp4",
            }
            with jobs_lock:
                jobs[job_id]["shorts"].append(short)

        os.remove(src)
        update(job_id, status="done", stage="All shorts are ready!", progress=100)
    except yt_dlp.utils.DownloadError as e:
        msg = re.sub(r"\x1b\[[0-9;]*m", "", str(e)).replace("ERROR: ", "")
        update(job_id, status="error", stage="Failed", error=f"YouTube error: {msg[:300]}")
    except Exception as e:  # noqa: BLE001 - surface any failure to the UI
        update(job_id, status="error", stage="Failed", error=str(e)[:500])


# --------------------------------------------------------------------------- routes

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.post("/api/process")
def api_process():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    if not is_youtube_url(url):
        return jsonify(error="Please paste a valid YouTube link (youtube.com or youtu.be)."), 400

    try:
        min_len = int(data.get("min_len", 60))
        max_len = int(data.get("max_len", 90))
        max_count = int(data.get("max_count", 10))
        height = int(data.get("quality", 1080))
    except (TypeError, ValueError):
        return jsonify(error="Invalid options."), 400
    min_len = max(MIN_LEN_LIMIT, min(MAX_LEN_LIMIT, min_len))
    max_len = max(min_len, min(MAX_LEN_LIMIT, max_len))
    opts = {
        "min_len": min_len,
        "max_len": max_len,
        "max_count": max(1, min(50, max_count)),
        "height": 720 if height == 720 else 1080,
        "mode": "crop" if data.get("mode") == "crop" else "blur",
        "titles": data.get("titles", True) is not False,
    }

    cleanup_old_jobs()
    job_id = uuid.uuid4().hex
    with jobs_lock:
        jobs[job_id] = {"status": "working", "stage": "Starting...", "progress": 0,
                        "title": "", "shorts": [], "total": 0, "error": None,
                        "created": time.time()}
    threading.Thread(target=process_job, args=(job_id, url, opts), daemon=True).start()
    return jsonify(job_id=job_id)


@app.get("/api/status/<job_id>")
def api_status(job_id):
    with jobs_lock:
        job = jobs.get(job_id)
        if not job:
            return jsonify(error="Job not found (it may have expired)."), 404
        return jsonify(job)


def job_dir_or_404(job_id):
    if not re.fullmatch(r"[0-9a-f]{32}", job_id):
        abort(404)
    path = os.path.join(JOBS_DIR, job_id)
    if not os.path.isdir(path):
        abort(404)
    return path


@app.get("/media/<job_id>/<path:filename>")
def media(job_id, filename):
    return send_from_directory(job_dir_or_404(job_id), filename)


@app.get("/download/<job_id>/<path:filename>")
def download(job_id, filename):
    path = job_dir_or_404(job_id)
    with jobs_lock:
        job = jobs.get(job_id) or {}
        short = next((s for s in job.get("shorts", []) if s["file"] == filename), None)
    name = short["download_name"] if short else filename
    return send_from_directory(path, filename, as_attachment=True, download_name=name)


@app.get("/download-all/<job_id>")
def download_all(job_id):
    path = job_dir_or_404(job_id)
    with jobs_lock:
        job = jobs.get(job_id) or {}
        shorts = list(job.get("shorts", []))
        title = job.get("title", "")
    if not shorts:
        abort(404)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
        for s in shorts:
            zf.write(os.path.join(path, s["file"]), s["download_name"])
    buf.seek(0)
    return send_file(buf, mimetype="application/zip", as_attachment=True,
                     download_name=f"{safe_name(title)}_shorts.zip")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n  ShortsForge running at  http://127.0.0.1:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
