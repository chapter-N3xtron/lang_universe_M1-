import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  testMatch: "manual-scroll-observation.spec.ts",
  timeout: 30000,
  retries: 0,
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  use: {
    baseURL: "http://127.0.0.1:3102",
    headless: true,
    acceptDownloads: true,
  },
  webServer: {
    command: "./node_modules/.bin/next dev -p 3102",
    url: "http://127.0.0.1:3102",
    reuseExistingServer: false,
  },
});
