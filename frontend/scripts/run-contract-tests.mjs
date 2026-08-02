import { rmSync } from "node:fs";
import { spawnSync } from "node:child_process";

const outputDirectory = ".contract-dist";
const commands = [
  [process.execPath, ["node_modules/typescript/bin/tsc", "-p", "tsconfig.contract.json"]],
  ["node", [".contract-dist/navigation.contract.js"]],
  ["node", [".contract-dist/engagementRoute.contract.js"]],
  ["node", [".contract-dist/startupRequestPolicy.contract.js"]],
  ["node", [".contract-dist/hostNavigation.contract.js"]],
];

rmSync(outputDirectory, { recursive: true, force: true });
try {
  for (const [command, args] of commands) {
    const result = spawnSync(command, args, { stdio: "inherit" });
    if (result.error) throw result.error;
    if (result.status !== 0) process.exitCode = result.status ?? 1;
    if (process.exitCode) break;
  }
} finally {
  rmSync(outputDirectory, { recursive: true, force: true });
}
