import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "WEB_PORT");
  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        "/api": {
          target: `http://127.0.0.1:${process.env.WEB_PORT || env.WEB_PORT || 8501}`,
          // Keep the browser's host so Python's same-origin CSRF check succeeds.
          changeOrigin: false,
        },
      },
    },
    build: { outDir: "dist" },
  };
});
