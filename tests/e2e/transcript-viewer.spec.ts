import { test, expect } from '@playwright/test';
import { randomUUID } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

test('admin verifies transcript against playback, including empty and failed responses', async ({ page, request }) => {
  const tempDir = mkdtempSync(join(tmpdir(), 'transcript-e2e-'));
  const localVideo = join(tempDir, 'sample.mp4');
  const filename = `e2e-transcript-${randomUUID()}.mp4`;
  const jobId = randomUUID();
  let videoId: string | null = null;
  let token: string | null = null;
  let transcriptState: 'ready' | 'empty' | 'error' = 'ready';

  try {
    execFileSync('ffmpeg', [
      '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=size=160x90:rate=10',
      '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=16000',
      '-t', '3', '-c:a', 'aac', '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
      '-movflags', '+faststart', '-y', localVideo,
    ]);
    const login = await request.post('/api/auth/login', { data: {
      email: process.env.TEST_ADMIN_EMAIL || 'admin@example.com',
      password: process.env.TEST_ADMIN_PASSWORD || 'test-password-123',
    } });
    expect(login.ok()).toBe(true);
    token = (await login.json()).access_token;
    const headers = { Authorization: `Bearer ${token}` };
    const uploaded = await request.post('/api/videos/upload', { headers, multipart: {
      upload: { name: filename, mimeType: 'video/mp4', buffer: readFileSync(localVideo) },
    } });
    expect(uploaded.status()).toBe(201);
    videoId = (await uploaded.json()).id;
    await expect.poll(async () => {
      const response = await request.get('/api/videos', { headers });
      const videos = await response.json() as Array<{ id: string; status: string }>;
      return videos.find((video) => video.id === videoId)?.status;
    }, { timeout: 120_000 }).toBe('COMPLETED');

    // Keep the model output deterministic; authentication, upload and media are real.
    await page.route('**/api/videos', async (route) => {
      const response = await route.fetch();
      const videos = await response.json() as Array<{ id: string }>;
      await route.fulfill({ response, json: videos.map((video) => video.id === videoId
        ? { ...video, transcription_status: 'COMPLETED', transcription_job_id: jobId }
        : video) });
    });
    await page.route(`**/api/processing/jobs/${jobId}`, async (route) => {
      if (transcriptState === 'error') {
        await route.fulfill({ status: 503, json: { detail: 'Temporarily unavailable' } });
      } else {
        await route.fulfill({ json: {
          id: jobId, status: 'COMPLETED', model: 'tiny', error: null,
          result: { language: 'en', segments: transcriptState === 'empty' ? [] : [
            { start_seconds: 1, end_seconds: 2.5, text: 'Example recognized words.' },
          ] },
        } });
      }
    });
    await page.addInitScript((accessToken) => localStorage.setItem('access_token', accessToken!), token);
    await page.goto('/');
    const row = page.getByRole('row').filter({ hasText: filename });
    const openTranscript = row.getByRole('button', { name: 'View transcript', exact: true });
    await openTranscript.click();
    const dialog = page.getByRole('dialog', { name: 'Automatic transcript' });
    await expect(dialog).toBeVisible();
    await expect(dialog).toContainText('Example recognized words.');
    await expect(dialog).toContainText('Model: tiny · Language: en');
    const player = dialog.locator('video');
    await expect.poll(() => player.evaluate((video) => video.readyState)).toBeGreaterThanOrEqual(1);
    await dialog.getByRole('button', { name: 'Play from 00:01.000' }).click();
    await expect.poll(() => player.evaluate((video) => video.currentTime)).toBeGreaterThanOrEqual(1);
    await expect.poll(() => player.evaluate((video) => video.paused)).toBe(false);
    await page.keyboard.press('Escape');
    await expect(dialog).toHaveCount(0);
    await expect(openTranscript).toBeFocused();

    // At a narrow viewport the modal should remain usable without horizontal scrolling.
    await page.setViewportSize({ width: 390, height: 844 });
    await openTranscript.click();
    await expect(dialog).toContainText('Example recognized words.');
    expect(await dialog.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
    const bounds = await dialog.boundingBox();
    expect(bounds!.x).toBeGreaterThanOrEqual(0);
    expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(390);
    await dialog.getByRole('button', { name: 'Close transcript' }).click();

    transcriptState = 'empty';
    await openTranscript.click();
    await expect(dialog).toContainText('No speech was recognized in this video.');
    await expect(dialog.getByRole('list', { name: 'Transcript passages' })).toHaveCount(0);
    await dialog.getByRole('button', { name: 'Close transcript' }).click();

    transcriptState = 'error';
    await openTranscript.click();
    await expect(dialog.getByRole('alert')).toContainText('Could not load transcript (503)');
    await expect(dialog).not.toContainText('Example recognized words.');
    await dialog.getByRole('button', { name: 'Close transcript' }).click();

    // Verify the frontend role gate separately from the backend role tests.
    await page.route('**/api/auth/me', async (route) => {
      const response = await route.fetch();
      await route.fulfill({ response, json: { ...await response.json(), role: 'reviewer' } });
    });
    await page.reload();
    await expect(page.getByRole('heading', { name: 'Annotation reviews', exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Transcribe audio' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'View transcript' })).toHaveCount(0);
  } finally {
    try {
      if (videoId && token) {
        const deleted = await request.delete(`/api/videos/${videoId}`, { headers: { Authorization: `Bearer ${token}` } });
        expect(deleted.status()).toBe(204);
      }
    } finally {
      rmSync(tempDir, { recursive: true, force: true });
    }
  }
});
