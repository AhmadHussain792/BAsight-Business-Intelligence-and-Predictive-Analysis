"""
Python-side entry point to the code-execution sandbox. Spawns the Node
subprocess (sandbox/entrypoint.mjs) which itself hard-kills a worker_thread
running Pyodide/WASM Python — see pyodide_worker.mjs for what that boundary
actually guarantees.

Two independent timeout layers on purpose: the Node side kills its worker
via Worker.terminate() (verified during development to actually stop a
blocking WASM loop, unlike an in-process JS timeout). This module adds a
second, outer timeout via subprocess.run(timeout=...), which can SIGKILL the
whole Node process unconditionally. Belt and suspenders — if the inner
mechanism ever fails for a reason not yet discovered, the outer one still
bounds worst-case execution time.
"""
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

SANDBOX_DIR = Path(__file__).parent.parent.parent / "sandbox"
ENTRYPOINT = SANDBOX_DIR / "entrypoint.mjs"

DEFAULT_TIMEOUT_MS = 10_000
# Outer Python-level timeout is deliberately looser than the inner Node
# timeout — it should almost never be the one that fires; it exists only to
# bound total wait time if the inner mechanism doesn't fire as expected.
OUTER_TIMEOUT_BUFFER_SECONDS = 5


@dataclass
class SandboxResult:
    ok: bool
    result: object | None = None
    error: str | None = None


def run_sandboxed_code(code: str, csv_data: str, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> SandboxResult:
    """
    Executes `code` against a pandas DataFrame named `df` (reconstructed
    from `csv_data`) inside an isolated Pyodide/WASM sandbox. `code` must
    assign its answer to a variable named `result` (JSON-serializable).

    Returns SandboxResult(ok=False, ...) for any failure mode — bad code,
    timeout, or the sandbox's own packages being unavailable — rather than
    raising, since a tool-calling agent needs a result object it can hand
    back to the LLM to react to, not an exception that aborts the turn.
    """
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
