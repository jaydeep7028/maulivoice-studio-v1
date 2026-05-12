const wavesurfer = WaveSurfer.create({
    container: '#waveform',
    waveColor: '#666',
    progressColor: '#ff9800',
    cursorColor: '#ffffff',
    height: 120,
    responsive: true
});

const playBtn = document.getElementById('playBtn');
const pauseBtn = document.getElementById('pauseBtn');
const stopBtn = document.getElementById('stopBtn');

playBtn.onclick = () => wavesurfer.play();
pauseBtn.onclick = () => wavesurfer.pause();
stopBtn.onclick = () => wavesurfer.stop();

const dropZone = document.getElementById('dropZone');
const audioPlayer = document.getElementById('audioPlayer');

dropZone.addEventListener('dragover', (e)=>{
    e.preventDefault();
});

dropZone.addEventListener('drop', (e)=>{
    e.preventDefault();

    const file = e.dataTransfer.files[0];

    if(file){
        const url = URL.createObjectURL(file);
        audioPlayer.src = url;
        wavesurfer.load(url);
    }
});
