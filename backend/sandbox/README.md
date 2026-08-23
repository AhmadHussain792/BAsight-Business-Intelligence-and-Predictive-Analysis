# Code-execution sandbox (Pyodide/WASM)

This is the fallback path for agent queries that the structured tool set
(`app/agent/tools.py` — not yet built as of this writing) can't answer. The
LLM writes pandas code, which runs here instead of anywhere near the real
backend process.

## How it works

```
FastAPI backend (Python)
  -> app/agent/sandbox.py: run_sandboxed_code(code, csv_data, timeout_ms)
     -> subprocess: node sandbox/entrypoint.mjs   [stdin/stdout JSON, outer timeout]
        -> worker_thread: sandbox/pyodide_worker.mjs   [inner hard timeout via terminate()]
           -> Pyodide (WASM Python) with pandas/numpy, running only the LLM's code
```

Two independent timeout layers: the Node entrypoint hard-kills its worker
via `Worker.terminate()`, and the Python wrapper has its own looser
`subprocess.run(timeout=...)` as a second, independent backstop.

## Why this shape, specifically

E2B Cloud Sandbox was the other option under consideration. Went with
Pyodide instead because it's self-hosted (no per-execution cost or external
API dependency for a project that might just be personally deployed) and —
more importantly — because it was actually possible to verify its isolation
properties directly in this dev environment, whereas E2B would have been
entirely unverified (no API key, no network path to their service here).

## What was verified, and how (this matters more than it usually would,
## because two of the assumptions below turned out to be wrong on first try)

1. **Hard timeout actually stops a genuine infinite loop.**
   First attempt used a same-thread `Promise.race` — this does **not**
   work: a blocking WASM loop never yields back to the JS event loop, so
   the race's timer never fires, and the whole process hangs. Confirmed
   this failure directly (had to kill the test with a shell-level
   `timeout` wrapper). Fixed by moving execution into a `worker_thread`
   and calling `.terminate()` from the parent after the deadline — this
   works because it stops the underlying thread from the outside, not
   cooperatively. Verified: a genuine `while True: pass` was killed in
   ~2s against the target timeout, both directly against the worker and
   through the full Node entrypoint stdin/stdout path.

2. **No host filesystem access.** Wrote a real secret file on the host,
   confirmed sandboxed Python `open()` cannot read it (Pyodide's
   filesystem is an isolated in-memory VFS, not the real disk).

3. **No network access from sandboxed code.** Confirmed a `urllib`
   request from inside the sandbox fails — no fetch/socket bridge is
   exposed to code running there.

4. **A real, exploitable env-var leak — found and fixed.** Pyodide
   exposes a `js` interop module by design (that's how Python↔JS calls
   work). In a Node host, `js.process` is reachable through it, and
   `js.process.env` is the **real** Node process environment — including
   anything from `.env` (API keys, etc.) if the worker inherited it.
   Confirmed this concretely: set a fake secret in the parent's env,
   read it back out via `js.process.env.X` from inside "sandboxed" code.
   Fixed with two independent layers: (a) the worker is spawned with
   `env: {}` — no inherited environment at all, so there's nothing to
   leak even if something reaches the bridge; (b) `js`/`pyodide_js`/
   `micropip` imports are blocked outright inside executed code, as
   defense in depth beyond (a). Reverified the leak attempt fails after
   both fixes.

5. **Pandas package loading requires network access this dev sandbox
   doesn't have** (`cdn.jsdelivr.net` isn't reachable here). This is a
   **deployment dependency, not a security gap** — the isolation
   properties above hold regardless of which packages get loaded, since
   they come from the WASM boundary itself, not from anything
   package-specific. But it does mean the actual pandas-execution path
   (the entire point of this module) is **unverified end-to-end** in
   this environment. Before relying on this in production, run:
   ```bash
   cd sandbox
   echo '{"code":"result = df[\"a\"].sum()","csv_data":"a,b\n1,2\n3,4\n","timeout_ms":15000}' | node entrypoint.mjs
   ```
   from a machine with normal internet access, and confirm you get back
   `{"ok":true,"result":4}`. If it doesn't, self-hosting the Pyodide
   package files (rather than depending on jsdelivr's CDN at request
   time) is the standard production fix — see Pyodide's docs on
   `indexURL`.

## A debugging note worth keeping, since it cost real time three separate
## times before the pattern was obvious

`pyodide.runPython(code)` returns the value of the code's **last bare
expression** — but that's not the same as "the last thing that happened."
An assignment (`x = 1`) isn't an expression, and neither is a `try/except`
block, so code ending in either of those silently returns `undefined`
regardless of what happened inside. `pyodide_worker.mjs` avoids this
entirely: every Python snippet assigns to a named global explicitly, and
the JS side fetches it via `pyodide.globals.get(name)` rather than trusting
the return value of `runPython` at all.

## Interface

`run_sandboxed_code(code: str, csv_data: str, timeout_ms: int) -> SandboxResult`

The executed `code` must assign its answer to a variable named `result`
(JSON-serializable — plain values, or a pandas Series/DataFrame/numpy
scalar, which get converted automatically). `df` is available, reconstructed
from `csv_data`. Returns `SandboxResult(ok, result, error)` — never raises
for sandbox-side failures (bad code, timeout, missing packages), since a
tool-calling agent needs an object it can hand back to the LLM to react to,
not an exception that aborts the whole turn.
