const videoForm = document.getElementById('video-form');
const videosContainer = document.getElementById('videos');

async function fetchVideos() {
  const response = await fetch('/api/videos');
  const videos = await response.json();
  videosContainer.innerHTML = videos.map((video) => `
    <article class="video-card">
      <h3>${video.title}</h3>
      <small>${video.filename}</small>
      <small>Annotator: ${video.annotator_id}</small>
      <small>Status: ${video.status}</small>
    </article>
  `).join('');
}

videoForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const formData = new FormData(videoForm);
  const payload = Object.fromEntries(formData.entries());

  const response = await fetch('/api/videos', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (response.ok) {
    videoForm.reset();
    await fetchVideos();
  }
});

fetchVideos();
