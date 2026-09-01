"use client";

interface CustomResultProps {
  result: unknown;
}

export default function CustomResult({ result }: CustomResultProps) {
  if (typeof result === "number") {
    return (
      <div className="perforated-top mt-4 bg-ink-raised px-6 pt-5 pb-4">
        <p className="text-eyebrow text-[10px] text-paper/45">Result</p>
        <p className="mt-1 font-mono text-4xl font-semibold tabular-nums text-signal">
          {result.toLocaleString(undefined, { maximumFractionDigits: 2 })}
        </p>
      </div>
    );
  }

  if (Array.isArray(result) && result.length > 0 && typeof result[0] === "object") {
    const columns = Object.keys(result[0] as Record<string, unknown>);
    return (
      <div className="mt-4 overflow-x-auto bg-ink-raised px-5 py-5">
        <p className="text-eyebrow mb-3 text-[10px] text-paper/45">Result</p>
        <table className="w-full font-mono text-xs">
          <thead>
            <tr className="border-b border-dashed border-paper/15 text-left text-paper/45">
              {columns.map((c) => (
                <th key={c} className="pb-2 pr-4 font-normal">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {result.slice(0, 10).map((row, i) => (
              <tr key={i} className="border-b border-paper/5 text-paper/75">
                {columns.map((c) => (
                  <td key={c} className="py-1.5 pr-4">
                    {String((row as Record<string, unknown>)[c])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  return (
    <div className="mt-4 bg-ink-raised px-5 py-4">
      <p className="text-eyebrow mb-2 text-[10px] text-paper/45">Result</p>
      <pre className="whitespace-pre-wrap break-words font-mono text-xs text-paper/70">
        {typeof result === "string" ? result : JSON.stringify(result, null, 2)}
      </pre>
    </div>
  );
}
