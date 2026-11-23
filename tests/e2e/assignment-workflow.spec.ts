import { test, expect } from '@playwright/test';
import { randomUUID } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

test('administrator approves and assigns a video that the annotator can annotate', async ({ page, request }) => {
  const tempDir = mkdtempSync(join(tmpdir(), 'assignment-e2e-'));
  const localVideo = join(tempDir, 'sample.mp4');
  const suffix = randomUUID();
  const email = `e2e-annotator-${suffix}@example.com`;
  const password = 'assignment-test-password-123';
  const filename = `e2e-assignment-${suffix}.mp4`;
  let adminToken: string | null = null;
  let userId: string | null = null;
  let videoId: string | null = null;

  try {
    execFileSync('ffmpeg', [
      '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=size=160x90:rate=10',
      '-t', '3', '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
      '-movflags', '+faststart', '-y', localVideo,
    ]);

    await page.goto('/');
    await page.getByRole('button', { name: "Don't have an account? Register" }).click();
    await page.getByLabel('Full name').fill('Assignment Test Annotator');
    await page.getByLabel('Email').fill(email);
    await page.getByLabel('Password').fill(password);
    await page.getByRole('button', { name: 'Register', exact: true }).click();
    await expect(page.getByText('Registration successful. Your account is waiting for administrator approval.')).toBeVisible();

    await page.getByRole('button', { name: 'Already have an account? Sign in' }).click();
    await page.getByLabel('Email').fill(process.env.TEST_ADMIN_EMAIL || 'admin@example.com');
    await page.getByLabel('Password').fill(process.env.TEST_ADMIN_PASSWORD || 'test-password-123');
    await page.getByRole('button', { name: 'Sign in' }).click();
    await expect(page.getByRole('heading', { name: 'Videos', exact: true })).toBeVisible();
    adminToken = await page.evaluate(() => localStorage.getItem('access_token'));
    expect(adminToken).toBeTruthy();

    const headers = { Authorization: `Bearer ${adminToken}` };
    const usersResponse = await request.get('/api/users/pending', { headers });
    expect(usersResponse.ok()).toBe(true);
    userId = (await usersResponse.json() as Array<{ id: string; email: string }>).find((user) => user.email === email)?.id || null;
    expect(userId).toBeTruthy();

    await page.getByRole('button', { name: 'Pending users' }).click();
    const pendingRow = page.getByRole('row').filter({ hasText: email });
    await expect(pendingRow).toBeVisible();
    await pendingRow.getByRole('button', { name: 'Approve' }).click();
    await expect(page.getByText(`Approved ${email}`)).toBeVisible();
    await page.getByRole('button', { name: 'Close pending users' }).click();

    await page.locator('input[type="file"]').setInputFiles({
      name: filename, mimeType: 'video/mp4', buffer: readFileSync(localVideo),
    });
    const uploadResponse = page.waitForResponse(
      (response) => response.url().endsWith('/api/videos/upload') && response.request().method() === 'POST',
    );
    await page.getByRole('button', { name: 'Upload', exact: true }).click();
    const uploaded = await uploadResponse;
    expect(uploaded.status()).toBe(201);
    videoId = (await uploaded.json()).id;

    const videoRow = page.getByRole('row').filter({ hasText: filename });
    await expect(videoRow).toBeVisible();
    await expect(videoRow.locator('.video-status')).toHaveText('COMPLETED', { timeout: 120_000 });
    await videoRow.getByRole('button', { name: 'Assign' }).click();
    await expect(page.getByText('Type a name or email to find someone to assign.')).toBeVisible();
    await expect(page.getByRole('list', { name: 'Search results' })).toHaveCount(0);
    const annotatorSearch = page.getByLabel('Find annotator');
    await annotatorSearch.fill('no-such-annotator@example.com');
    await expect(page.getByText('No matching annotators.')).toBeVisible();
    await expect(page.locator('.modal-backdrop').getByRole('button', { name: 'Assign', exact: true })).toBeDisabled();
    await annotatorSearch.fill(email.slice(0, 20));
    await page.getByRole('list', { name: 'Search results' }).getByRole('button', { name: new RegExp(email) }).click();
    await expect(page.getByText(`Selected: Assignment Test Annotator (${email})`)).toBeVisible();
    const assignmentRequest = page.waitForRequest(
      (request) => request.url().endsWith('/api/assignments') && request.method() === 'POST',
    );
    await page.locator('.modal-backdrop').getByRole('button', { name: 'Assign', exact: true }).click();
    expect((await assignmentRequest).postDataJSON().annotator_id).toBe(userId);
    await expect(page.getByText('Video assigned successfully.')).toBeVisible();
    await page.getByRole('button', { name: 'Close assign video' }).click();
    await page.getByRole('button', { name: 'Sign out' }).click();

    await page.getByLabel('Email').fill(email);
    await page.getByLabel('Password').fill(password);
    await page.getByRole('button', { name: 'Sign in' }).click();
    await expect(page.getByRole('heading', { name: 'Your videos' })).toBeVisible();
    const assignment = page.locator('.list .row').filter({ hasText: filename });
    await expect(assignment).toContainText('Not started');
    await assignment.getByRole('button', { name: 'Start' }).click();
    await expect(page.locator('video')).toBeVisible();
    await expect.poll(async () => page.locator('video').evaluate(
      (element) => (element as HTMLVideoElement).duration,
    )).toBeGreaterThan(2);

    await page.getByRole('button', { name: '+ New segment' }).click();
    await page.getByLabel('Title').fill('First scene');
    await page.getByLabel('Description').fill('The test video begins.');
    await page.getByRole('button', { name: 'Save segment' }).click();
    await expect(page.getByRole('status')).toHaveText('Segment saved.');
    await page.getByRole('button', { name: 'Back to videos' }).click();
    await expect(page.locator('.list .row').filter({ hasText: filename })).toContainText('In progress');
    await expect(page.locator('.list .row').filter({ hasText: filename })).toContainText('1 segment');
  } finally {
    try {
      if (!adminToken) {
        const login = await request.post('/api/auth/login', {
          data: {
            email: process.env.TEST_ADMIN_EMAIL || 'admin@example.com',
            password: process.env.TEST_ADMIN_PASSWORD || 'test-password-123',
          },
        });
        if (login.ok()) adminToken = (await login.json()).access_token;
      }
      if (adminToken) {
        const headers = { Authorization: `Bearer ${adminToken}` };
        if (!videoId) {
          const listed = await request.get('/api/videos', { headers });
          if (listed.ok()) {
            videoId = (await listed.json() as Array<{ id: string; filename: string }>).find(
              (video) => video.filename === filename,
            )?.id || null;
          }
        }
        if (!userId) {
          const listed = await request.get('/api/users', { headers });
          if (listed.ok()) {
            userId = (await listed.json() as Array<{ id: string; email: string }>).find(
              (user) => user.email === email,
            )?.id || null;
          }
        }
        if (videoId) {
          const deleted = await request.delete(`/api/videos/${videoId}`, { headers });
          if (deleted.status() !== 204) throw new Error(`Could not remove test video (${deleted.status()})`);
        }
        if (userId) {
          const deleted = await request.delete(`/api/users/${userId}`, { headers });
          if (deleted.status() !== 204) throw new Error(`Could not remove test user (${deleted.status()})`);
        }
      }
    } finally {
      rmSync(tempDir, { recursive: true, force: true });
    }
  }
});
