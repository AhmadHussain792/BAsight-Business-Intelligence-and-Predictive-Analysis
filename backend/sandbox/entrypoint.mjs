import { Worker } from "worker_threads";
import { fileURLToPath } from "url";
import path from "path";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const WORKER_PATH = path.join(__dirname, "pyodide_worker.mjs");

function readStdin() {
  return new Promise((resolve, reject) => {
    let data = "";
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (chunk) => (data += chunk));
    process.stdin.on("end", () => resolve(data));
    process.stdin.on("error", reject);
  });
}

function runInWorker(code, csvData, timeoutMs) {
  return new Promise((resolve) => {
    const worker = new Worker(WORKER_PATH, {
      workerData: { code, csvData },

      env: {}, // no inherited environment so nothing sensitive for sandboxed code to reach.
      resourceLimits: {
        // caps worst-case memory blowup
        maxOldGenerationSizeMb: 1536,
        maxYoungGenerationSizeMb: 512,
      },
    });

    let settled = false;
    const settle = (value) => {
      if (settled) return;
      settled = true;
      resolve(value);
    };

    const timer = setTimeout(() => {
      worker.terminate().finally(() => settle({ ok: false, error: "TIMEOUT: code did not finish in time." }));
    }, timeoutMs);

    worker.on("message", (msg) => {
      clearTimeout(timer);
      settle(msg);
    });
    worker.on("error", (err) => {
      clearTimeout(timer);
      settle({ ok: false, error: `WORKER_ERROR: ${err.message}` });
    });
    worker.on("exit", (code) => {
      clearTimeout(timer);
      if (code !== 0) settle({ ok: false, error: `WORKER_EXIT_${code}` });
    });
  });
}

async function main() {
  let request;
  try {
    const raw = await readStdin();
    request = JSON.parse(raw);
  } catch (e) {
    process.stdout.write(JSON.stringify({ ok: false, error: `INVALID_REQUEST: ${e.message}` }));
    process.exit(1);
  }

  const { code, csv_data: csvData, timeout_ms: timeoutMs } = request;
  if (typeof code !== "string" || typeof csvData !== "string") {
    process.stdout.write(JSON.stringify({ ok: false, error: "INVALID_REQUEST: missing code or csv_data" }));
    process.exit(1);
  }

  const result = await runInWorker(code, csvData, timeoutMs || 10000);
  process.stdout.write(JSON.stringify(result));
  process.exit(0);
}

main();
