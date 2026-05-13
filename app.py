from flask import Flask, render_template, request, send_from_directory, jsonify
from werkzeug.utils import secure_filename
from pathlib import Path
import subprocess, uuid, os, shutil, zipfile, json
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent
UPLOADS = BASE_DIR / "uploads"
OUTPUTS = BASE_DIR / "outputs"
SUBTITLES = BASE_DIR / "subtitles"
EXPORTS = BASE_DIR / "exports"
PROJECTS = BASE_DIR / "projects"
BACKGROUNDS = BASE_DIR / "backgrounds"

for folder in [UPLOADS, OUTPUTS, SUBTITLES, EXPORTS, PROJECTS, BACKGROUNDS]:
    folder.mkdir(exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 300 * 1024 * 1024

ALLOWED = {"mp3", "wav", "m4a", "aac", "flac", "ogg"}

PRESETS = {
    "clean": {
        "name": "Clean Voice",
        "filter": "highpass=f=85,lowpass=f=14500,afftdn=nf=-24,equalizer=f=3000:t=q:w=1:g=2,acompressor=threshold=-20dB:ratio=2.5:attack=12:release=180,alimiter=limit=0.92,loudnorm=I=-16:TP=-1.5:LRA=10"
    },
    "studio": {
        "name": "Studio Master",
        "filter": "highpass=f=80,lowpass=f=16000,afftdn=nf=-25,equalizer=f=3500:t=q:w=1:g=2.4,acompressor=threshold=-18dB:ratio=3:attack=10:release=170:makeup=2,alimiter=limit=0.90,loudnorm=I=-14:TP=-1.2:LRA=9"
    },
    "devotional": {
        "name": "Devotional Warm",
        "filter": "highpass=f=85,lowpass=f=13500,afftdn=nf=-24,equalizer=f=220:t=q:w=1:g=1.6,equalizer=f=2600:t=q:w=1:g=1.8,aecho=0.65:0.55:520:0.10,acompressor=threshold=-20dB:ratio=2.4:attack=20:release=220,alimiter=limit=0.92,loudnorm=I=-15:TP=-1.5:LRA=11"
    },
    "shorts": {
        "name": "Shorts Loud",
        "filter": "highpass=f=90,lowpass=f=15500,afftdn=nf=-23,acompressor=threshold=-20dB:ratio=3.6:attack=7:release=150:makeup=3,alimiter=limit=0.92,loudnorm=I=-13:TP=-1.0:LRA=8"
    }
}

EXPORTS_PRESET = {
    "youtube": {"name": "YouTube", "bitrate": "192k"},
    "shorts": {"name": "Shorts/Reels", "bitrate": "192k"},
    "podcast": {"name": "Podcast", "bitrate": "160k"},
    "master": {"name": "Master HQ", "bitrate": "256k"}
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

def create_srt(script, path):
    text = (script or "").strip() or "MauliVoice Studio Ultimate"
    lines = []
    for part in text.replace("।", "।\n").replace(".", ".\n").replace("!", "!\n").replace("?", "?\n").splitlines():
        part = part.strip()
        if not part:
            continue
        words = part.split()
        for i in range(0, len(words), 8):
            lines.append(" ".join(words[i:i+8]))
    if not lines:
        lines = [text]
    cursor = 0.0
    with path.open("w", encoding="utf-8") as f:
        for idx, line in enumerate(lines, 1):
            duration = max(2.5, min(5.5, len(line.split()) * 0.55))
            f.write(f"{idx}\n{srt_time(cursor)} --> {srt_time(cursor + duration)}\n{line}\n\n")
            cursor += duration + 0.15

def run_ffmpeg(cmd):
    subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=260)

@app.route("/")
def index():
    return render_template("index.html", presets=PRESETS, export_presets=EXPORTS_PRESET)

@app.route("/health")
def health():
    return jsonify({"ok": True, "ffmpeg": bool(shutil.which("ffmpeg")), "version": "Commercial One Window Working Build"})

@app.route("/process", methods=["POST"])
def process():
    if not shutil.which("ffmpeg"):
        return jsonify({"ok": False, "error": "FFmpeg not available. Docker deploy required."}), 500

    audio = request.files.get("audio")
    background = request.files.get("background")
    script = request.form.get("script", "")
    preset_key = request.form.get("preset", "studio")
    export_key = request.form.get("export_preset", "youtube")
    bg_volume = float(request.form.get("bg_volume", "0.12") or 0.12)
    project_name = (request.form.get("project_name", "MauliVoice Project") or "MauliVoice Project").strip()

    bg_volume = max(0.02, min(bg_volume, 0.60))

    if not audio or audio.filename == "":
        return jsonify({"ok": False, "error": "Please select an audio file."}), 400
    if not allowed_file(audio.filename):
        return jsonify({"ok": False, "error": "Unsupported audio format."}), 400

    job = uuid.uuid4().hex[:10]
    audio_path = UPLOADS / f"{job}_{secure_filename(audio.filename)}"
    audio.save(audio_path)

    bg_path = None
    if background and background.filename and allowed_file(background.filename):
        bg_path = BACKGROUNDS / f"{job}_{secure_filename(background.filename)}"
        background.save(bg_path)

    preset = PRESETS.get(preset_key, PRESETS["studio"])
    export_preset = EXPORTS_PRESET.get(export_key, EXPORTS_PRESET["youtube"])

    output_name = f"{job}_maulivoice_{export_key}.mp3"
    srt_name = f"{job}_subtitles.srt"
    project_name_file = f"{job}_project.mauli_project"
    zip_name = f"{job}_creator_package.zip"

    output_path = OUTPUTS / output_name
    srt_path = SUBTITLES / srt_name
    project_path = PROJECTS / project_name_file
    zip_path = EXPORTS / zip_name

    try:
        if bg_path:
            temp_voice = OUTPUTS / f"{job}_voice_tmp.wav"
            run_ffmpeg(["ffmpeg", "-y", "-i", str(audio_path), "-af", preset["filter"], "-ar", "44100", "-ac", "2", str(temp_voice)])
            mix_filter = f"[1:a]volume={bg_volume},aloop=loop=-1:size=2e+09[bg];[0:a][bg]amix=inputs=2:duration=first:dropout_transition=2,alimiter=limit=0.92,loudnorm=I=-14:TP=-1.3:LRA=10[out]"
            run_ffmpeg(["ffmpeg", "-y", "-i", str(temp_voice), "-i", str(bg_path), "-filter_complex", mix_filter, "-map", "[out]", "-codec:a", "libmp3lame", "-b:a", export_preset["bitrate"], str(output_path)])
            try:
                temp_voice.unlink()
            except Exception:
                pass
        else:
            run_ffmpeg(["ffmpeg", "-y", "-i", str(audio_path), "-af", preset["filter"], "-codec:a", "libmp3lame", "-b:a", export_preset["bitrate"], str(output_path)])
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "Processing timeout. Try shorter file."}), 500
    except subprocess.CalledProcessError as e:
        return jsonify({"ok": False, "error": e.stderr[-1200:]}), 500

    create_srt(script, srt_path)

    meta = {
        "app": "MauliVoice Studio Ultimate",
        "version": "Commercial One Window Working Build",
        "project_name": project_name,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "preset": preset["name"],
        "export": export_preset["name"],
        "background_mixed": bool(bg_path)
    }
    project_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(output_path, output_name)
        z.write(srt_path, srt_name)
        z.write(project_path, project_name_file)

    return jsonify({
        "ok": True,
        "message": "Done. Creator package ready.",
        "audio_url": f"/download/audio/{output_name}",
        "srt_url": f"/download/subtitles/{srt_name}",
        "project_url": f"/download/project/{project_name_file}",
        "zip_url": f"/download/export/{zip_name}"
    })

@app.route("/download/audio/<path:filename>")
def download_audio(filename):
    return send_from_directory(OUTPUTS, filename, as_attachment=True)

@app.route("/download/subtitles/<path:filename>")
def download_srt(filename):
    return send_from_directory(SUBTITLES, filename, as_attachment=True)

@app.route("/download/project/<path:filename>")
def download_project(filename):
    return send_from_directory(PROJECTS, filename, as_attachment=True)

@app.route("/download/export/<path:filename>")
def download_export(filename):
    return send_from_directory(EXPORTS, filename, as_attachment=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)), debug=False)
