"use client";

import { useCallback, useRef, useState } from "react";
import { FileSpreadsheet, Upload } from "lucide-react";

interface UploadScreenProps {
  onFileSelected: (file: File) => void;
  errorMessage: string | null;
}

const ALLOWED_EXTENSIONS = [".csv", ".xlsx", ".xls"];
const MAX_SIZE_MB = 25;

function validateFile(file: File): string | null {
  const lowerName = file.name.toLowerCase();
  const hasAllowedExtension = ALLOWED_EXTENSIONS.some((ext) => lowerName.endsWith(ext));
  if (!hasAllowedExtension) {
    return `BAsight reads spreadsheets, not this. Use ${ALLOWED_EXTENSIONS.join(", ")}.`;
  }
  if (file.size > MAX_SIZE_MB * 1024 * 1024) {
    return `That file is over the ${MAX_SIZE_MB}MB limit. Trim it down and try again.`;
  }
  return null;
}

export default function UploadScreen({ onFileSelected, errorMessage }: UploadScreenProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = useCallback(
    (file: File | undefined | null) => {
      if (!file) return;
      const validationError = validateFile(file);
      if (validationError) {
        setLocalError(validationError);
        return;
      }
      setLocalError(null);
      onFileSelected(file);
    },
    [onFileSelected]
  );

  const onDrop = useCallback(
    (event: React.DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      setIsDragging(false);
      handleFile(event.dataTransfer.files?.[0]);
    },
    [handleFile]
  );

  const displayedError = localError || errorMessage;

  return (
    <main className="relative min-h-screen overflow-hidden bg-ink text-paper">
      <div className="halftone pointer-events-none absolute inset-0 opacity-40" />

      <div className="relative mx-auto flex min-h-screen max-w-4xl flex-col items-center justify-center px-6 py-16">
        <div className="mb-10 text-center">
          <p className="text-eyebrow mb-4 text-xs text-signal">BAsight &nbsp;·&nbsp; Business Intelligence &amp; Predictive Analytics</p>
          <h1 className="font-display text-6xl font-extrabold uppercase leading-[0.92] tracking-tight sm:text-8xl">
            Ring up
            <br />
            <span className="text-signal">your data.</span>
          </h1>
          <p className="mx-auto mt-6 max-w-md font-mono text-sm leading-relaxed text-paper/60">
            Hand over a raw sales export. We&apos;ll clean it, itemize it, and print
            out what your numbers actually say.
          </p>
        </div>

        <div
          onDragOver={(e) => {
            e.preventDefault();
            setIsDragging(true);
          }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={onDrop}
          onClick={() => inputRef.current?.click()}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") inputRef.current?.click();
          }}
          className={`group relative w-full max-w-xl cursor-pointer rounded-sm border-2 border-dashed p-10 text-center transition-all duration-300 ${
            isDragging
              ? "border-signal bg-signal/10 scale-[1.01]"
              : "border-paper/25 bg-ink-raised/60 hover:border-signal/60 hover:bg-ink-raised"
          }`}
        >
          <input
            ref={inputRef}
            type="file"
            accept={ALLOWED_EXTENSIONS.join(",")}
            className="sr-only"
            onChange={(e) => handleFile(e.target.files?.[0])}
          />

          <div className="mb-5 flex justify-center">
            <div
              className={`flex h-14 w-14 items-center justify-center rounded-full border-2 transition-colors ${
                isDragging ? "border-signal text-signal" : "border-paper/30 text-paper/50 group-hover:border-signal/60 group-hover:text-signal"
              }`}
            >
              <Upload size={22} strokeWidth={2} />
            </div>
          </div>

          <p className="font-display text-2xl font-bold uppercase tracking-wide">
            {isDragging ? "Drop it." : "Drop file, or click to browse"}
          </p>
          <p className="mt-2 font-mono text-xs text-paper/45">
            CSV or Excel &nbsp;·&nbsp; up to {MAX_SIZE_MB}MB &nbsp;·&nbsp; stays on this session only
          </p>

          <div className="mt-7 flex items-center justify-center gap-2 text-paper/25">
            <FileSpreadsheet size={14} />
            <div className="h-3 w-24 barcode text-paper/25" />
          </div>
        </div>

        {displayedError && (
          <div
            role="alert"
            className="animate-rise-in mt-5 flex items-center gap-2 rounded-sm border border-brick/50 bg-brick/10 px-4 py-2.5 font-mono text-xs text-brick"
          >
            {displayedError}
          </div>
        )}

        <p className="text-eyebrow mt-12 text-[10px] text-paper/25">
          BAsight &nbsp;/&nbsp; Built for financial decision-making
        </p>
      </div>
    </main>
  );
}
