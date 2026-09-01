import { parentPort, workerData } from "worker_threads";
import { loadPyodide } from "pyodide";

/**

 * runs inside a worker_thread, spawned per code-execution request by entrypoint.mjs
 *
 * hard timeout: entrypoint.mjs kills this worker via terminate() after a deadline 
 * terminate() stops the underlying V8 isolate/thread from the outside
 *
 * every Python snippet below assigns its result to a named global and fetches it via pyodide.globals.get(name)
>>>>>>> b485336 (Added visuals such as charts, stylized texts, etc for each tool call in the LLM response to enhance user experience. Updated Vertex AI client to enable config of model's thinking capacity for both 2.x and 3.x generations. Wrote detailed README.md for the project)
 */

function getGlobal(pyodide, name) {
  const value = pyodide.globals.get(name);
  return typeof value?.toJs === "function" ? value.toJs() : value;
}

async function main() {
  const pyodide = await loadPyodide({
    stdout: () => {},
    stderr: () => {},
  });


  // `import pandas` success checked explicitly as loadPackage does not reliably throw on failure
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


  // reconstruct the dataset inside the sandbox from the CSV string passed in
  // using CSV passed as plain data ensures no shared mutable state between the backend DataFrame and the sandbox copy
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

    // truncate so a stray traceback doesnt cross a specified payload size
    parentPort.postMessage({ ok: false, error: String(e.message || e).slice(0, 2000) });
  }
}

main().catch((e) => {

  // safety net for anything not already caught above such as loadPyodide() (pyodide startup) which was never wrapped. 
  // without this, an unexpected failure anywhere crashes the worker with no
  // message except for entrypoint.mjs's exit handler reporting a "WORKER_EXIT_1"
  parentPort.postMessage({
    ok: false,
    error: `WORKER_INIT_ERROR: ${String(e?.stack || e?.message || e)}`.slice(0, 2000),
  });
});
