import { parentPort, workerData } from "worker_threads";
import { loadPyodide } from "pyodide";

/**
 * Runs inside a worker_thread, spawned fresh per code-execution request by
 * entrypoint.mjs. Security properties (verified during development, see
 * backend/sandbox/README.md):
 *
 *  - Hard timeout: entrypoint.mjs kills this worker via terminate() after a
 *    deadline. This is NOT the same as an in-process timeout — a same-thread
 *    Promise.race cannot interrupt a blocking WASM loop, since the loop never
 *    yields back to the event loop for the timer to fire. terminate() works
 *    because it stops the underlying V8 isolate/thread from the outside.
 *  - No host filesystem access: Pyodide's Python open() operates on an
 *    isolated in-memory virtual filesystem, not the real disk.
 *  - No network access from sandboxed code: no fetch/socket bridge is
 *    exposed to the executed code.
 *  - No host secrets: the worker is spawned with an empty environment
 *    (entrypoint.mjs sets env: {}), so even if something reached
 *    js.process.env, there'd be nothing sensitive in it.
 *  - js/pyodide_js/micropip imports are blocked outright inside the
 *    executed code, as defense in depth beyond the empty env — this is what
 *    stops code from reaching the host JS/Node layer at all (confirmed
 *    during testing that js.process is reachable by default, an everyday
 *    Node global, not gated by Pyodide).
 *
 * Note on style: every Python snippet below assigns its result to a named
 * global and fetches it via pyodide.globals.get(name), rather than relying
 * on runPython's "return the last bare expression" semantics. That implicit
 * behavior only applies when the final top-level statement is itself a bare
 * expression — it silently returns undefined for anything ending in an
 * assignment or a try/except block, which cost real debugging time here.
 * Explicit globals.get() has no such gotcha.
 */

function getGlobal(pyodide, name) {
  const value = pyodide.globals.get(name);
  return typeof value?.toJs === "function" ? value.toJs() : value;
}

async function main() {
  // Pyodide's default stdout/stderr writes through a raw file-descriptor
  // path that is broken inside a worker_thread (observed during testing:
  // it floods stderr with repeated ERR_INVALID_ARG_TYPE writes whenever
  // Python prints anything, e.g. an uncaught traceback). Routing through
  // explicit JS callbacks avoids that path entirely.
  const pyodide = await loadPyodide({
    stdout: () => {},
    stderr: () => {},
  });

  // loadPackage does NOT reliably throw on failure (observed during testing
  // — a failed fetch logs a warning and resolves normally). The real signal
  // is whether `import pandas` succeeds afterward, checked explicitly below.
  try {
    await pyodide.loadPackage(["pandas", "numpy"]);
  } catch (e) {
    parentPort.postMessage({
      ok: false,
      error: `SANDBOX_PACKAGES_UNAVAILABLE: ${e.message}`,
    });
    return;
  }

  pyodide.runPython(`
try:
    import pandas
    import numpy
    _import_check = "ok"
except ImportError as e:
    _import_check = "missing: " + str(e)
`);
  const importCheck = getGlobal(pyodide, "_import_check");
  if (importCheck !== "ok") {
    parentPort.postMessage({
      ok: false,
      error:
        "SANDBOX_PACKAGES_UNAVAILABLE: could not load pandas/numpy " +
        "(requires network access to the Pyodide package CDN at deploy/runtime): " +
        importCheck,
    });
    return;
  }

  // Reconstruct the dataset inside the sandbox from the CSV string passed in.
  // Using CSV (not a live DataFrame handle) is deliberate: it's the simplest
  // thing that can cross the process boundary as plain data, with no shared
  // mutable state between the real backend's DataFrame and the sandbox's copy.
  pyodide.globals.set("_csv_data", workerData.csvData);

  pyodide.runPython(`
import sys

class _BlockedModule:
    def __getattr__(self, name):
        raise ImportError("access to the host runtime is not permitted inside the sandbox")

sys.modules["js"] = _BlockedModule()
sys.modules["pyodide_js"] = _BlockedModule()
sys.modules["micropip"] = _BlockedModule()

import pandas as pd
import numpy as np
import io

try:
    df = pd.read_csv(io.StringIO(_csv_data))
    _setup_status = "ready"
except Exception as e:
    _setup_status = "failed: " + str(e)
`);
  const setupStatus = getGlobal(pyodide, "_setup_status");
  if (setupStatus !== "ready") {
    parentPort.postMessage({ ok: false, error: `SANDBOX_SETUP_FAILED: ${setupStatus}` });
    return;
  }

  try {
    // User code must assign to `result`. Deliberately not relying on
    // "last expression" semantics here either — we don't control what
    // shape of code the LLM writes (loops, assignments, multi-statement
    // blocks don't have a meaningful last-expression value).
    pyodide.runPython(workerData.code);

    pyodide.runPython(`
import json
import numpy as np
import pandas as pd

def _to_jsonable(obj):
    if isinstance(obj, pd.Series):
        return obj.tolist()
    if isinstance(obj, pd.DataFrame):
        return obj.to_dict(orient="records")
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj

try:
    _result_value = result
    _result_status = "ok"
except NameError:
    _result_status = "no_result_variable"
    _result_value = None
`);
    const resultStatus = getGlobal(pyodide, "_result_status");
    if (resultStatus === "no_result_variable") {
      parentPort.postMessage({ ok: false, error: "Code did not assign a result variable." });
      return;
    }

    pyodide.runPython(`
try:
    _result_json = json.dumps({"v": _to_jsonable(_result_value)})
except TypeError:
    _result_json = json.dumps({"v": str(_result_value)})
`);
    const resultJson = getGlobal(pyodide, "_result_json");
    const parsed = JSON.parse(resultJson);
    parentPort.postMessage({ ok: true, result: parsed.v });
  } catch (e) {
    // Truncate — a stray traceback shouldn't blow past a reasonable payload size.
    parentPort.postMessage({ ok: false, error: String(e.message || e).slice(0, 2000) });
  }
}

main().catch((e) => {
  // Safety net for anything not already caught above — most importantly,
  // Pyodide's own startup (loadPyodide() itself was never wrapped). Without
  // this, an unexpected failure anywhere just crashes the worker with no
  // message at all, and entrypoint.mjs's exit handler reports a bare
  // "WORKER_EXIT_1" with zero diagnostic value — exactly what happened
  // during testing before this was added.
  parentPort.postMessage({
    ok: false,
    error: `WORKER_INIT_ERROR: ${String(e?.stack || e?.message || e)}`.slice(0, 2000),
  });
});
