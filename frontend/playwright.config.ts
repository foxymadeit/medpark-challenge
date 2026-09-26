import { defineConfig, devices } from "@playwright/test";

// Real mode (no demo store), production build. Two ways to run it:
//   npm run build && npm run e2e
//     against tests/e2e/mock-server.mjs, which follows API_CONTRACT.md;
//   E2E_BACKEND=../backend E2E_PYTHON=../backend/.venv/bin/python npm run e2e
//     against the real backend (romans-branch) with its fake pipeline stages
//     and a local SMTP catcher (tests/e2e/real-backend.sh).
const real = Boolean(process.env.E2E_BACKEND);
const port = real ? 8000 : 4173;

export default defineConfig({
  testDir: "tests/e2e",
  timeout: 60_000,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  outputDir: process.env.PW_OUTPUT ?? "/tmp/liminal-playwright",
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    trace: "off",
    video: "off",
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1440, height: 900 },
      },
    },
  ],
  webServer: {
    command: real
      ? "sh tests/e2e/real-backend.sh"
      : "SEND_WINDOW=10 node tests/e2e/mock-server.mjs",
    url: `http://127.0.0.1:${port}/`,
    reuseExistingServer: false,
    timeout: 60_000,
  },
});
