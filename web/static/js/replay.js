/**
 * GeoShield – Disaster Replay Engine
 * Provides timeline replay controls to step through satellite-detected disaster evolution.
 */

let replayData = [];
let currentIndex = 0;
let isPlaying = false;
let playInterval = null;

document.addEventListener('DOMContentLoaded', () => {
  initReplay();
});

async function initReplay() {
  const yearSelect = document.getElementById('replay-year');
  if (yearSelect) {
    yearSelect.addEventListener('change', () => loadReplaySequence(yearSelect.value));
  }

  loadReplaySequence(2024);

  const slider = document.getElementById('timeline-slider');
  if (slider) {
    slider.addEventListener('input', (e) => {
      currentIndex = parseInt(e.target.value);
      renderCurrentFrame();
    });
  }

  const btnPlay = document.getElementById('btn-play-pause');
  if (btnPlay) {
    btnPlay.addEventListener('click', () => {
      togglePlayback();
    });
  }
}

async function loadReplaySequence(year = 2024) {
  try {
    const res = await fetch(`/api/replay?year=${year}`);
    const data = await res.json();
    replayData = data.daily_data || [];

    const slider = document.getElementById('timeline-slider');
    if (slider) {
      slider.min = 0;
      slider.max = Math.max(0, replayData.length - 1);
      slider.value = 0;
    }

    currentIndex = 0;
    renderCurrentFrame();
  } catch (err) {
    console.error('Replay load error', err);
  }
}

function renderCurrentFrame() {
  if (!replayData || replayData.length === 0) return;
  const frame = replayData[currentIndex];
  if (!frame) return;

  document.getElementById('replay-current-date').innerText = frame.date;
  document.getElementById('frame-total').innerText = frame.total.toLocaleString();
  document.getElementById('frame-fire').innerText = frame.fire.toLocaleString();
  document.getElementById('frame-flood').innerText = frame.flood.toLocaleString();
  document.getElementById('frame-avg-frp').innerText = `${frame.avg_frp} MW`;
  document.getElementById('frame-high-sev').innerText = frame.high_sev;

  const slider = document.getElementById('timeline-slider');
  if (slider) slider.value = currentIndex;
}

function togglePlayback() {
  const btn = document.getElementById('btn-play-pause');
  if (isPlaying) {
    clearInterval(playInterval);
    isPlaying = false;
    if (btn) btn.innerHTML = '▶ Play Replay';
  } else {
    isPlaying = true;
    if (btn) btn.innerHTML = '⏸ Pause';
    playInterval = setInterval(() => {
      currentIndex++;
      if (currentIndex >= replayData.length) {
        currentIndex = 0;
      }
      renderCurrentFrame();
    }, 600);
  }
}
