/**
 * TypeScript types mirroring the backend Pydantic `*Out` schemas 1:1
 * (field names verbatim, including snake_case — do not camelCase them).
 *
 * Sources:
 * - Ticker, WatchlistEntry     <- backend/schemas/ticker.py (TickerOut, WatchlistEntry)
 * - Brief, BriefDetail         <- backend/schemas/brief.py (BriefOut, BriefDetail)
 * - AgentRun, TraceStep        <- backend/schemas/agent_run.py (AgentRunOut) and
 *                                  backend/services/trace.py (TraceRecorder step shape)
 */

// backend/models/brief.py::Thesis
export type Thesis = "bullish" | "bearish" | "neutral";

// backend/models/brief.py::SuggestedAction
export type SuggestedAction = "buy" | "sell" | "hold";

// backend/models/agent_run.py::RunStatus
export type RunStatus = "running" | "complete" | "failed";

// backend/services/trace.py::TraceRecorder step `type` values
export type TraceStepType = "tool_call" | "tool_result" | "reasoning" | "final";

/**
 * One entry in AgentRun.trace (backend/services/trace.py).
 * All fields are always present as keys; unused fields for a given `type`
 * are `null` rather than omitted.
 */
export interface TraceStep {
  step: number;
  type: TraceStepType;
  tool_name: string | null;
  input: Record<string, unknown> | null;
  output: unknown | null;
  text: string | null;
  timestamp: string; // ISO-8601
}

/** backend/schemas/ticker.py::TickerOut */
export interface Ticker {
  id: number;
  symbol: string;
  added_at: string; // ISO-8601 datetime
  active: boolean;
}

/**
 * backend/schemas/ticker.py::WatchlistEntry
 * (TickerOut fields + computed fields for the /api/watchlist list view)
 */
export interface WatchlistEntry {
  id: number;
  symbol: string;
  added_at: string; // ISO-8601 datetime
  active: boolean;
  latest_price: number | null;
  day_change_pct: number | null;
  status: string;
  last_brief_at: string | null; // ISO-8601 datetime
}

/**
 * Shape of each item in Brief.evidence (backend/agents/claude_backend.py and
 * backend/agents/heuristic_backend.py "final" trace step output).
 */
export interface Evidence {
  claim: string;
  source_tool: string;
  source_ref: string | null;
}

/** backend/schemas/brief.py::BriefOut */
export interface Brief {
  id: number;
  ticker_id: number;
  agent_run_id: number;
  created_at: string; // ISO-8601 datetime
  thesis: Thesis;
  confidence: number;
  summary: string;
  evidence: Evidence[];
  diff_from_prior: string | null;
  suggested_action: SuggestedAction | null;
}

/** backend/schemas/agent_run.py::AgentRunOut */
export interface AgentRun {
  id: number;
  ticker_id: number;
  anomaly_id: number | null;
  started_at: string; // ISO-8601 datetime
  completed_at: string | null; // ISO-8601 datetime
  status: RunStatus;
  trace: TraceStep[];
  brief_id: number | null;
}

/** backend/schemas/brief.py::BriefDetail (BriefOut merged with the full AgentRun) */
export interface BriefDetail extends Brief {
  agent_run: AgentRun;
}
