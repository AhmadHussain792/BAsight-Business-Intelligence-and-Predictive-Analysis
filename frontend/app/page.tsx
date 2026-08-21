'use client';

import { useState } from 'react';
import {
  BarChart,
  Bar,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [stats, setStats] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const [chatInput, setChatInput] = useState('');
  const [chatAnswer, setChatAnswer] = useState('');
  const [chatLoading, setChatLoading] = useState(false);

  async function uploadFile() {
    if (!file) {
      setError('Please choose a CSV file first.');
      return;
    }

    const formData = new FormData();
    formData.append('uploaded_file', file);

    setLoading(true);
    setError(null);

    try {
      const response = await fetch('http://127.0.0.1:8000/file-upload', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Upload failed.');
      }

      const data = await response.json();
      setStats(data);
    } catch (err: any) {
      setError(err.message || 'Something went wrong.');
    } finally {
      setLoading(false);
    }
  }

  async function askQuestion() {
    if (!chatInput.trim()) {
      setError('Please enter a question.');
      return;
    }

    setChatLoading(true);
    setError(null);

    try {
      const response = await fetch('http://127.0.0.1:8000/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ question: chatInput }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Chat request failed.');
      }

      const data = await response.json();
      setChatAnswer(data.answer || 'No answer returned.');
    } catch (err: any) {
      setError(err.message || 'Chat failed.');
    } finally {
      setChatLoading(false);
    }
  }

  const chartData =
    stats && Array.isArray(stats.columns)
      ? stats.columns.map((col: string, index: number) => ({
          name: col,
          value: index + 1,
        }))
      : [];

  return (
    <main className="min-h-screen bg-slate-100 p-8 text-slate-800">
      <div className="mx-auto max-w-6xl space-y-6">
        <section className="rounded-xl border border-slate-300 bg-white p-6 shadow-md">
          <h1 className="text-2xl font-semibold">CSV Upload + AI Insights</h1>
          <p className="mt-2 text-sm text-slate-600">
            Upload a CSV file, view summary stats, and ask questions about your data.
          </p>

          <div className="mt-4 flex flex-col gap-4 md:flex-row">
            <input
              type="file"
              accept=".csv"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              className="block w-full rounded border border-slate-300 p-2"
            />

            <button
              onClick={uploadFile}
              className="rounded bg-blue-600 px-4 py-2 font-medium text-white hover:bg-blue-700"
            >
              {loading ? 'Uploading...' : 'Upload File'}
            </button>
          </div>

          {error && <p className="mt-4 text-sm text-red-600">{error}</p>}
        </section>

        {stats && (
          <section className="grid gap-6 md:grid-cols-2">
            <div className="rounded-xl border border-slate-300 bg-white p-6 shadow-md">
              <h2 className="text-lg font-semibold">Summary</h2>
              <div className="mt-4 space-y-2 text-sm">
                <p><strong>Total Rows:</strong> {stats.total_rows}</p>
                <p><strong>Total Columns:</strong> {stats.total_columns}</p>
                <p><strong>Columns:</strong> {stats.columns.join(', ')}</p>
              </div>
            </div>

            <div className="rounded-xl border border-slate-300 bg-white p-6 shadow-md">
              <h2 className="text-lg font-semibold">Columns Overview</h2>
              <div className="mt-4 h-64 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" />
                    <YAxis />
                    <Tooltip />
                    <Bar dataKey="value" fill="#3b82f6" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </section>
        )}

        <section className="rounded-xl border border-slate-300 bg-white p-6 shadow-md">
          <h2 className="text-lg font-semibold">Ask About Your Data</h2>
          <p className="mt-2 text-sm text-slate-600">
            Example: “What is the average amount?” or “Which row has the highest value??”
          </p>

          <div className="mt-4 flex flex-col gap-3">
            <textarea
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              rows={3}
              className="w-full rounded border border-slate-300 p-2"
              placeholder="Type your question here..."
            />

            <button
              onClick={askQuestion}
              className="rounded bg-green-600 px-4 py-2 font-medium text-white hover:bg-green-700"
            >
              {chatLoading ? 'Thinking...' : 'Ask AI'}
            </button>
          </div>

          {chatAnswer && (
            <div className="mt-4 rounded bg-slate-50 p-4">
              <h3 className="font-semibold">Answer</h3>
              <p className="mt-2 text-sm">{chatAnswer}</p>
            </div>
          )}
        </section>
      </div>
    </main>
  );
}