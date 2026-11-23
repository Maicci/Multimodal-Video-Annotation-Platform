import { test, expect } from '@playwright/test';
import { randomUUID } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

test('upload, play, annotate, reload, edit, and delete a video', async ({ page, request }) => {
  const tempDir = mkdtempSync(join(tmpdir(), 'video-e2e-'));
  const localVideo = join(tempDir, 'sample.mp4');
  const filename = `e2e-${randomUUID()}.mp4`;
  let token: string | null = null;

  try {
    execFileSync('ffmpeg', [
      '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=size=160x90:rate=10',
      '-t', '3', '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
      '-movflags', '+faststart', '-y', localVideo,
    ]);

    await page.goto('/');
    await expect(page.getByLabel('Email')).toBeVisible({ timeout: 10_000 });
    await page.getByLabel('Email').fill(process.env.TEST_ADMIN_EMAIL || 'admin@example.com');
    await page.getByLabel('Password').fill(process.env.TEST_ADMIN_PASSWORD || 'test-password-123');
    await page.getByRole('button', { name: 'Sign in' }).click();
    await expect(page.getByRole('heading', { name: 'Videos', exact: true })).toBeVisible();
    token = await page.evaluate(() => localStorage.getItem('access_token'));

    await page.locator('input[type="file"]').setInputFiles({
      name: filename, mimeType: 'video/mp4', buffer: readFileSync(localVideo),
    });
    await page.route('**/api/videos/upload', async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 500));
      await route.continue();
    }, { times: 1 });
    const uploadResponse = page.waitForResponse(
      (response) => response.url().endsWith('/api/videos/upload') && response.request().method() === 'POST',
    );
    await page.getByRole('button', { name: 'Upload', exact: true }).click();
    await expect(page.getByRole('progressbar', { name: 'Video upload progress' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Uploading...' })).toBeDisabled();
    const uploaded = await uploadResponse;
    expect(uploaded.status()).toBe(201);
    expect((await uploaded.json()).id).toBeTruthy();
    await expect(page.getByRole('status')).toContainText(`Video "${filename}" uploaded successfully.`);

    const row = page.getByRole('row').filter({ hasText: filename });
    await expect(row).toBeVisible();
    await expect(row.locator('.video-status')).toHaveText('COMPLETED', { timeout: 120_000 });

    await page.locator('input[type="file"]').setInputFiles({
      name: filename, mimeType: 'video/mp4', buffer: readFileSync(localVideo),
    });
    const duplicateResponse = page.waitForResponse(
      (response) => response.url().endsWith('/api/videos/upload') && response.request().method() === 'POST',
    );
    await page.getByRole('button', { name: 'Upload', exact: true }).click();
    expect((await duplicateResponse).status()).toBe(409);
    await expect(page.getByRole('alert')).toHaveText('Video with same filename already exists');

    await row.getByRole('button', { name: 'View' }).click();

    await expect(page.locator('video')).toBeVisible();
    await expect.poll(async () => page.locator('video').evaluate(
      (element) => (element as HTMLVideoElement).duration,
    )).toBeGreaterThan(2);
    const thumbnails = page.locator('.thumbnail-strip img');
    await expect(thumbnails).toHaveCount(12);
    await expect.poll(async () => thumbnails.evaluateAll(
      (images) => images.every((image) =>
        (image as HTMLImageElement).complete && (image as HTMLImageElement).naturalWidth > 0),
    )).toBe(true);

    await page.getByRole('button', { name: '+ New segment' }).click();
    await page.getByLabel('Title').fill('Opening scene');
    await page.getByLabel('Video description').fill('A test pattern appears.');
    await page.getByLabel('Audio description').fill('A steady test tone plays.');

    await page.locator('.frame-timeline').scrollIntoViewIfNeeded();
    const timelineBox = await page.locator('.frame-timeline').boundingBox();
    const startBox = await page.locator('.start-handle').boundingBox();
    const endBox = await page.locator('.end-handle').boundingBox();
    if (!timelineBox || !startBox || !endBox) throw new Error('Timeline handles are missing');
    await page.mouse.move(startBox.x + startBox.width / 2, startBox.y + startBox.height / 2);
    await page.mouse.down();
    await page.mouse.move(timelineBox.x + timelineBox.width * 0.25, startBox.y + startBox.height / 2, { steps: 5 });
    await page.mouse.up();
    await page.mouse.move(endBox.x + endBox.width / 2, endBox.y + endBox.height / 2);
    await page.mouse.down();
    await page.mouse.move(timelineBox.x + timelineBox.width * 0.75, endBox.y + endBox.height / 2, { steps: 5 });
    await page.mouse.up();
    const startTime = Number(await page.getByLabel('Start (seconds)').inputValue());
    const endTime = Number(await page.getByLabel('End (seconds)').inputValue());
    expect(startTime).toBeGreaterThan(0.3);
    expect(endTime).toBeGreaterThan(startTime);
    expect(endTime).toBeLessThan(3);

    await page.getByRole('button', { name: 'Save segment' }).click();
    await expect(page.getByRole('status')).toHaveText('Segment saved.');
    await page.getByLabel('Video summary').fill('A short test pattern video.');
    await page.getByRole('button', { name: 'Save summary' }).click();
    await expect(page.getByRole('status').filter({ hasText: 'Summary saved.' })).toBeVisible();
    await page.reload();
    await expect(page.getByRole('heading', { name: 'Videos', exact: true })).toBeVisible();
    await page.getByRole('row').filter({ hasText: filename }).getByRole('button', { name: 'View' }).click();
    await expect(page.getByLabel('Title')).toHaveValue('Opening scene');
    await expect(page.getByLabel('Video description')).toHaveValue('A test pattern appears.');
    await expect(page.getByLabel('Audio description')).toHaveValue('A steady test tone plays.');
    await expect(page.getByLabel('Video summary')).toHaveValue('A short test pattern video.');
    await expect(page.getByLabel('Start (seconds)')).toHaveValue(String(startTime));

    await page.getByLabel('Title').fill('Edited opening');
    await page.getByRole('button', { name: 'Save segment' }).click();
    await expect(page.getByRole('status')).toHaveText('Segment saved.');
    await page.reload();
    await page.getByRole('row').filter({ hasText: filename }).getByRole('button', { name: 'View' }).click();
    await expect(page.getByLabel('Title')).toHaveValue('Edited opening');

    page.once('dialog', (dialog) => dialog.accept());
    await page.getByRole('button', { name: 'Delete segment' }).click();
    await expect(page.getByText('No saved segments yet.')).toBeVisible();
  } finally {
    try {
      if (token) {
        const headers = { Authorization: `Bearer ${token}` };
        const listed = await request.get('/api/videos', { headers });
        if (!listed.ok()) throw new Error(`Could not list test uploads (${listed.status()})`);
        const videos = await listed.json() as Array<{ id: string; filename: string }>;
        const uploadedVideo = videos.find((video) => video.filename === filename);
        if (uploadedVideo) {
          const deleted = await request.delete(`/api/videos/${uploadedVideo.id}`, { headers });
          if (deleted.status() !== 204) {
            throw new Error(`Could not remove test upload (${deleted.status()})`);
          }
        }
      }
    } finally {
      rmSync(tempDir, { recursive: true, force: true });
    }
  }
});

test('rejects an unsupported file before upload', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Email').fill(process.env.TEST_ADMIN_EMAIL || 'admin@example.com');
  await page.getByLabel('Password').fill(process.env.TEST_ADMIN_PASSWORD || 'test-password-123');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('heading', { name: 'Videos', exact: true })).toBeVisible();

  await page.locator('input[type="file"]').setInputFiles({
    name: 'document.pdf', mimeType: 'application/pdf', buffer: Buffer.from('not a video'),
  });
  await expect(page.getByRole('alert')).toHaveText('Only MP4 and MOV files are supported.');
  await expect(page.getByRole('button', { name: 'Upload', exact: true })).toBeDisabled();
});
