from flask import Flask, render_template, request, send_from_directory, jsonify
from werkzeug.utils import secure_filename
from pathlib import Path
import subprocess, uuid, os

BASE_DIR = Path(__file__).resolve().parent
UPLOADS = BASE_DIR / "uploads"
OUTPUTS = BASE_DIR / "outputs"
SUBTITLES = BASE_DIR / "subtitles"

for folder in [UPLOADS, OUTPUTS, SUBTITLES]:
    folder.mkdir(exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 250 * 1024 * 1024

ALLOWED = {"mp3", "wav", "m4a", "aac", "flac", "ogg"}

PRESETS = {
    "studio_master": "highpass=f=80,lowpass=f=16000,acompressor=threshold=-18dB:ratio=3:attack=12:release=180:makeup=2,alimiter=limit=0.90,loudnorm=I=-14:TP=-1.2:LRA=10",
    "podcast": "highpass=f=95,lowpass=f=15000,acompressor=threshold=-19dB:ratio=3.2:attack=8:release=170:makeup=2.5,alimiter=limit=0.91,loudnorm=I=-16:TP=-1.5:LRA=9",
    "shorts": "highpass=f=90,lowpass=f=15500,acompressor=threshold=-20dB:ratio=3.8:attack=7:release=150:makeup=3,alimiter=limit=0.92,loudnorm=I=-13:TP=-1.0:LRA=8",
    "warm_voice": "highpass=f=75,lowpass=f=13000,equalizer=f=180:t=q:w=1:g=1.8,acompressor=threshold=-21dB:ratio=2.4:attack=18:release=220,alimiter=limit=0.92,loudnorm=I=-15:TP=-1.5:LRA=11"
}

def allowed_file(name):
    return "." in name and name.rsplit(".", 1)[1].lower() in ALLOWED

def srt_time(seconds):
    seconds = max(0, float(seconds))
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"

def create_srt(script, out_path):
    text = (script or "").strip() or "MauliVoice Studio Ultimate"
    words = text.split()
    chunks = [" ".join(words[i:i+8]) for i in range(0, len(words), 8)] or [text]
    with out_path.open("w", encoding="utf-8") as f:
        for i, line in enumerate(chunks, 1):
            start = (i - 1) * 4
            end = i * 4 - 0.2
            f.write(f"{i}\n{srt_time(start)} --> {srt_time(end)}\n{line}\n\n")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/health")
def health():
    return jsonify({"status": "ok", "app": "MauliVoice Universal Creator Studio"})

@app.route("/process", methods=["POST"])
def process():
    audio = request.files.get("audio")
    script = request.form.get("script", "")
    preset = request.form.get("preset", "studio_master")

    if not audio or audio.filename == "":
        return jsonify({"ok": False, "error": "Audio file missing"}), 400
    if not allowed_file(audio.filename):
        return jsonify({"ok": False, "error": "Unsupported audio format"}), 400

    job = uuid.uuid4().hex[:10]
    filename = secure_filename(audio.filename)
    input_path = UPLOADS / f"{job}_{filename}"
    output_name = f"{job}_maulivoice_output.mp3"
    srt_name = f"{job}_subtitles.srt"
    output_path = OUTPUTS / output_name
    srt_path = SUBTITLES / srt_name
    audio.save(input_path)

    filter_chain = PRESETS.get(preset, PRESETS["studio_master"])
    try:
        cmd = ["ffmpeg", "-y", "-i", str(input_path), "-af", filter_chain, "-codec:a", "libmp3lame", "-b:a", "192k", str(output_path)]
        subprocess.run(cmd, capture_output=True, text=True, check=True)
    except FileNotFoundError:
        return jsonify({"ok": False, "error": "FFmpeg not found on server/PC"}), 500
    except subprocess.CalledProcessError as e:
        return jsonify({"ok": False, "error": e.stderr[-1000:]}), 500

    create_srt(script, srt_path)
    return jsonify({"ok": True, "audio_url": f"/download/audio/{output_name}", "srt_url": f"/download/subtitles/{srt_name}", "message": "Processing complete"})

@app.route("/download/audio/<path:filename>")
def download_audio(filename):
    return send_from_directory(OUTPUTS, filename, as_attachment=True)

@app.route("/download/subtitles/<path:filename>")
def download_subtitles(filename):
    return send_from_directory(SUBTITLES, filename, as_attachment=True)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
