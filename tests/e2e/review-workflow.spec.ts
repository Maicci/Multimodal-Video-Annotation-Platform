import { test, expect, type Page } from '@playwright/test';
import { randomUUID } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

test('annotator submits, reviewer returns, annotator resubmits, reviewer approves', async ({ page, request, browser }, testInfo) => {
  const directory = mkdtempSync(join(tmpdir(), 'review-e2e-'));
  const source = join(directory, 'source.mp4');
  const suffix = randomUUID();
  const filename = `e2e-review-${suffix}.mp4`;
  const authorEmail = `e2e-author-${suffix}@example.com`;
  const reviewerEmail = `e2e-reviewer-${suffix}@example.com`;
  const password = 'review-workflow-password';
  const users: string[] = [];
  let videoId: string | null = null;
  let adminHeaders: Record<string, string> | null = null;
  const reviewerContext = await browser.newContext({ baseURL: process.env.BASE_URL || 'http://127.0.0.1:5173' });
  const reviewerPage = await reviewerContext.newPage();
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  reviewerPage.on('pageerror', (error) => errors.push(error.message));

  async function login(target: Page, email: string) {
    await target.goto('/');
    await target.getByLabel('Email', { exact: true }).fill(email);
    await target.getByLabel('Password', { exact: true }).fill(password);
    await target.getByRole('button', { name: 'Sign in', exact: true }).click();
  }

  try {
    execFileSync('ffmpeg', ['-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=size=160x90:rate=10',
      '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=16000', '-t', '3',
      '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-movflags', '+faststart', '-y', source]);
    const loginResponse = await request.post('/api/auth/login', { data: {
      email: process.env.TEST_ADMIN_EMAIL || 'admin@example.com', password: process.env.TEST_ADMIN_PASSWORD || 'test-password-123',
    } });
    expect(loginResponse.ok()).toBe(true);
    adminHeaders = { Authorization: `Bearer ${(await loginResponse.json()).access_token}` };
    for (const [email, role] of [[authorEmail, 'annotator'], [reviewerEmail, 'reviewer']]) {
      const response = await request.post('/api/users', { headers: adminHeaders, data: { email, role, password, full_name: `Review test ${role}` } });
      expect(response.status()).toBe(201);
      users.push((await response.json()).id);
    }
    const upload = await request.post('/api/videos/upload', { headers: adminHeaders, multipart: {
      upload: { name: filename, mimeType: 'video/mp4', buffer: readFileSync(source) },
    } });
    expect(upload.status()).toBe(201);
    videoId = (await upload.json()).id;
    await expect.poll(async () => {
      const videos = await (await request.get('/api/videos', { headers: adminHeaders! })).json();
      return videos.find((video: { id: string }) => video.id === videoId)?.status;
    }, { timeout: 120_000 }).toBe('COMPLETED');
    expect((await request.post('/api/assignments', { headers: adminHeaders, data: { video_id: videoId, annotator_id: users[0] } })).ok()).toBe(true);

    await login(page, authorEmail);
    const assignment = page.locator('.list .row').filter({ hasText: filename });
    await assignment.getByRole('button', { name: 'Start', exact: true }).click();
    await expect(page.getByRole('button', { name: 'Skip for now' })).toBeEnabled();
    await page.getByLabel('Reason for skipping (optional)').fill('Listen again later.');
    await page.getByRole('button', { name: 'Skip for now' }).click();
    await expect(page.getByRole('heading', { name: 'Skipped', exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Back to videos' }).click();
    await expect(assignment).toContainText('Skipped');
    await assignment.getByRole('button', { name: 'Resume', exact: true }).click();
    await page.getByRole('button', { name: '+ New segment' }).click();
    await page.getByLabel('Title', { exact: true }).fill('Opening');
    await page.getByLabel('Video description').fill('A moving pattern appears.');
    await page.getByLabel('Audio description').fill('A sound is audible.');
    await page.getByRole('button', { name: 'Save segment', exact: true }).click();
    await expect(page.getByRole('status').filter({ hasText: 'Segment saved.' })).toBeVisible();
    await page.getByLabel('Video summary').fill('A short pattern and tone.');
    await expect(page.getByRole('button', { name: 'Submit for review', exact: true })).toBeDisabled();
    await page.getByRole('button', { name: 'Save summary', exact: true }).click();
    await expect(page.getByRole('status').filter({ hasText: 'Summary saved.' })).toBeVisible();
    page.once('dialog', (dialog) => dialog.accept());
    await page.getByRole('button', { name: 'Submit for review', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Submitted', exact: true })).toBeVisible();
    await expect(page.getByLabel('Video description')).toBeDisabled();
    await expect(page.getByRole('button', { name: 'Delete segment' })).toBeDisabled();
    await expect(page.locator('.selection-handle')).toHaveCount(0);

    await login(reviewerPage, reviewerEmail);
    await expect(reviewerPage.getByRole('heading', { name: 'Annotation reviews', exact: true })).toBeVisible();
    const queueRow = reviewerPage.locator('.review-queue li').filter({ hasText: filename });
    await queueRow.getByRole('button', { name: 'Review submission' }).click();
    await expect(reviewerPage.getByRole('region', { name: 'Submitted segments' })).toContainText('A moving pattern appears.');
    await expect(reviewerPage.getByRole('region', { name: 'Submitted summary' })).toContainText('A short pattern and tone.');
    await expect(reviewerPage.getByRole('button', { name: 'Save segment', exact: true })).toHaveCount(0);
    await expect.poll(() => reviewerPage.locator('video').evaluate((video) => video.readyState)).toBeGreaterThanOrEqual(1);
    await reviewerPage.getByRole('button', { name: 'Play from 0.00 s' }).click();
    await expect.poll(() => reviewerPage.locator('video').evaluate((video) => video.paused)).toBe(false);
    await reviewerPage.getByRole('button', { name: 'Return for changes' }).click();
    await expect(reviewerPage.getByRole('alert')).toContainText('Add a comment');
    await reviewerPage.getByLabel('Review comment').fill('Please name the sound in the audio description.');
    await reviewerPage.getByRole('button', { name: 'Return for changes' }).click();
    await expect(reviewerPage.getByRole('status')).toHaveText('Review status: returned');

    await page.reload();
    await expect(assignment).toContainText('Returned for changes');
    await assignment.getByRole('button', { name: 'Revise', exact: true }).click();
    await expect(page.getByRole('region', { name: 'Review history' })).toContainText('Please name the sound');
    await page.getByLabel('Audio description').fill('A steady 440 Hz tone plays.');
    await expect(page.getByRole('button', { name: 'Resubmit for review', exact: true })).toBeDisabled();
    await page.getByRole('button', { name: 'Save segment', exact: true }).click();
    await expect(page.getByRole('status').filter({ hasText: 'Segment saved.' })).toBeVisible();
    page.once('dialog', (dialog) => dialog.accept());
    await page.getByRole('button', { name: 'Resubmit for review', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Submitted', exact: true })).toBeVisible();
    await reviewerPage.getByRole('button', { name: 'Back to review queue' }).click();
    await queueRow.getByRole('button', { name: 'Review submission' }).click();
    await expect(reviewerPage.getByRole('region', { name: 'Submitted segments' })).toContainText('A steady 440 Hz tone plays.');
    await reviewerPage.getByLabel('Review comment').fill('Descriptions are clear now.');
    await reviewerPage.getByRole('button', { name: 'Approve annotation' }).click();
    await expect(reviewerPage.getByRole('status')).toHaveText('Review status: approved');
    await reviewerPage.reload();
    await queueRow.getByRole('button', { name: 'View review' }).click();
    const history = reviewerPage.getByRole('region', { name: 'Review history' });
    await expect(history.locator('li')).toHaveCount(5);
    await expect(history).toContainText('Please name the sound');
    await expect(history).toContainText('Descriptions are clear now.');
    await expect(reviewerPage.getByRole('button', { name: 'Approve annotation' })).toHaveCount(0);
    const screenshot = testInfo.outputPath('approved-review.png');
    await reviewerPage.screenshot({ path: screenshot, fullPage: true });
    await testInfo.attach('Approved review', { path: screenshot, contentType: 'image/png' });

    await page.reload();
    await expect(assignment).toContainText('Approved');
    await assignment.getByRole('button', { name: 'View', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Approved', exact: true })).toBeVisible();
    await expect(page.getByLabel('Audio description')).toHaveValue('A steady 440 Hz tone plays.');
    await expect(page.getByLabel('Audio description')).toBeDisabled();
    await expect(page.getByLabel('Video summary')).toBeDisabled();
    expect(errors).toEqual([]);
  } finally {
    await reviewerContext.close();
    try {
      if (adminHeaders && videoId) expect((await request.delete(`/api/videos/${videoId}`, { headers: adminHeaders })).status()).toBe(204);
      if (adminHeaders) for (const userId of users) expect((await request.delete(`/api/users/${userId}`, { headers: adminHeaders })).status()).toBe(204);
    } finally { rmSync(directory, { recursive: true, force: true }); }
  }
});
