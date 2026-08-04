/**
 * Typed fetch client for the Sentinel backend API (backend/api/*.py).
 *
 * - Plain `fetch`, no external HTTP library.
 * - `cache: "no-store"` on GETs so polling always gets fresh data.
 * - Non-2xx responses throw an Error whose message includes the response
 *   body text, so callers get the backend's actual error detail.
 */

import type { AgentRun, Brief, Ticker, WatchlistEntry } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Request failed with ${res.status} ${res.statusText}: ${body}`);
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return (await res.json()) as T;
}

/** GET /api/watchlist */
export async function getWatchlist(): Promise<WatchlistEntry[]> {
  const res = await fetch(`${API_BASE}/api/watchlist`, { cache: "no-store" });
  return handleResponse<WatchlistEntry[]>(res);
}

/** POST /api/watchlist */
export async function addTicker(symbol: string): Promise<Ticker> {
  const res = await fetch(`${API_BASE}/api/watchlist`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ symbol }),
  });
  return handleResponse<Ticker>(res);
}

/** DELETE /api/watchlist/{symbol} */
export async function removeTicker(symbol: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/watchlist/${encodeURIComponent(symbol)}`, {
    method: "DELETE",
  });
  return handleResponse<void>(res);
}

/** GET /api/briefs?ticker=&limit= */
export async function getBriefs(ticker?: string): Promise<Brief[]> {
  const url = new URL(`${API_BASE}/api/briefs`);
  if (ticker) {
    url.searchParams.set("ticker", ticker);
  }
  const res = await fetch(url, { cache: "no-store" });
  return handleResponse<Brief[]>(res);
}

/** GET /api/briefs/{brief_id} */
export async function getBrief(id: number): Promise<Brief & { agent_run: AgentRun }> {
  const res = await fetch(`${API_BASE}/api/briefs/${id}`, { cache: "no-store" });
  return handleResponse<Brief & { agent_run: AgentRun }>(res);
}

/** GET /api/tickers/{symbol}/history */
export async function getTickerHistory(
  symbol: string
): Promise<{ briefs: Brief[]; diff: string | null }> {
  const res = await fetch(`${API_BASE}/api/tickers/${encodeURIComponent(symbol)}/history`, {
    cache: "no-store",
  });
  return handleResponse<{ briefs: Brief[]; diff: string | null }>(res);
}

/** POST /api/tickers/{symbol}/run */
export async function runAnalystNow(symbol: string): Promise<Brief> {
  const res = await fetch(`${API_BASE}/api/tickers/${encodeURIComponent(symbol)}/run`, {
    method: "POST",
  });
  return handleResponse<Brief>(res);
}

/** POST /api/watchdog/tick */
export async function runWatchdogTick(): Promise<
  { ticker: string; crossed: boolean; triggered: boolean; anomaly_id: number | null }[]
> {
  const res = await fetch(`${API_BASE}/api/watchdog/tick`, { method: "POST" });
  return handleResponse<
    { ticker: string; crossed: boolean; triggered: boolean; anomaly_id: number | null }[]
  >(res);
}
