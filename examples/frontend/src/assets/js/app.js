const videoForm = document.getElementById('video-form');
const videosContainer = document.getElementById('videos');
const formError = document.getElementById('video-form-error');

async function fetchVideos() {
  const response = await fetch('/api/videos');
  if (!response.ok) throw new Error('Could not load the video list.');
  const videos = await response.json();
  const cards = videos.map((video) => {
    const card = document.createElement('article');
    card.className = 'video-card';
    const title = document.createElement('h3');
    title.textContent = video.title;
    card.append(title);
    for (const text of [video.filename, `Annotator: ${video.annotator_id}`, `Status: ${video.status}`]) {
      const line = document.createElement('small');
      line.textContent = text;
      card.append(line);
    }
    return card;
  });
  videosContainer.replaceChildren(...cards);
}

videoForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const formData = new FormData(videoForm);
  const payload = Object.fromEntries(formData.entries());

  formError.textContent = '';
  try {
    const response = await fetch('/api/videos', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const data = await response.json().catch(() => null);
      const errors = Array.isArray(data?.detail) ? data.detail : [];
      formError.textContent = errors.map(issue => `${issue.loc?.at(-1)}: ${issue.msg}`).join(' ')
        || 'Could not create the video.';
      return;
    }
    videoForm.reset();
    await fetchVideos();
  } catch (error) {
    formError.textContent = error.message;
  }
});

fetchVideos().catch(error => { formError.textContent = error.message; });
