from flask import Flask, render_template, request, send_from_directory, jsonify
from werkzeug.utils import secure_filename
from pathlib import Path
import subprocess
import uuid
import os
import shutil

BASE_DIR = Path(__file__).resolve().parent
UPLOADS = BASE_DIR / "uploads"
OUTPUTS = BASE_DIR / "outputs"
SUBTITLES = BASE_DIR / "subtitles"

for folder in [UPLOADS, OUTPUTS, SUBTITLES]:
    folder.mkdir(exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 300 * 1024 * 1024

ALLOWED = {"mp3", "wav", "m4a", "aac", "flac", "ogg"}

PRESETS = {
    "studio_master": {
        "label": "Studio Master",
        "filter": "highpass=f=80,lowpass=f=16000,afftdn=nf=-24,acompressor=threshold=-18dB:ratio=3:attack=12:release=180:makeup=2,alimiter=limit=0.90,loudnorm=I=-14:TP=-1.2:LRA=10"
    },
    "podcast": {
        "label": "Podcast Voice",
        "filter": "highpass=f=95,lowpass=f=15000,afftdn=nf=-25,equalizer=f=3200:t=q:w=1:g=2.5,acompressor=threshold=-19dB:ratio=3.2:attack=8:release=170:makeup=2.5,alimiter=limit=0.91,loudnorm=I=-16:TP=-1.5:LRA=9"
    },
    "shorts": {
        "label": "YouTube Shorts Loud",
        "filter": "highpass=f=90,lowpass=f=15500,afftdn=nf=-23,acompressor=threshold=-20dB:ratio=3.8:attack=7:release=150:makeup=3,alimiter=limit=0.92,loudnorm=I=-13:TP=-1.0:LRA=8"
    },
    "warm_voice": {
        "label": "Warm Voice",
        "filter": "highpass=f=75,lowpass=f=13000,afftdn=nf=-22,equalizer=f=180:t=q:w=1:g=1.8,acompressor=threshold=-21dB:ratio=2.4:attack=18:release=220,alimiter=limit=0.92,loudnorm=I=-15:TP=-1.5:LRA=11"
    }
}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED

def srt_time(seconds):
    seconds = max(0, float(seconds))
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"

def create_srt(script, output_path):
    text = (script or "").strip() or "MauliVoice Studio Ultimate"
    words = text.split()
    chunks = [" ".join(words[i:i+8]) for i in range(0, len(words), 8)] or [text]
    with output_path.open("w", encoding="utf-8") as f:
        for index, line in enumerate(chunks, 1):
            start = (index - 1) * 4
            end = index * 4 - 0.2
            f.write(f"{index}\\n{srt_time(start)} --> {srt_time(end)}\\n{line}\\n\\n")

@app.route("/")
def index():
    return render_template("index.html", presets=PRESETS)

@app.route("/health")
def health():
    return jsonify({
        "ok": True,
        "app": "MauliVoice Studio Ultimate",
        "version": "Latest-Tech Cloud PWA",
        "ffmpeg": bool(shutil.which("ffmpeg"))
    })

@app.route("/process", methods=["POST"])
def process():
    audio = request.files.get("audio")
    script = request.form.get("script", "")
    preset = request.form.get("preset", "studio_master")

    if not audio or audio.filename == "":
        return jsonify({"ok": False, "error": "Audio file missing"}), 400

    if not allowed_file(audio.filename):
        return jsonify({"ok": False, "error": "Unsupported audio format"}), 400

    if not shutil.which("ffmpeg"):
        return jsonify({"ok": False, "error": "FFmpeg is not available on server. Use Docker deployment included in this package."}), 500

    job_id = uuid.uuid4().hex[:10]
    safe_original = secure_filename(audio.filename)
    input_path = UPLOADS / f"{job_id}_{safe_original}"
    output_name = f"{job_id}_maulivoice_master.mp3"
    subtitle_name = f"{job_id}_subtitles.srt"
    output_path = OUTPUTS / output_name
    subtitle_path = SUBTITLES / subtitle_name

    audio.save(input_path)

    selected = PRESETS.get(preset, PRESETS["studio_master"])
    filter_chain = selected["filter"]

    try:
        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-af", filter_chain,
            "-codec:a", "libmp3lame",
            "-b:a", "192k",
            str(output_path)
        ]
        subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=260)
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "Processing timeout. Try a shorter file."}), 500
    except subprocess.CalledProcessError as e:
        return jsonify({"ok": False, "error": e.stderr[-1200:]}), 500

    create_srt(script, subtitle_path)

    return jsonify({
        "ok": True,
        "message": "Processing complete",
        "audio_url": f"/download/audio/{output_name}",
        "srt_url": f"/download/subtitles/{subtitle_name}",
        "preset": selected["label"]
    })

@app.route("/download/audio/<path:filename>")
def download_audio(filename):
    return send_from_directory(OUTPUTS, filename, as_attachment=True)

@app.route("/download/subtitles/<path:filename>")
def download_subtitles(filename):
    return send_from_directory(SUBTITLES, filename, as_attachment=True)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)
