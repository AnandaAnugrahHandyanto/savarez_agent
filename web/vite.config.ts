import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";

const BACKEND = process.env.HERMES_DASHBOARD_URL ?? "http://127.0.0.1:9119";

/**
 * Dev-server session-token flow
 * -----------------------------
 * `hermes dashboard` prints a URL with a `#tk=<token>` fragment on startup.
 * To run Vite against a live dashboard:
 *   1. `hermes dashboard --no-open`
 *   2. Open `http://localhost:5173/#tk=<token>` with the printed token.
 * The SPA consumes the fragment, stores the token in sessionStorage, and
 * scrubs it from the address bar. `/api/*` calls are proxied to the
 * dashboard (see `server.proxy`). If the dashboard restarts, reload will
 * 401 — repeat step 2 with the newly printed URL.
 */

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    outDir: "../hermes_cli/web_dist",
    emptyOutDir: true,
  },
  server: {
    proxy: {
      "/api": {
        target: BACKEND,
        ws: true,
      },
      // Same host as `hermes dashboard` must serve these; Vite has no
      // dashboard-plugins/* files, so without this, plugin scripts 404
      // or receive index.html in dev.
      "/dashboard-plugins": BACKEND,
    },
  },
});
