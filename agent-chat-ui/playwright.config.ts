import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  timeout: 30000,
  retries: 0,
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  use: {
    baseURL: "http://127.0.0.1:3001",
    headless: true,
  },
  webServer: {
    command: "pnpm dev --port 3001",
    url: "http://127.0.0.1:3001",
    reuseExistingServer: true,
  },
});
