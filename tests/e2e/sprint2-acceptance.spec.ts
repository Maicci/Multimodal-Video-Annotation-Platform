import { test, expect, type Page } from '@playwright/test';
import { randomUUID } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

type Segment = {
  id: string; title: string; start_frame: number; end_frame: number;
  start_time: number; end_time: number; version: number;
  description: string; audio_description: string;
};

// Read the rendered playheads and media clock together; do not sample React state.
async function sampleSynchronization(page: Page) {
  return page.evaluate(() => {
    const video = document.querySelector('video')!;
    const range = document.querySelector<HTMLInputElement>('input[type="range"]')!;
    const wave = document.querySelector('svg[aria-label="Waveform with segment selection and playback position"] line:last-child')!;
    const timeline = document.querySelector<HTMLElement>('.timeline-playhead')!;
    return {
      video: video.currentTime,
      waveform: Number(wave.getAttribute('x1')) / 1000 * Number(range.max),
      timeline: parseFloat(timeline.style.left) / 100 * video.duration,
      seeking: video.seeking,
    };
  });
}

for (const kind of ['cfr', 'vfr'] as const) {
  test(`Sprint 2 ${kind}: annotator completes, refreshes and resumes without database changes`, async ({ page, request, browser, browserName }, testInfo) => {
    const directory = mkdtempSync(join(tmpdir(), 'sprint2-'));
    const source = join(directory, 'source.mp4');
    const suffix = randomUUID();
    const filename = `e2e-sprint2-${kind}-${suffix}.mp4`;
    const email = `e2e-sprint2-${suffix}@example.com`;
    const password = 'sprint2-acceptance-password';
    let videoId: string | null = null;
    let userId: string | null = null;
    let adminHeaders: Record<string, string> | null = null;
    const pageErrors: string[] = [];
    page.on('pageerror', (error) => pageErrors.push(error.message));

    try {
      // Eight seconds, with an 80 ms audible pulse every second. VFR preserves
      // original timestamps while sampling 10 fps first, then 30 fps after t=4.
      execFileSync('ffmpeg', [
        '-v', 'error', '-f', 'lavfi', '-i', `testsrc2=size=320x180:rate=${kind === 'vfr' ? 30 : 25}:duration=8`,
        '-f', 'lavfi', '-i', "aevalsrc='if(lt(mod(t,1),0.08),0.7*sin(2*PI*200*t),0)':s=16000:d=8",
        ...(kind === 'vfr' ? ['-vf', "select='if(lt(t,4),not(mod(n,3)),1)'", '-fps_mode', 'vfr'] : []),
        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-movflags', '+faststart', '-y', source,
      ]);
      const probe = JSON.parse(execFileSync('ffprobe', [
        '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'frame=best_effort_timestamp_time', '-of', 'json', source,
      ], { encoding: 'utf8' }));
      const reference: number[] = probe.frames.map((frame: { best_effort_timestamp_time: string }) => Number(frame.best_effort_timestamp_time));
      const intervals = [...new Set(reference.slice(1).map((time, i) => (time - reference[i]).toFixed(3)))];
      expect(intervals.length).toBe(kind === 'vfr' ? 2 : 1);

      const login = await request.post('/api/auth/login', { data: {
        email: process.env.TEST_ADMIN_EMAIL || 'admin@example.com',
        password: process.env.TEST_ADMIN_PASSWORD || 'test-password-123',
      } });
      expect(login.ok()).toBe(true);
      adminHeaders = { Authorization: `Bearer ${(await login.json()).access_token}` };
      const createdUser = await request.post('/api/users', { headers: adminHeaders, data: {
        email, password, full_name: 'Sprint 2 Acceptance Annotator', role: 'annotator',
      } });
      expect(createdUser.status()).toBe(201);
      userId = (await createdUser.json()).id;
      const uploaded = await request.post('/api/videos/upload', { headers: adminHeaders, multipart: {
        upload: { name: filename, mimeType: 'video/mp4', buffer: readFileSync(source) },
      } });
      expect(uploaded.status()).toBe(201);
      videoId = (await uploaded.json()).id;
      const base = `/api/videos/${videoId}`;
      await expect.poll(async () => {
        const videos = await (await request.get('/api/videos', { headers: adminHeaders! })).json();
        return videos.find((video: { id: string }) => video.id === videoId)?.status;
      }, { timeout: 120_000 }).toBe('COMPLETED');
      const assigned = await request.post('/api/assignments', { headers: adminHeaders, data: { video_id: videoId, annotator_id: userId } });
      expect(assigned.ok()).toBe(true);

      await page.goto('/');
      await page.getByLabel('Email').fill(email);
      await page.getByLabel('Password').fill(password);
      await page.getByRole('button', { name: 'Sign in', exact: true }).click();
      const assignment = page.locator('.list .row').filter({ hasText: filename });
      await expect(assignment).toContainText('Not started');
      const token = await page.evaluate(() => localStorage.getItem('access_token'));
      const headers = { Authorization: `Bearer ${token}` };
      const timing = await (await request.get(`${base}/timeline`, { headers })).json();
      expect(timing.frame_count).toBe(reference.length);
      for (let i = 0; i < reference.length; i++) expect(timing.boundaries[i]).toBeCloseTo(reference[i], 6);
      const waveform = await (await request.get(`${base}/waveform`, { headers })).json();
      // Check audio-data placement as well as the UI clock: each pulse must be
      // represented in the first 100 ms of its second, with quiet midpoints.
      for (let second = 0; second < 8; second++) {
        const at = (time: number) => Math.floor(time / waveform.duration * waveform.peaks.length);
        expect(Math.max(...waveform.peaks.slice(at(second), at(second + 0.1) + 1))).toBeGreaterThan(0.1);
        expect(waveform.peaks[at(second + 0.5)]).toBeLessThan(0.02);
      }

      await assignment.getByRole('button', { name: 'Start', exact: true }).click();
      const video = page.locator('video');
      await expect.poll(() => video.evaluate((element) => element.readyState)).toBeGreaterThanOrEqual(2);
      await expect(page.getByLabel('Start frame (inclusive)')).toBeVisible();
      const seek = page.getByLabel('Seek audio waveform');
      const seekSamples: Awaited<ReturnType<typeof sampleSynchronization>>[] = [];
      for (const target of [0.5, 2.25, 6.5]) {
        await seek.fill(String(target));
        await expect.poll(() => video.evaluate((element) => Math.abs(element.currentTime - Number(document.querySelector<HTMLInputElement>('input[type="range"]')!.value)))).toBeLessThan(0.02);
        await expect.poll(() => video.evaluate((element) => element.seeking)).toBe(false);
        seekSamples.push(await sampleSynchronization(page));
        expect(Math.abs(seekSamples.at(-1)!.video - target)).toBeLessThan(0.02);
        const expectedFrame = reference.reduce((best, time, i) => time <= target ? i : best, 0);
        await expect(page.locator('.video-controls')).toContainText(`Frame ${expectedFrame}`);
      }
      for (const locator of [page.locator('.frame-timeline'), page.getByRole('img', { name: 'Waveform with segment selection and playback position' })]) {
        await locator.scrollIntoViewIfNeeded();
        const box = (await locator.boundingBox())!;
        await locator.click({ position: { x: box.width * 0.3, y: box.height / 2 } });
        await expect.poll(() => video.evaluate((element) => element.seeking)).toBe(false);
        const sample = await sampleSynchronization(page);
        expect(Math.abs(sample.video - 2.4)).toBeLessThan(0.03);
        seekSamples.push(sample);
      }

      await seek.fill('0.5');
      await page.getByRole('button', { name: 'Play', exact: true }).click();
      await expect.poll(() => video.evaluate((element) => element.paused)).toBe(false);
      const playbackSamples = await page.evaluate(async () => {
        const samples: { video: number; waveform: number; timeline: number }[] = [];
        const started = performance.now();
        await new Promise<void>((resolve) => {
          function sample() {
            const video = document.querySelector('video')!;
            const range = document.querySelector<HTMLInputElement>('input[type="range"]')!;
            const line = document.querySelector('svg[aria-label="Waveform with segment selection and playback position"] line:last-child')!;
            const playhead = document.querySelector<HTMLElement>('.timeline-playhead')!;
            samples.push({ video: video.currentTime, waveform: Number(line.getAttribute('x1')) / 1000 * Number(range.max), timeline: parseFloat(playhead.style.left) / 100 * video.duration });
            if (performance.now() - started >= 3000) resolve();
            else requestAnimationFrame(sample);
          }
          requestAnimationFrame(sample);
        });
        return samples;
      });
      await page.getByRole('button', { name: 'Pause', exact: true }).click();
      const maximumErrorMs = (samples: typeof playbackSamples) => Math.max(...samples.flatMap((s) => [Math.abs(s.video - s.waveform), Math.abs(s.video - s.timeline)])) * 1000;
      const metrics = { browser: browserName, version: browser.version(), kind, frameCount: reference.length, frameIntervalsSeconds: intervals, sampleCount: playbackSamples.length, seekMaxErrorMs: maximumErrorMs(seekSamples), playbackMaxErrorMs: maximumErrorMs(playbackSamples), playbackSamples };
      await testInfo.attach('synchronization.json', { body: JSON.stringify(metrics, null, 2), contentType: 'application/json' });
      console.log(`SYNC ${JSON.stringify({ ...metrics, playbackSamples: undefined })}`);

      await page.getByRole('button', { name: '+ New segment' }).click();
      await page.getByLabel('Title', { exact: true }).fill('Acceptance scene');
      await page.getByLabel('Start frame (inclusive)').fill('10');
      await page.getByLabel('End frame (exclusive)').fill('10');
      await page.getByRole('button', { name: 'Save segment', exact: true }).click();
      await expect(page.getByRole('alert')).toContainText('valid time range');
      expect(await (await request.get(`${base}/segments`, { headers })).json()).toEqual([]);
      const endFrame = reference.length - 5;
      await page.getByLabel('End frame (exclusive)').fill(String(endFrame));
      await page.getByLabel('Video description').fill('A moving test pattern is visible.');
      await page.getByLabel('Audio description').fill('A short tone repeats every second.');
      async function save(): Promise<Segment> {
        const response = page.waitForResponse((r) => r.url().includes(`${base}/segments`) && ['POST', 'PUT'].includes(r.request().method()));
        await page.getByRole('button', { name: 'Save segment', exact: true }).click();
        const saved = await response;
        expect(saved.ok()).toBe(true);
        await expect(page.getByRole('status').filter({ hasText: 'Segment saved.' })).toBeVisible();
        return saved.json();
      }
      let segment = await save();
      const valid = { title: 'Invalid attempt', start_time: reference[10], end_time: reference[endFrame] };
      for (const invalid of [
        { ...valid, start_time: -1 }, { ...valid, end_time: valid.start_time },
        { ...valid, end_time: 100 }, { ...valid, start_frame: 0 },
        { ...valid, start_time: reference[10] + 0.001, end_time: reference[10] + 0.002 },
      ]) {
        const rejected = await request.post(`${base}/segments`, { headers, data: invalid });
        expect(rejected.status()).toBe(422);
      }
      for (let edit = 1; edit <= 6; edit++) {
        await page.getByLabel('Title', { exact: true }).fill(`Acceptance scene edit ${edit}`);
        await page.getByLabel('Start (seconds)').fill(String(reference[10] + 0.001));
        segment = await save();
        expect(segment.start_frame).toBe(10);
        expect(segment.end_frame).toBe(endFrame);
        expect(segment.start_time).toBeCloseTo(reference[10], 6);
        expect(segment.end_time).toBeCloseTo(reference[endFrame], 6);
      }
      expect(await (await request.get(`${base}/segments`, { headers })).json()).toHaveLength(1);

      await page.getByRole('button', { name: 'Mark complete' }).click();
      await expect(page.getByRole('status').filter({ hasText: 'whole-video summary before completing' })).toBeVisible();
      await page.getByLabel('Video summary').fill('An eight-second test pattern with regular audio pulses.');
      await expect(page.getByRole('button', { name: 'Mark complete' })).toBeDisabled();
      await page.getByRole('button', { name: 'Save summary', exact: true }).click();
      await expect(page.getByRole('status').filter({ hasText: 'Summary saved.' })).toBeVisible();

      // Create and remove a second segment; leave the first intact for resume.
      await page.getByRole('button', { name: '+ New segment' }).click();
      await page.getByLabel('Title', { exact: true }).fill('Disposable scene');
      await page.getByLabel('Start frame (inclusive)').fill('1');
      await page.getByLabel('End frame (exclusive)').fill('3');
      await save();
      page.once('dialog', (dialog) => dialog.accept());
      await page.getByRole('button', { name: 'Delete segment' }).click();
      await expect(page.getByRole('status').filter({ hasText: 'Segment deleted.' })).toBeVisible();
      await expect(page.locator('.segment-item')).toHaveCount(1);

      async function verifyResumed() {
        await expect(page.getByLabel('Title', { exact: true })).toHaveValue(segment.title);
        await expect(page.getByLabel('Video description')).toHaveValue('A moving test pattern is visible.');
        await expect(page.getByLabel('Audio description')).toHaveValue('A short tone repeats every second.');
        await expect(page.getByLabel('Video summary')).toHaveValue('An eight-second test pattern with regular audio pulses.');
        await expect(page.getByLabel('Start frame (inclusive)')).toHaveValue('10');
        await expect(page.getByLabel('End frame (exclusive)')).toHaveValue(String(endFrame));
      }
      await page.getByRole('button', { name: 'Back to videos' }).click();
      await expect(assignment).toContainText('In progress');
      await assignment.getByRole('button', { name: 'Continue', exact: true }).click();
      await verifyResumed();
      await page.reload();
      await assignment.getByRole('button', { name: 'Continue', exact: true }).click();
      await verifyResumed();
      await page.getByRole('button', { name: 'Back to videos' }).click();
      await page.getByRole('button', { name: 'Sign out' }).click();
      await page.getByLabel('Email').fill(email);
      await page.getByLabel('Password').fill(password);
      await page.getByRole('button', { name: 'Sign in', exact: true }).click();
      await assignment.getByRole('button', { name: 'Continue', exact: true }).click();
      await verifyResumed();
      await page.getByRole('button', { name: 'Mark complete' }).click();
      await expect(page.getByText('Annotation: completed', { exact: true })).toBeVisible();
      await expect(page.getByRole('button', { name: 'Mark complete' })).toBeDisabled();
      await page.screenshot({ path: testInfo.outputPath('completed-workspace.png'), fullPage: true });
      await page.getByRole('button', { name: 'Back to videos' }).click();
      await expect(assignment).toContainText('Completed');
      await assignment.getByRole('button', { name: 'Review', exact: true }).click();
      await verifyResumed();
      await expect(page.getByText('Annotation: completed', { exact: true })).toBeVisible();
      await page.setViewportSize({ width: 869, height: 1058 });
      await page.emulateMedia({ colorScheme: 'dark' });
      await page.screenshot({ path: testInfo.outputPath('narrow-workspace.png'), fullPage: true });
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
      expect(pageErrors).toEqual([]);
      expect(metrics.seekMaxErrorMs).toBeLessThanOrEqual(50);
      expect(playbackSamples.length).toBeGreaterThan(30);
      expect(playbackSamples.at(-1)!.video - playbackSamples[0].video).toBeGreaterThan(2.5);
      expect(metrics.playbackMaxErrorMs).toBeLessThanOrEqual(100);
    } finally {
      try {
        if (adminHeaders && videoId) expect((await request.delete(`/api/videos/${videoId}`, { headers: adminHeaders })).status()).toBe(204);
        if (adminHeaders && userId) expect((await request.delete(`/api/users/${userId}`, { headers: adminHeaders })).status()).toBe(204);
      } finally {
        rmSync(directory, { recursive: true, force: true });
      }
    }
  });
}
