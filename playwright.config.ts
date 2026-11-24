import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { defineConfig } from "@playwright/test";

const backendPort = process.env["BACKEND_PORT"] ?? "8000";
const dataDir = mkdtempSync(join(tmpdir(), "retirement-studio-e2e-"));

export default defineConfig({
  testDir: "e2e",
  use: { baseURL: "http://localhost:5173" },
  webServer: [
    {
      command: `uv run -m uvicorn backend.main:app --port ${backendPort}`,
      url: `http://localhost:${backendPort}/api/health`,
      env: { DATA_DIR: dataDir, BACKEND_PORT: backendPort },
      reuseExistingServer: false,
    },
    {
      command: "npx vite dashboard --port 5173 --strictPort",
      url: "http://localhost:5173",
      reuseExistingServer: false,
    },
  ],
});
