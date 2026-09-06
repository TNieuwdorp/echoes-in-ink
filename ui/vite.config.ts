import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";

// In review mode the FastAPI backend (echoes serve) runs on :8765 and Vite proxies /api.
// The built site (npm run build) has no backend and reads Parquet from /data instead.
export default defineConfig({
  plugins: [svelte()],
  server: { port: 5173, proxy: { "/api": "http://127.0.0.1:8765" } },
  optimizeDeps: { exclude: ["parquet-wasm"] },
  build: { target: "esnext" },
});
