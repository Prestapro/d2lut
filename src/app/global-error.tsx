'use client';

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-zinc-950 text-white flex items-center justify-center px-6">
        <main className="max-w-md text-center space-y-4">
          <h1 className="text-2xl font-bold text-amber-400">Something went wrong</h1>
          <p className="text-zinc-300">{error.message || 'Unexpected runtime error.'}</p>
          <button
            type="button"
            className="px-4 py-2 rounded-md bg-amber-500 text-black font-medium"
            onClick={reset}
          >
            Retry
          </button>
        </main>
      </body>
    </html>
  );
}
