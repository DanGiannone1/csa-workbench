import { createServer } from "node:http";

import { buildShowcaseModel, renderShowcaseHtml } from "./eval_showcase.mjs";

function usage() {
  return "Usage: node scripts/eval_showcase_server.mjs [--port <1024-65535>] [--product <results.json>] [--waza <waza.json>]";
}

export function parseShowcaseArgs(argv) {
  const values = { port: 4310, productPath: null, wazaPath: null };
  for (let index = 0; index < argv.length; index += 1) {
    const argument = argv[index];
    const next = argv[index + 1];
    if (argument === "--port" && next) {
      values.port = Number(next);
      index += 1;
    } else if (argument === "--product" && next) {
      values.productPath = next;
      index += 1;
    } else if (argument === "--waza" && next) {
      values.wazaPath = next;
      index += 1;
    } else if (argument === "--help" || argument === "-h") {
      return { help: true, ...values };
    } else {
      throw new Error(`${usage()}\nUnknown or incomplete argument: ${argument}`);
    }
  }
  if (!Number.isInteger(values.port) || values.port < 1024 || values.port > 65535) {
    throw new Error(`${usage()}\n--port must be an integer from 1024 through 65535`);
  }
  return values;
}

export function createShowcaseServer(options = {}) {
  return createServer((request, response) => {
    if (request.method !== "GET") {
      response.writeHead(405, { "content-type": "text/plain; charset=utf-8", allow: "GET" });
      response.end("Method not allowed\n");
      return;
    }
    const url = new URL(request.url ?? "/", "http://127.0.0.1");
    if (url.pathname === "/health") {
      response.writeHead(200, { "content-type": "application/json", "cache-control": "no-store" });
      response.end(JSON.stringify({ status: "ok" }));
      return;
    }
    if (!["/", "/index.html"].includes(url.pathname)) {
      response.writeHead(404, { "content-type": "text/plain; charset=utf-8" });
      response.end("Not found\n");
      return;
    }
    try {
      const model = buildShowcaseModel(options);
      const html = renderShowcaseHtml(model);
      response.writeHead(200, {
        "content-type": "text/html; charset=utf-8",
        "cache-control": "no-store",
        "x-content-type-options": "nosniff",
        "referrer-policy": "no-referrer",
      });
      response.end(html);
    } catch (error) {
      response.writeHead(500, { "content-type": "text/plain; charset=utf-8", "cache-control": "no-store" });
      response.end(`Unable to render the evaluation showcase: ${error instanceof Error ? error.message : String(error)}\n`);
    }
  });
}

if (process.argv[1] && import.meta.url === new URL(`file://${process.argv[1]}`).href) {
  try {
    const args = parseShowcaseArgs(process.argv.slice(2));
    if (args.help) {
      console.log(usage());
    } else {
      const server = createShowcaseServer({ productPath: args.productPath, wazaPath: args.wazaPath });
      server.listen(args.port, "127.0.0.1", () => {
        console.log(`CSA Workbench evaluation showcase: http://127.0.0.1:${args.port}`);
        console.log("Refresh the page after a Waza or Deep Agents run to load the newest local evidence.");
      });
    }
  } catch (error) {
    console.error(error instanceof Error ? error.message : String(error));
    process.exitCode = 2;
  }
}
