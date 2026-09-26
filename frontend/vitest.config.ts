import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
export default defineConfig({
  plugins: [react()],
  define: {
    "import.meta.env.VITE_DEMO_MODE": JSON.stringify("true"),
    "import.meta.env.VITE_DEMO_EMAIL": JSON.stringify("admin@medpark.local"),
    "import.meta.env.VITE_DEMO_PASSWORD": JSON.stringify(
      "test-only-demo-password",
    ),
    "import.meta.env.VITE_DEMO_SEND_COUNTDOWN_SECONDS": JSON.stringify("300"),
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
    restoreMocks: true,
    // The recorder tests race real timers; under a loaded machine 5 s is too tight.
    testTimeout: 15000,
    exclude: ["tests/e2e/**", "node_modules/**"],
  },
});
