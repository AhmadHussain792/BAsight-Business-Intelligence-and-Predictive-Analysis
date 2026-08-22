"use client";

import { useCallback, useState } from "react";
import UploadScreen from "@/components/UploadScreen";
import ReceiptLoader from "@/components/ReceiptLoader";
import Dashboard from "@/components/Dashboard";
import { uploadDataset } from "@/lib/api";
import { ApiError, DatasetResponse } from "@/lib/types";

type Phase = "upload" | "processing" | "ready";

export default function Home() {
  const [phase, setPhase] = useState<Phase>("upload");
  const [fileName, setFileName] = useState("");
  const [result, setResult] = useState<DatasetResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleFileSelected = useCallback((file: File) => {
    setFileName(file.name);
    setResult(null);
    setErrorMessage(null);
    setPhase("processing");

    uploadDataset(file)
      .then((response) => setResult(response))
      .catch((err) => {
        const message = err instanceof ApiError ? err.message : "Something went wrong reading that file.";
        setErrorMessage(message);
      });
  }, []);

  const handleReset = useCallback(() => {
    setPhase("upload");
    setResult(null);
    setErrorMessage(null);
    setFileName("");
  }, []);

  if (phase === "upload") {
    return <UploadScreen onFileSelected={handleFileSelected} errorMessage={null} />;
  }

  if (phase === "processing") {
    return (
      <ReceiptLoader
        fileName={fileName}
        result={result}
        errorMessage={errorMessage}
        onFinished={() => setPhase("ready")}
        onDismissError={handleReset}
      />
    );
  }

  if (result) {
    return <Dashboard dataset={result} onReset={handleReset} />;
  }

  return null;
}
