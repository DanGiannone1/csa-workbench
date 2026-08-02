import type { NextConfig } from "next";
import path from "node:path";

const nextDistDir = process.env.NEXT_DIST_DIR;

const nextConfig: NextConfig = {
  ...(nextDistDir
    ? {
        distDir: nextDistDir,
        typescript: { tsconfigPath: `${nextDistDir}.tsconfig.json` },
      }
    : {}),
  output: "standalone",
  turbopack: {
    // Tokens live in the repository design-system package, one level above frontend.
    root: path.resolve(__dirname, ".."),
  },
};

export default nextConfig;
