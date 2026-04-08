import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

export default defineConfig(({ mode }) => {
    const env = loadEnv(mode, process.cwd(), "");
    const backendTarget = env.VITE_API_BASE_URL || "http://127.0.0.1:8000";
    return {
        plugins: [react()],
        resolve: {
            alias: {
                "@": fileURLToPath(new URL("./src", import.meta.url)),
            },
        },
        server: {
            proxy: {
                "/auth": backendTarget,
                "/api": backendTarget,
                "/chat": backendTarget,
                "/health": backendTarget,
                "/ready": backendTarget,
            },
        },
        test: {
            environment: "jsdom",
            globals: true,
            setupFiles: "./src/setupTests.ts",
        },
    };
});
