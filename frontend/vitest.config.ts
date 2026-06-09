import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";

// Pure transform tests run in node (no DOM). The `@/*` alias mirrors tsconfig.
export default defineConfig({
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  test: {
    environment: "node",
    include: ["src/**/*.{test,spec}.ts"],
  },
});
