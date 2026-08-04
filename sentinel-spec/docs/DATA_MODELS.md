# Sentinel — Data Models

Use SQLAlchemy models mirroring these. Pydantic schemas for the API should match field names 1:1 where possible.

## Ticker (watchlist entry)
| Field | Type | Notes |
|---|---|---|
| id | UUID/int | PK |
| symbol | str | e.g. "AAPL", unique |
| added_at | datetime | |
| active | bool | soft-delete flag |

## PriceSnapshot
| Field | Type | Notes |
|---|---|---|
| id | UUID/int | PK |
| ticker_id | FK → Ticker | |
| timestamp | datetime | |
| price | float | |
| volume | int | |
| day_change_pct | float | |

*(Can be ephemeral/cached rather than fully persisted for MVP — persist only if you want historical charts.)*

## Anomaly
| Field | Type | Notes |
|---|---|---|
| id | UUID/int | PK |
| ticker_id | FK → Ticker | |
| detected_at | datetime | |
| trigger_type | enum | `volume_spike`, `price_move`, `news` |
| raw_metrics | JSON | the numbers that crossed threshold |
| watchdog_rationale | str | Claude's judgment-tier explanation |
| triggered_analyst_run | bool | whether this led to a full Analyst run |

## AgentRun
Represents one execution of the Analyst Agent (one investigation).

| Field | Type | Notes |
|---|---|---|
| id | UUID/int | PK |
| ticker_id | FK → Ticker | |
| anomaly_id | FK → Anomaly, nullable | null if manually triggered |
| started_at | datetime | |
| completed_at | datetime | nullable while running |
| status | enum | `running`, `complete`, `failed` |
| trace | JSON | ordered list of step objects — see below |
| brief_id | FK → Brief, nullable | set once complete |

**`trace` step object shape:**
```json
{
  "step": 1,
  "type": "tool_call",           // or "tool_result" or "reasoning" or "final"
  "tool_name": "get_filings",
  "input": {"ticker": "AAPL", "form_types": ["10-Q"], "limit": 1},
  "output": "...",                // present on tool_result steps
  "timestamp": "2026-08-03T14:22:01Z"
}
```

## Brief
| Field | Type | Notes |
|---|---|---|
| id | UUID/int | PK |
| ticker_id | FK → Ticker | |
| agent_run_id | FK → AgentRun | |
| created_at | datetime | |
| thesis | enum | `bullish`, `bearish`, `neutral` |
| confidence | int | 1-5 |
| summary | text | 2-4 sentence human-readable summary |
| evidence | JSON | list of `{claim: str, source_tool: str, source_ref: str}` |
| diff_from_prior | text, nullable | what changed vs. the previous brief on this ticker |
| suggested_action | enum, nullable | `buy`, `sell`, `hold` — stretch goal field |

## PaperTrade (stretch goal)
| Field | Type | Notes |
|---|---|---|
| id | UUID/int | PK |
| ticker_id | FK → Ticker | |
| brief_id | FK → Brief | the brief that suggested it |
| action | enum | `buy`, `sell` |
| entry_price | float | price at time of acceptance |
| entry_at | datetime | |
| status | enum | `open`, `closed` |
| exit_price | float, nullable | |
| exit_at | datetime, nullable | |
