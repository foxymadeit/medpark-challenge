import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  return {
    plugins: [react()],
    server: {
      // Set only for the local backend; demo mode never calls it.
      proxy: env.API_PROXY_TARGET
        ? { "/api": { target: env.API_PROXY_TARGET, changeOrigin: false } }
        : undefined,
    },
  };
});
