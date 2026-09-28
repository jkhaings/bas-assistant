import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const API_PATHS = [
    "/ask",
    "/approve",
    "/threads",
    "/tickets",
    "/requests",
    "/documents",
    "/evals",
    "/budget",
    "/healthz",
    "/search",
    "/docs",
    "/openapi.json",
];

const apiProxy = Object.fromEntries(API_PATHS.map((path) => [path, "http://localhost:8000"]));

export default defineConfig({
    plugins: [react(), tailwindcss()],
    server: {
        proxy: { ...apiProxy, "/grafana": "http://localhost:3000" },
        // How I built this imports eval/golden.jsonl?raw. Vite checks a ?raw id against the
        // allow list with its query attached, which only a parent directory can match.
        fs: { allow: [".", "../eval"] },
    },
    test: {
        environment: "jsdom",
        setupFiles: ["./src/tests/setup.ts"],
    },
});
