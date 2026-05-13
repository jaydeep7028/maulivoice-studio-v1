const wavesurfer = WaveSurfer.create({
  container: "#waveform",
  waveColor: "#6f7aa0",
  progressColor: "#ffb35c",
  cursorColor: "#fff",
  barWidth: 2,
  height: 140,
  responsive: true
});

const audioInput = document.getElementById("audioInput");
const dropZone = document.getElementById("dropZone");
const audioPlayer = document.getElementById("audioPlayer");
const fileName = document.getElementById("fileName");
const statusBox = document.getElementById("status");
const topStatus = document.getElementById("topStatus");
const downloads = document.getElementById("downloads");

function loadPreview(file){
  if(!file) return;
  const url = URL.createObjectURL(file);
  audioPlayer.src = url;
  wavesurfer.load(url);
  fileName.textContent = file.name;
  statusBox.textContent = "Preview loaded.";
  topStatus.textContent = "Preview ready";
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
  statusBox.textContent = "Processing audio... please wait.";
  topStatus.textContent = "Processing";
  downloads.innerHTML = `<button disabled>Working...</button><button disabled>Please wait</button>`;

  try{
    const res = await fetch("/process", {method:"POST", body:new FormData(e.target)});
    const data = await res.json();
    if(!data.ok){
      statusBox.textContent = "Error: " + data.error;
      topStatus.textContent = "Error";
      return;
    }
    statusBox.textContent = data.message;
    topStatus.textContent = "Done";
    downloads.innerHTML = `
      <a href="${data.audio_url}">Download Audio</a>
      <a href="${data.srt_url}">Download SRT</a>
      <a href="${data.project_url}">Project File</a>
      <a href="${data.zip_url}">ZIP Package</a>
    `;
  }catch(err){
    statusBox.textContent = "Network error: " + err.message;
    topStatus.textContent = "Error";
  }
});
