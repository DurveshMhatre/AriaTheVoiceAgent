import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";

export default defineConfig({
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  server: { fs: { allow: [fileURLToPath(new URL("../..", import.meta.url))] } },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test-setup.ts"],
    pool: "threads",
    maxWorkers: 1,
    minWorkers: 1,
    fileParallelism: false,
    coverage: {
      provider: "v8",
      include: ["src/lib/**/*.ts"],
      exclude: ["src/lib/**/*.test.ts"],
      reportsDirectory: process.env.VITEST_COVERAGE_DIR ?? "coverage",
      thresholds: {
        lines: 80,
        functions: 80,
        statements: 80,
        "src/lib/call/reducer.ts": { lines: 90, functions: 90, statements: 90, branches: 75 },
        "src/lib/call/protocol.ts": { lines: 90, functions: 90, statements: 90, branches: 90 },
        "src/lib/call/errors.ts": { lines: 90, functions: 90, statements: 90, branches: 90 },
      },
    },
  },
});
