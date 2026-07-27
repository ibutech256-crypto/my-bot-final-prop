"use client";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="min-h-screen bg-slate-950 text-white flex items-center justify-center p-8">
      <div className="max-w-md text-center space-y-4">
        <div className="h-16 w-16 rounded-2xl bg-red-900/30 border border-red-800/50 flex items-center justify-center mx-auto">
          <span className="text-3xl">⚠️</span>
        </div>
        <h1 className="text-xl font-bold text-white">Connection Interrupted</h1>
        <p className="text-sm text-slate-400">
          The dashboard encountered a temporary data glitch. This is usually resolved by reconnecting.
        </p>
        <div className="flex gap-3 justify-center">
          <button
            onClick={() => reset()}
            className="px-6 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm font-bold transition-colors"
          >
            🔄 Retry
          </button>
          <button
            onClick={() => window.location.reload()}
            className="px-6 py-2.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-white text-sm font-bold transition-colors"
          >
            🔁 Reload Page
          </button>
        </div>
        <p className="text-[10px] text-slate-600">
          {error?.message || "A temporary error occurred while loading the dashboard"}
        </p>
      </div>
    </div>
  );
}
