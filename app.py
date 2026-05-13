from flask import Flask, render_template, request, send_from_directory, jsonify
from werkzeug.utils import secure_filename
from pathlib import Path
import subprocess, uuid, os, shutil, zipfile, json
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent
UPLOADS = BASE_DIR / "uploads"
OUTPUTS = BASE_DIR / "outputs"
SUBTITLES = BASE_DIR / "subtitles"
PROJECTS = BASE_DIR / "projects"
EXPORTS = BASE_DIR / "exports"
BACKGROUNDS = BASE_DIR / "backgrounds"
for f in [UPLOADS, OUTPUTS, SUBTITLES, PROJECTS, EXPORTS, BACKGROUNDS]:
    f.mkdir(exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 350 * 1024 * 1024
ALLOWED = {"mp3","wav","m4a","aac","flac","ogg"}

PRESETS = {
    "devotional": {"name":"Devotional", "desc":"Warm, Spiritual Tone", "filter":"highpass=f=90,lowpass=f=13500,afftdn=nf=-24,equalizer=f=220:t=q:w=1:g=1.8,equalizer=f=2600:t=q:w=1:g=2,aecho=0.8:0.72:700:0.18,acompressor=threshold=-20dB:ratio=2.5:attack=20:release=220,alimiter=limit=0.92,loudnorm=I=-15:TP=-1.5:LRA=11"},
    "podcast": {"name":"Podcast", "desc":"Clean, Modern Voice", "filter":"highpass=f=95,lowpass=f=15000,afftdn=nf=-25,equalizer=f=3200:t=q:w=1:g=2.5,acompressor=threshold=-19dB:ratio=3.2:attack=8:release=170:makeup=2.5,alimiter=limit=0.91,loudnorm=I=-16:TP=-1.5:LRA=9"},
    "cinematic": {"name":"Cinematic", "desc":"Deep, Wide & Epic", "filter":"highpass=f=70,lowpass=f=14000,afftdn=nf=-22,equalizer=f=140:t=q:w=1:g=2.2,equalizer=f=2800:t=q:w=1:g=1.6,aecho=0.55:0.45:420:0.08,acompressor=threshold=-20dB:ratio=2.8:attack=18:release=210,alimiter=limit=0.92,loudnorm=I=-15:TP=-1.4:LRA=11"},
    "narration": {"name":"Narration", "desc":"Neutral & Professional", "filter":"highpass=f=80,lowpass=f=16000,afftdn=nf=-25,equalizer=f=3500:t=q:w=1:g=2.5,acompressor=threshold=-18dB:ratio=3:attack=12:release=180:makeup=2,alimiter=limit=0.90,loudnorm=I=-14:TP=-1.2:LRA=10"},
    "news": {"name":"News", "desc":"Crisp & Clear", "filter":"highpass=f=100,lowpass=f=15500,afftdn=nf=-24,equalizer=f=3800:t=q:w=1:g=3,acompressor=threshold=-18dB:ratio=3.5:attack=8:release=160:makeup=2.5,alimiter=limit=0.92,loudnorm=I=-15:TP=-1.4:LRA=9"},
    "lofi": {"name":"Lofi", "desc":"Soft & Relaxed", "filter":"highpass=f=70,lowpass=f=9500,equalizer=f=200:t=q:w=1:g=1.8,acompressor=threshold=-22dB:ratio=2.1:attack=28:release=260,alimiter=limit=0.92,loudnorm=I=-17:TP=-1.8:LRA=12"}
}

EXPORT_PRESETS = {
    "youtube": {"label": "YouTube (1080p)", "bitrate": "320k", "loudness": "-14"},
    "shorts": {"label": "Shorts/Reels", "bitrate": "192k", "loudness": "-13"},
    "podcast": {"label": "Podcast", "bitrate": "160k", "loudness": "-16"},
    "audiobook": {"label": "Audiobook", "bitrate": "128k", "loudness": "-18"}
}

def allowed(name):
    return "." in name and name.rsplit(".",1)[1].lower() in ALLOWED

def srt_time(sec):
    sec=max(0,float(sec)); h=int(sec//3600); m=int((sec%3600)//60); s=int(sec%60); ms=int((sec-int(sec))*1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"

def make_smart_srt(script, path):
    text=(script or "").strip() or "MauliVoice Studio Ultimate"
    raw = [x.strip() for x in text.replace("।", "।\n").replace(".", ".\n").replace("?", "?\n").replace("!", "!\n").splitlines() if x.strip()]
    chunks=[]
    for line in raw:
        words=line.split()
        if len(words)<=8:
            chunks.append(line)
        else:
            for i in range(0,len(words),8):
                chunks.append(" ".join(words[i:i+8]))
    if not chunks: chunks=[text]
    cursor=0.0
    with path.open("w", encoding="utf-8") as f:
        for i,line in enumerate(chunks,1):
            dur=max(2.2,min(5.8,len(line.split())*0.55))
            f.write(f"{i}\\n{srt_time(cursor)} --> {srt_time(cursor+dur)}\\n{line}\\n\\n")
            cursor += dur + 0.15

def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=280)

@app.route("/")
def index():
    return render_template("index.html", presets=PRESETS, export_presets=EXPORT_PRESETS)

@app.route("/health")
def health():
    return jsonify({"ok": True, "version": "NextGen UI Exact Build", "ffmpeg": bool(shutil.which("ffmpeg"))})

@app.route("/process", methods=["POST"])
def process():
    audio=request.files.get("audio")
    bg=request.files.get("background")
    script=request.form.get("script","")
    preset=request.form.get("preset","devotional")
    export_preset=request.form.get("export_preset","youtube")
    project_name=request.form.get("project_name","Sant Tukaram Katha").strip() or "MauliVoice Project"
    bg_volume=float(request.form.get("bg_volume","0.28") or 0.28)
    bg_volume=max(0.02,min(bg_volume,0.60))

    if not audio or audio.filename=="": return jsonify({"ok":False,"error":"Audio file missing"}),400
    if not allowed(audio.filename): return jsonify({"ok":False,"error":"Unsupported file format"}),400
    if not shutil.which("ffmpeg"): return jsonify({"ok":False,"error":"FFmpeg not available. Docker deploy required."}),500

    job=uuid.uuid4().hex[:10]
    inp=UPLOADS/f"{job}_{secure_filename(audio.filename)}"
    audio.save(inp)

    bg_path=None
    if bg and bg.filename and allowed(bg.filename):
        bg_path=BACKGROUNDS/f"{job}_{secure_filename(bg.filename)}"
        bg.save(bg_path)

    selected=PRESETS.get(preset, PRESETS["devotional"])
    exp=EXPORT_PRESETS.get(export_preset, EXPORT_PRESETS["youtube"])
    out_name=f"{job}_maulivoice_master.mp3"
    srt_name=f"{job}_subtitles.srt"
    project_file_name=f"{job}_project.mauli_project"
    zip_name=f"{job}_export_package.zip"

    out=OUTPUTS/out_name
    srt=SUBTITLES/srt_name
    project_file=PROJECTS/project_file_name
    zip_file=EXPORTS/zip_name

    try:
        if bg_path:
            temp=OUTPUTS/f"{job}_voice_tmp.wav"
            run(["ffmpeg","-y","-i",str(inp),"-af",selected["filter"],"-ar","44100","-ac","2",str(temp)])
            fc=f"[1:a]volume={bg_volume},aloop=loop=-1:size=2e+09[bg];[0:a][bg]amix=inputs=2:duration=first:dropout_transition=2,alimiter=limit=0.92,loudnorm=I={exp['loudness']}:TP=-1.3:LRA=10[out]"
            run(["ffmpeg","-y","-i",str(temp),"-i",str(bg_path),"-filter_complex",fc,"-map","[out]","-codec:a","libmp3lame","-b:a",exp["bitrate"],str(out)])
            try: temp.unlink()
            except Exception: pass
        else:
            run(["ffmpeg","-y","-i",str(inp),"-af",selected["filter"],"-codec:a","libmp3lame","-b:a",exp["bitrate"],str(out)])
    except subprocess.TimeoutExpired:
        return jsonify({"ok":False,"error":"Processing timeout. Try shorter audio."}),500
    except subprocess.CalledProcessError as e:
        return jsonify({"ok":False,"error":e.stderr[-1200:]}),500

    make_smart_srt(script, srt)

    meta={
        "project_name": project_name,
        "job_id": job,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "voice_preset": selected["name"],
        "export_preset": exp["label"],
        "app": "MauliVoice Studio Ultimate",
        "version": "NextGen UI Exact Build"
    }
    project_file.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    with zipfile.ZipFile(zip_file,"w",zipfile.ZIP_DEFLATED) as z:
        z.write(out,out_name); z.write(srt,srt_name); z.write(project_file,project_file_name)

    return jsonify({
        "ok": True,
        "message": "Master + SRT ready",
        "audio_url": f"/download/audio/{out_name}",
        "srt_url": f"/download/subtitles/{srt_name}",
        "project_url": f"/download/project/{project_file_name}",
        "zip_url": f"/download/export/{zip_name}"
    })

@app.route("/download/audio/<path:f>")
def da(f): return send_from_directory(OUTPUTS, f, as_attachment=True)
@app.route("/download/subtitles/<path:f>")
def ds(f): return send_from_directory(SUBTITLES, f, as_attachment=True)
@app.route("/download/project/<path:f>")
def dp(f): return send_from_directory(PROJECTS, f, as_attachment=True)
@app.route("/download/export/<path:f>")
def de(f): return send_from_directory(EXPORTS, f, as_attachment=True)

if __name__=="__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000)), debug=False)
