import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  server: {
    // Loopback only, same rule as every published Compose port (ADR-008).
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": {
        // Inside the dev Compose the API answers by service name; on the host
        // it answers on loopback.
        target: process.env["VITE_API_PROXY_TARGET"] ?? "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
