const wavesurfer = WaveSurfer.create({
  container: "#waveform",
  waveColor: "#777",
  progressColor: "#ff9800",
  cursorColor: "#fff",
  barWidth: 2,
  height: 110,
  responsive: true
});

const audioInput = document.getElementById("audioInput");
const dropZone = document.getElementById("dropZone");
const audioPlayer = document.getElementById("audioPlayer");
const statusBox = document.getElementById("status");
const downloads = document.getElementById("downloads");

function loadPreview(file){
  if(!file) return;
  const url = URL.createObjectURL(file);
  audioPlayer.src = url;
  wavesurfer.load(url);
  statusBox.textContent = "Preview loaded.";
}

audioInput.addEventListener("change", e => loadPreview(e.target.files[0]));

["dragenter","dragover"].forEach(ev=>{
  dropZone.addEventListener(ev, e=>{
    e.preventDefault();
    dropZone.classList.add("dragging");
  });
});
["dragleave","drop"].forEach(ev=>{
  dropZone.addEventListener(ev, e=>{
    e.preventDefault();
    dropZone.classList.remove("dragging");
  });
});
dropZone.addEventListener("drop", e=>{
  const file = e.dataTransfer.files[0];
  if(file){
    audioInput.files = e.dataTransfer.files;
    loadPreview(file);
  }
});

document.getElementById("playBtn").onclick = () => wavesurfer.play();
document.getElementById("pauseBtn").onclick = () => wavesurfer.pause();
document.getElementById("stopBtn").onclick = () => wavesurfer.stop();

document.getElementById("processForm").addEventListener("submit", async e=>{
  e.preventDefault();
  statusBox.textContent = "Uploading and processing...";
  downloads.innerHTML = "";
  const formData = new FormData(e.target);

  try{
    const res = await fetch("/process", {method:"POST", body:formData});
    const data = await res.json();
    if(!data.ok){
      statusBox.textContent = "Error: " + data.error;
      return;
    }
    statusBox.textContent = `${data.message} — ${data.preset}`;
    downloads.innerHTML = `<a href="${data.audio_url}">Download Mastered Audio</a><a href="${data.srt_url}">Download SRT</a>`;
  }catch(err){
    statusBox.textContent = "Network/server error: " + err.message;
  }
});
