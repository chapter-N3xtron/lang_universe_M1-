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
    baseURL: "http://127.0.0.1:3101",
    headless: true,
  },
  webServer: {
    command: "./node_modules/.bin/next start -p 3101",
    url: "http://127.0.0.1:3101",
    reuseExistingServer: false,
  },
});
