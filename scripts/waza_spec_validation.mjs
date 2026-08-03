import { createHash } from "node:crypto";
import { readFileSync, readdirSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import Ajv from "ajv";
import { parseDocument } from "yaml";

const REPOSITORY_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const WAZA_SPEC_ROOT = join(REPOSITORY_ROOT, "tests", "evals", "waza");

export const PINNED_WAZA_SCHEMAS = Object.freeze({
  eval: Object.freeze({
    url: "https://raw.githubusercontent.com/microsoft/waza/v0.38.3/schemas/eval.schema.json",
    sha256: "f9ae5730c4170695a700ce927c0fa26d3c75c00d901e46115ec4d123f87b5565",
  }),
  task: Object.freeze({
    url: "https://raw.githubusercontent.com/microsoft/waza/v0.38.3/schemas/task.schema.json",
    sha256: "28466d3b205b68fab9eb1de55d87d3643ebd3835a8eb4cb990907483487cf6d1",
  }),
});

export function parseWazaYaml(source, sourceName = "Waza YAML") {
  const document = parseDocument(source, { prettyErrors: true, uniqueKeys: true });
  if (document.errors.length) {
    throw new Error(`${sourceName} is not valid YAML: ${document.errors.map((error) => error.message).join("; ")}`);
  }
  return document.toJS({ maxAliasCount: 0 });
}

async function fetchPinnedSchema({ url, sha256 }) {
  const response = await fetch(url, { redirect: "error" });
  if (!response.ok) throw new Error(`Unable to retrieve pinned Waza schema ${url}: HTTP ${response.status}`);
  const bytes = Buffer.from(await response.arrayBuffer());
  const actual = createHash("sha256").update(bytes).digest("hex");
  if (actual !== sha256) {
    throw new Error(`Pinned Waza schema hash mismatch for ${url}: expected ${sha256}, got ${actual}`);
  }
  return JSON.parse(bytes.toString("utf8"));
}

export async function loadPinnedWazaSchemas() {
  const [evalSchema, taskSchema] = await Promise.all([
    fetchPinnedSchema(PINNED_WAZA_SCHEMAS.eval),
    fetchPinnedSchema(PINNED_WAZA_SCHEMAS.task),
  ]);
  return { eval: evalSchema, task: taskSchema };
}

function yamlFiles(root) {
  return readdirSync(root, { withFileTypes: true }).flatMap((entry) => {
    const path = join(root, entry.name);
    return entry.isDirectory() ? yamlFiles(path) : entry.isFile() && entry.name.endsWith(".yaml") ? [path] : [];
  });
}

function formatValidationErrors(path, errors) {
  const details = (errors ?? []).map((error) =>
    `${error.instancePath || "/"} ${error.message}${error.params?.missingProperty ? ` (${error.params.missingProperty})` : ""}`,
  );
  return `${relative(REPOSITORY_ROOT, path)} failed Waza v0.38.3 schema validation:\n- ${details.join("\n- ")}`;
}

export async function validateCheckedInWazaSpecs({
  specRoot = WAZA_SPEC_ROOT,
  schemas = null,
} = {}) {
  const loadedSchemas = schemas ?? await loadPinnedWazaSchemas();
  const ajv = new Ajv({ allErrors: true, strict: false, validateFormats: false });
  const validateEval = ajv.compile(loadedSchemas.eval);
  const validateTask = ajv.compile(loadedSchemas.task);
  const files = yamlFiles(specRoot).sort();
  const counts = { evals: 0, tasks: 0 };

  for (const path of files) {
    const value = parseWazaYaml(readFileSync(path, "utf8"), relative(REPOSITORY_ROOT, path));
    const isEval = path.endsWith(`${process.platform === "win32" ? "\\" : "/"}eval.yaml`);
    const validate = isEval ? validateEval : validateTask;
    counts[isEval ? "evals" : "tasks"] += 1;
    if (!validate(value)) throw new Error(formatValidationErrors(path, validate.errors));
  }
  return { ...counts, schemaVersion: "0.38.3", files: files.length };
}

if (process.argv[1] && pathToFileURL(resolve(process.argv[1])).href === import.meta.url) {
  const result = await validateCheckedInWazaSpecs();
  console.log(`Validated ${result.evals} eval specs and ${result.tasks} task specs against Waza ${result.schemaVersion}.`);
}
