import { defineConfig, devices } from "@playwright/test";

/**
 * E2E runs against a real Next server. The API is not required for the
 * foundation smoke test; specs that need data mock it with MSW (WEB-04) or run
 * against the compose stack in CI (F-05).
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "desktop",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 900 } },
    },
    { name: "mobile", use: { ...devices["Pixel 7"] } },
  ],
  webServer: {
    command: "pnpm dev",
    url: "http://localhost:3000/today",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
