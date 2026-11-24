import { defineConfig } from '@playwright/test';

const browserName = process.env.E2E_BROWSER || 'chromium';
if (browserName !== 'chromium' && browserName !== 'firefox' && browserName !== 'webkit') {
  throw new Error(`Unsupported E2E_BROWSER: ${browserName}`);
}
const artifacts = process.env.E2E_ARTIFACT_DIR;

export default defineConfig({
  testDir: '.',
  testMatch: '*.spec.ts',
  timeout: 180_000,
  workers: 1,
  outputDir: artifacts ? `${artifacts}/${browserName}/test-results` : 'test-results',
  reporter: artifacts ? [
    ['list'],
    ['json', { outputFile: `${artifacts}/${browserName}/results.json` }],
    ['html', { outputFolder: `${artifacts}/${browserName}/html`, open: 'never' }],
  ] : 'list',
  use: {
    baseURL: process.env.BASE_URL || 'http://127.0.0.1:5173',
    browserName,
    trace: 'retain-on-failure',
  },
});
