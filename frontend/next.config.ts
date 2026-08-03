import type { NextConfig } from "next";
import path from "node:path";

const nextDistDir = process.env.NEXT_DIST_DIR;

const nextConfig: NextConfig = {
  // Local browser evidence must contain product UI only; the development indicator
  // otherwise overlays narrow content and makes Axe unable to determine contrast.
  devIndicators: false,
  ...(nextDistDir
    ? {
        distDir: nextDistDir,
        typescript: { tsconfigPath: `${nextDistDir}.tsconfig.json` },
      }
    : {}),
  output: "standalone",
  // Include the sibling production design-system package in standalone tracing.
  outputFileTracingRoot: path.resolve(__dirname, ".."),
  turbopack: {
    // Tokens live in the repository design-system package, one level above frontend.
    root: path.resolve(__dirname, ".."),
  },
};

export default nextConfig;
