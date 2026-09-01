# python-side entry point to the code-execution sandbox, calls the Node subprocess (sandbox/entrypoint.mjs)
# two independent timeout layers: outer python timeout via subprocess.run(timeout=...) and inner Node.js Worker.terminate()

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

SANDBOX_DIR = Path(__file__).parent.parent.parent / "sandbox"
ENTRYPOINT = SANDBOX_DIR / "entrypoint.mjs"

DEFAULT_TIMEOUT_MS = 10_000
# outer python-level timeout is deliberately longer than the inner Node timeout so it never fires first 
# it exists to kill execution if the inner mechanism doesnt work as expected.
OUTER_TIMEOUT_BUFFER_SECONDS = 5


@dataclass
class SandboxResult:
    ok: bool
    result: object | None = None
    error: str | None = None

# executes code against a pandas DataFrame reconstructed from csv_data inside an isolated Pyodide/WASM sandbox 
# returns SandboxResult(ok=False, ...) for any failures so the tool-calling agent can send a result object back to the LLM.
def run_sandboxed_code(code: str, csv_data: str, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> SandboxResult:
    payload = json.dumps({"code": code, "csv_data": csv_data, "timeout_ms": timeout_ms})
    outer_timeout_seconds = (timeout_ms / 1000) + OUTER_TIMEOUT_BUFFER_SECONDS

    try:
        proc = subprocess.run(
            ["node", str(ENTRYPOINT)],
            input=payload,
            capture_output=True,
            text=True,
            timeout=outer_timeout_seconds,
            cwd=str(SANDBOX_DIR),
        )
    except subprocess.TimeoutExpired:
        return SandboxResult(ok=False, error="TIMEOUT: sandbox process did not respond in time (outer bound).")

    if proc.returncode != 0 and not proc.stdout.strip():
        return SandboxResult(ok=False, error=f"SANDBOX_PROCESS_ERROR: {proc.stderr.strip()[:2000]}")

    try:
        parsed = json.loads(proc.stdout.strip())
    except json.JSONDecodeError:
        return SandboxResult(ok=False, error=f"SANDBOX_BAD_OUTPUT: {proc.stdout[:500]}")

    if parsed.get("ok"):
        return SandboxResult(ok=True, result=parsed.get("result"))
    return SandboxResult(ok=False, error=parsed.get("error", "Unknown sandbox error."))
