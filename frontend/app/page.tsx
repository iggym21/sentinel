"use client";

import { useCallback, useEffect, useState } from "react";
import AddTickerForm from "@/components/AddTickerForm";
import WatchlistCard from "@/components/WatchlistCard";
import { getWatchlist, removeTicker } from "@/lib/api";
import type { WatchlistEntry } from "@/lib/types";

const POLL_INTERVAL_MS = 10_000;

export default function Home() {
  const [watchlist, setWatchlist] = useState<WatchlistEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await getWatchlist();
      setWatchlist(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load watchlist");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [refresh]);

  async function handleRemove(symbol: string) {
    const prior = watchlist;
    setWatchlist((current) => current.filter((entry) => entry.symbol !== symbol));
    try {
      await removeTicker(symbol);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to remove ticker");
      setWatchlist(prior);
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-8 px-6 py-10">
      <div className="flex flex-col gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
            Watchlist
          </h1>
          <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
            Tracking {watchlist.length} ticker{watchlist.length === 1 ? "" : "s"} · refreshes every
            10s
          </p>
        </div>
        <AddTickerForm onAdded={refresh} />
      </div>

      {error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-300">
          {error}
        </div>
      )}

      {loading ? (
        <p className="text-sm text-zinc-500 dark:text-zinc-400">Loading watchlist…</p>
      ) : watchlist.length === 0 ? (
        <div className="rounded-xl border border-dashed border-zinc-300 px-6 py-16 text-center text-sm text-zinc-500 dark:border-zinc-700 dark:text-zinc-400">
          No tickers yet. Add one above to start tracking.
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {watchlist.map((entry) => (
            <WatchlistCard key={entry.symbol} entry={entry} onRemove={handleRemove} />
          ))}
        </div>
      )}
    </div>
  );
}
