# Sentinel MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a working, locally-demoable Sentinel: a two-agent (Watchdog + Analyst) autonomous market research tool with a FastAPI backend, Next.js dashboard, and a persisted reasoning trace, per `sentinel-spec/docs/*`.

**Architecture:** FastAPI + SQLAlchemy backend with a pluggable data-provider layer (real Alpaca/EDGAR or a deterministic offline `DemoProvider`) and a pluggable reasoning-backend layer (real Claude tool-use loop, or a deterministic `HeuristicBackend` that runs the same tools and trace shape without an LLM). This makes the entire trigger → investigate → brief loop runnable and testable with zero external API keys, while staying a drop-in real integration once keys are added. Next.js App Router frontend polls the backend and renders the watchlist, brief feed, and an expandable reasoning-trace timeline.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2, APScheduler, `anthropic` SDK, httpx, pytest + pytest-mock; Next.js 14 (App Router), React, TypeScript, Tailwind CSS.

## Global Constraints

- DB: SQLite for local dev (`DATABASE_URL=sqlite:///./sentinel.db`), schema must also be Postgres-compatible (no SQLite-only types) per `sentinel-spec/docs/DATA_MODELS.md`.
- Model split: Watchdog uses `claude-haiku-4-5-20251001`, Analyst uses `claude-sonnet-5` — read from env, never hardcoded inline (`sentinel-spec/CLAUDE.md`).
- Every Analyst run and Watchdog judgment call persists its full reasoning trace — never discard intermediate steps (`sentinel-spec/docs/ARCHITECTURE.md` §6).
- No real trade execution, no auth, US equities only — MVP non-goals (`sentinel-spec/docs/PRD.md` §3).
- Cut from this build: Paper Trade Log (stretch, first on the spec's own cut list) and cloud deployment (needs the user's own Vercel/Render/Neon accounts — out of scope for an unattended build). Everything else in `sentinel-spec/docs/BUILD_PLAN.md` phases 1-4 is in scope.
- Secrets only via `.env`, never hardcoded (`sentinel-spec/CLAUDE.md`).
- Field names in Pydantic schemas mirror `sentinel-spec/docs/DATA_MODELS.md` 1:1.

## Shared Interfaces (defined once, used across tasks)

These are locked here so later tasks don't redefine them differently.

**`backend/services/trace.py` — `TraceRecorder`:**
```python
class TraceRecorder:
    def __init__(self) -> None: ...
    def record_tool_call(self, tool_name: str, input: dict) -> None: ...
    def record_tool_result(self, tool_name: str, output: object) -> None: ...
    def record_reasoning(self, text: str) -> None: ...
    def record_final(self, output: dict) -> None: ...
    def to_json(self) -> list[dict]: ...
```
Each recorded step dict shape: `{"step": int, "type": "tool_call"|"tool_result"|"reasoning"|"final", "tool_name": str|None, "input": dict|None, "output": object|None, "text": str|None, "timestamp": str (ISO8601)}` — matches `sentinel-spec/docs/DATA_MODELS.md` `AgentRun.trace` step shape (extra `reasoning`/`final` types are explicitly allowed by `sentinel-spec/docs/ARCHITECTURE.md` §6).

**`backend/providers/base.py` — provider protocols:**
```python
class MarketDataProvider(Protocol):
    def get_price_snapshot(self, ticker: str) -> PriceSnapshotData: ...
    def get_price_history(self, ticker: str, days: int) -> list[OHLCVBar]: ...
    def get_recent_news(self, ticker: str, days: int) -> list[NewsItem]: ...

class FilingsProvider(Protocol):
    def get_filings(self, ticker: str, form_types: list[str] | None, limit: int) -> list[FilingRef]: ...
    def get_filing_text(self, filing_url: str, max_chars: int) -> str: ...
```
`PriceSnapshotData`, `OHLCVBar`, `NewsItem`, `FilingRef` are `@dataclass`es defined in `backend/providers/base.py`:
```python
@dataclass
class PriceSnapshotData:
    ticker: str; price: float; volume: int; day_change_pct: float; avg_volume_20d: float; timestamp: str

@dataclass
class OHLCVBar:
    date: str; open: float; high: float; low: float; close: float; volume: int

@dataclass
class NewsItem:
    headline: str; summary: str; published_at: str; source: str

@dataclass
class FilingRef:
    ticker: str; form_type: str; filed_at: str; url: str; title: str
```

**`backend/agents/reasoning_backend.py` — reasoning protocol:**
```python
class ReasoningBackend(Protocol):
    def watchdog_judge(self, ticker: str, metrics: dict, headlines: list[NewsItem]) -> WatchdogDecision: ...
    def run_analyst(self, ticker: str, trigger_context: dict | None, tool_dispatch: dict[str, Callable], trace: TraceRecorder) -> AnalystBriefResult: ...

@dataclass
class WatchdogDecision:
    trigger: bool; rationale: str

@dataclass
class AnalystBriefResult:
    thesis: str; confidence: int; summary: str
    evidence: list[dict]  # [{"claim": str, "source_tool": str, "source_ref": str|None}]
    diff_from_prior: str | None; suggested_action: str | None
```
Two implementations: `ClaudeBackend` (real Messages API tool loop) and `HeuristicBackend` (deterministic, no LLM — runs the same tools, same trace shape, rule-based judgment). `backend/agents/backend_factory.py` exposes `get_reasoning_backend() -> ReasoningBackend`: returns `ClaudeBackend` if `ANTHROPIC_API_KEY` is set and `REASONING_BACKEND` env var isn't forced to `"heuristic"`, else `HeuristicBackend`. This is what makes the whole system testable and demoable with zero API keys, per this plan's Global Constraints.

**Tool dispatch factory — `backend/agents/tools/registry.py`:**
```python
def build_tool_dispatch(db: Session, market: MarketDataProvider, filings: FilingsProvider, ticker_id: int) -> dict[str, Callable[[dict], object]]:
    """Returns {tool_name: fn(input_dict) -> JSON-serializable result} for all tools except submit_brief/submit_decision, which are terminal and handled by the loop itself."""
```

---

## Phase 0 — Repo & Data Layer

### Task 1: Repo scaffold + git init

**Files:**
- Create: `backend/requirements.txt`, `backend/.gitignore`, `backend/config.py`
- Create: `.gitignore` (repo root), `README.md` (repo root, adapted from `sentinel-spec/README.md`)
- Create: `backend/.env.example` (copy of `sentinel-spec/docs/ENV_EXAMPLE.md` body, as real `.env.example`)

**Interfaces:**
- Produces: `backend/config.py::Settings` (pydantic-settings `BaseSettings`) with fields: `anthropic_api_key: str | None`, `watchdog_model: str = "claude-haiku-4-5-20251001"`, `analyst_model: str = "claude-sonnet-5"`, `alpaca_api_key: str | None`, `alpaca_secret_key: str | None`, `alpaca_base_url: str = "https://paper-api.alpaca.markets"`, `database_url: str = "sqlite:///./sentinel.db"`, `watchdog_interval_minutes: int = 15`, `volume_spike_threshold_multiplier: float = 2.0`, `price_move_threshold_pct: float = 3.0`, `environment: str = "development"`, `reasoning_backend: str | None = None` (`"llm"` or `"heuristic"`, `None` = auto-detect). Exposes a module-level `settings = Settings()` singleton.

- [ ] **Step 1: Init git repo and scaffold directories**

```bash
cd "/Users/ignatiusmartin/Documents/Personal/Projects/Sentinel"
git init
mkdir -p backend/agents/tools backend/api backend/models backend/schemas backend/providers backend/services backend/scripts backend/tests
```

- [ ] **Step 2: Write `backend/requirements.txt`**

```
fastapi
uvicorn[standard]
sqlalchemy>=2.0
alembic
pydantic>=2
pydantic-settings
anthropic
httpx
apscheduler
python-dotenv
pytest
pytest-mock
respx
```

- [ ] **Step 3: Write `backend/config.py`** (Settings class per Interfaces above, using `pydantic_settings.BaseSettings` with `model_config = SettingsConfigDict(env_file=".env")`)

- [ ] **Step 4: Write `backend/.env.example`** — transcribe the env block from `sentinel-spec/docs/ENV_EXAMPLE.md` verbatim.

- [ ] **Step 5: Write root `.gitignore`** covering `venv/`, `__pycache__/`, `*.db`, `.env`, `node_modules/`, `.next/`, `*.pyc`.

- [ ] **Step 6: Install deps and verify import**

```bash
cd backend && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt
python -c "from config import settings; print(settings.database_url)"
```
Expected: prints `sqlite:///./sentinel.db` with no errors.

- [ ] **Step 7: Write root `README.md`** adapted from `sentinel-spec/README.md` (same quick-start, drop the "Status: not yet scaffolded" section).

- [ ] **Step 8: Commit**

```bash
git add backend README.md .gitignore
git commit -m "chore: scaffold backend package and config"
```

---

### Task 2: DB engine/session + Alembic

**Files:**
- Create: `backend/database.py`
- Create: `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/script.py.mako`
- Test: `backend/tests/conftest.py`

**Interfaces:**
- Consumes: `backend/config.py::settings.database_url`
- Produces: `backend/database.py::Base` (declarative base), `engine`, `SessionLocal`, `get_db()` (FastAPI dependency generator yielding a `Session`, closing it after).

- [ ] **Step 1: Write `backend/database.py`**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 2: Init Alembic**

```bash
cd backend && source venv/bin/activate && alembic init alembic
```

- [ ] **Step 3: Edit `backend/alembic/env.py`** to import `Base` and set `target_metadata = Base.metadata`, and to read `sqlalchemy.url` from `config.settings.database_url` instead of `alembic.ini` (set `config.set_main_option("sqlalchemy.url", settings.database_url)` at top of `run_migrations_online`/`run_migrations_offline`).

- [ ] **Step 4: Write `backend/tests/conftest.py`** — pytest fixture `db_session` that creates an in-memory SQLite engine (`sqlite:///:memory:`), runs `Base.metadata.create_all`, yields a `Session`, and tears down after each test. Also a `client` fixture (added in Task 3 once models exist, stub it here as a placeholder import-safe file).

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import Base

@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
```

- [ ] **Step 5: Verify** `cd backend && source venv/bin/activate && pytest tests/ -v` — expect 0 tests collected, no import errors.

- [ ] **Step 6: Commit**

```bash
git add backend/database.py backend/alembic.ini backend/alembic backend/tests/conftest.py
git commit -m "chore: add DB session management and Alembic setup"
```

---

### Task 3: DB models + Pydantic schemas + first migration

**Files:**
- Create: `backend/models/ticker.py`, `backend/models/price_snapshot.py`, `backend/models/anomaly.py`, `backend/models/agent_run.py`, `backend/models/brief.py`, `backend/models/__init__.py`
- Create: `backend/schemas/ticker.py`, `backend/schemas/anomaly.py`, `backend/schemas/agent_run.py`, `backend/schemas/brief.py`, `backend/schemas/__init__.py`
- Test: `backend/tests/test_models.py`

**Interfaces:**
- Produces SQLAlchemy models exactly matching `sentinel-spec/docs/DATA_MODELS.md`:
  - `Ticker`: `id: int PK`, `symbol: str unique not null`, `added_at: datetime`, `active: bool default True`
  - `PriceSnapshot`: `id: int PK`, `ticker_id: FK Ticker`, `timestamp: datetime`, `price: float`, `volume: int`, `day_change_pct: float`
  - `Anomaly`: `id: int PK`, `ticker_id: FK Ticker`, `detected_at: datetime`, `trigger_type: str` (`"volume_spike"|"price_move"|"news"`), `raw_metrics: JSON`, `watchdog_rationale: str`, `triggered_analyst_run: bool default False`
  - `AgentRun`: `id: int PK`, `ticker_id: FK Ticker`, `anomaly_id: FK Anomaly nullable`, `started_at: datetime`, `completed_at: datetime nullable`, `status: str` (`"running"|"complete"|"failed"`), `trace: JSON` (list of step dicts, default `[]`), `brief_id: FK Brief nullable`
  - `Brief`: `id: int PK`, `ticker_id: FK Ticker`, `agent_run_id: FK AgentRun`, `created_at: datetime`, `thesis: str` (`"bullish"|"bearish"|"neutral"`), `confidence: int`, `summary: str`, `evidence: JSON` (list of `{claim, source_tool, source_ref}`), `diff_from_prior: str nullable`, `suggested_action: str nullable` (`"buy"|"sell"|"hold"`)
  - Use plain `Integer` PKs (SQLite/Postgres portable), `String` for enum-like fields with a Python `enum.Enum` + SQLAlchemy `Enum` type validated at the ORM layer, `JSON` column type from `sqlalchemy` (works on both SQLite and Postgres).
- Produces Pydantic schemas (in `backend/schemas/`) named `TickerOut`, `TickerCreate`, `AnomalyOut`, `AgentRunOut`, `BriefOut`, each `model_config = ConfigDict(from_attributes=True)`, field names identical to the ORM models above.

- [ ] **Step 1: Write the failing test** `backend/tests/test_models.py`

```python
from datetime import datetime, timezone
from models.ticker import Ticker
from models.anomaly import Anomaly
from models.agent_run import AgentRun
from models.brief import Brief

def test_create_ticker_and_related_rows(db_session):
    t = Ticker(symbol="AAPL", added_at=datetime.now(timezone.utc), active=True)
    db_session.add(t)
    db_session.commit()
    db_session.refresh(t)
    assert t.id is not None

    anomaly = Anomaly(
        ticker_id=t.id, detected_at=datetime.now(timezone.utc),
        trigger_type="volume_spike", raw_metrics={"volume_ratio": 2.4},
        watchdog_rationale="Volume 2.4x average with no corroborating news.",
        triggered_analyst_run=True,
    )
    db_session.add(anomaly)
    db_session.commit()
    db_session.refresh(anomaly)

    run = AgentRun(
        ticker_id=t.id, anomaly_id=anomaly.id, started_at=datetime.now(timezone.utc),
        status="running", trace=[{"step": 1, "type": "reasoning", "text": "start"}],
    )
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)

    brief = Brief(
        ticker_id=t.id, agent_run_id=run.id, created_at=datetime.now(timezone.utc),
        thesis="bullish", confidence=4, summary="Strong quarter.",
        evidence=[{"claim": "Revenue up 12% YoY", "source_tool": "get_filings", "source_ref": "10-Q"}],
    )
    db_session.add(brief)
    db_session.commit()
    db_session.refresh(brief)

    run.brief_id = brief.id
    db_session.commit()

    assert anomaly.ticker_id == t.id
    assert run.trace[0]["type"] == "reasoning"
    assert brief.evidence[0]["claim"] == "Revenue up 12% YoY"
    assert run.brief_id == brief.id
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && source venv/bin/activate && pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'models.ticker'`

- [ ] **Step 3: Implement the models** — write `backend/models/ticker.py`, `price_snapshot.py`, `anomaly.py`, `agent_run.py`, `brief.py` per the field spec in Interfaces above, all inheriting `Base` from `database.py`. Add relationships (`Ticker.price_snapshots`, `Ticker.anomalies`, `Ticker.agent_runs`, `Ticker.briefs`, `Anomaly.agent_run`, `AgentRun.brief`) with `back_populates` where natural. Import all five models in `backend/models/__init__.py` so `Base.metadata` sees them.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_models.py -v`
Expected: PASS

- [ ] **Step 5: Write Pydantic schemas** in `backend/schemas/*.py` per Interfaces above.

- [ ] **Step 6: Generate and apply first Alembic migration**

```bash
cd backend && source venv/bin/activate
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
python -c "import sqlite3; c=sqlite3.connect('sentinel.db'); print(c.execute(\"select name from sqlite_master where type='table'\").fetchall())"
```
Expected: prints all 5 table names (`ticker`, `price_snapshot`, `anomaly`, `agent_run`, `brief` — actual table names as SQLAlchemy generates them).

- [ ] **Step 7: Commit**

```bash
git add backend/models backend/schemas backend/tests/test_models.py backend/alembic/versions
git commit -m "feat: add DB models, schemas, and initial migration"
```

---

## Phase 1 — Providers & Threshold Detection

### Task 4: Provider base types + DemoProvider

**Files:**
- Create: `backend/providers/base.py`, `backend/providers/demo_provider.py`, `backend/providers/__init__.py`
- Test: `backend/tests/test_demo_provider.py`

**Interfaces:**
- Produces: dataclasses `PriceSnapshotData`, `OHLCVBar`, `NewsItem`, `FilingRef` and Protocols `MarketDataProvider`, `FilingsProvider` exactly as specified in "Shared Interfaces" above (`backend/providers/base.py`).
- Produces: `backend/providers/demo_provider.py::DemoProvider` implementing `MarketDataProvider`. Must be **deterministic** given `(ticker, days)` — seed a `random.Random` from `hash(ticker)` so repeated calls in the same process for the same ticker return internally-consistent series (no wall-clock randomness), but different tickers look different. `get_price_snapshot` derives `day_change_pct` and volume from the tail of `get_price_history`'s series so the two stay consistent with each other.

- [ ] **Step 1: Write the failing test** `backend/tests/test_demo_provider.py`

```python
from providers.demo_provider import DemoProvider

def test_price_history_is_deterministic_and_shaped():
    p = DemoProvider()
    bars1 = p.get_price_history("AAPL", days=10)
    bars2 = p.get_price_history("AAPL", days=10)
    assert [b.close for b in bars1] == [b.close for b in bars2]
    assert len(bars1) == 10
    assert all(b.low <= b.close <= b.high for b in bars1)

def test_price_snapshot_consistent_with_history():
    p = DemoProvider()
    snap = p.get_price_snapshot("AAPL")
    history = p.get_price_history("AAPL", days=30)
    assert snap.price == history[-1].close
    assert snap.ticker == "AAPL"

def test_different_tickers_differ():
    p = DemoProvider()
    a = [b.close for b in p.get_price_history("AAPL", days=5)]
    b = [b.close for b in p.get_price_history("MSFT", days=5)]
    assert a != b

def test_recent_news_returns_items():
    p = DemoProvider()
    news = p.get_recent_news("AAPL", days=7)
    assert len(news) >= 1
    assert all(n.headline for n in news)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_demo_provider.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'providers.base'`

- [ ] **Step 3: Implement** `backend/providers/base.py` (dataclasses + Protocols) and `backend/providers/demo_provider.py::DemoProvider` — build the price series with a seeded RNG doing a simple random walk from a per-ticker base price (e.g. `base = 50 + (hash(ticker) % 400)`), daily pct moves `rng.gauss(0, 0.015)`, occasionally inject one larger move (`rng.random() < 0.1` → move *= 4) so threshold-crossing scenarios are reachable in tests/demo. `get_recent_news` returns 1-4 templated headlines referencing the ticker and recent price direction (e.g. `f"{ticker} shares {'climb' if pct>0 else 'slip'} as investors weigh recent trading activity"`).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_demo_provider.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/providers backend/tests/test_demo_provider.py
git commit -m "feat: add provider protocols and deterministic DemoProvider"
```

---

### Task 5: AlpacaProvider (real integration)

**Files:**
- Create: `backend/providers/alpaca_provider.py`
- Test: `backend/tests/test_alpaca_provider.py`

**Interfaces:**
- Consumes: `backend/providers/base.py` protocols/dataclasses (Task 4), `backend/config.py::settings`
- Produces: `AlpacaProvider(api_key: str, secret_key: str, base_url: str)` implementing `MarketDataProvider` via `httpx.Client`, hitting Alpaca's `/v2/stocks/{symbol}/bars` (history), `/v2/stocks/{symbol}/snapshot` (snapshot), and `/v1beta1/news` (news) endpoints with `APCA-API-KEY-ID`/`APCA-API-SECRET-KEY` headers.

- [ ] **Step 1: Write the failing test** `backend/tests/test_alpaca_provider.py` — mock HTTP with `respx`:

```python
import respx
import httpx
from providers.alpaca_provider import AlpacaProvider

@respx.mock
def test_get_price_history_parses_bars():
    respx.get("https://paper-api.alpaca.markets/v2/stocks/AAPL/bars").mock(
        return_value=httpx.Response(200, json={"bars": [
            {"t": "2026-08-01T00:00:00Z", "o": 190.1, "h": 192.0, "l": 189.5, "c": 191.2, "v": 1000000},
        ]})
    )
    provider = AlpacaProvider(api_key="k", secret_key="s", base_url="https://paper-api.alpaca.markets")
    bars = provider.get_price_history("AAPL", days=1)
    assert bars[0].close == 191.2
    assert bars[0].volume == 1000000

@respx.mock
def test_get_recent_news_parses_articles():
    respx.get("https://paper-api.alpaca.markets/v1beta1/news").mock(
        return_value=httpx.Response(200, json={"news": [
            {"headline": "AAPL beats estimates", "summary": "...", "created_at": "2026-08-01T12:00:00Z", "source": "benzinga"},
        ]})
    )
    provider = AlpacaProvider(api_key="k", secret_key="s", base_url="https://paper-api.alpaca.markets")
    news = provider.get_recent_news("AAPL", days=7)
    assert news[0].headline == "AAPL beats estimates"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_alpaca_provider.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'providers.alpaca_provider'`

- [ ] **Step 3: Implement `backend/providers/alpaca_provider.py`** — `AlpacaProvider` with `httpx.Client(base_url=..., headers={"APCA-API-KEY-ID": api_key, "APCA-API-SECRET-KEY": secret_key})`, methods parsing the above response shapes into the shared dataclasses. `get_price_snapshot` computes `day_change_pct` from the latest two bars and `avg_volume_20d` from a 20-bar history call.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_alpaca_provider.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/providers/alpaca_provider.py backend/tests/test_alpaca_provider.py
git commit -m "feat: add real Alpaca market data provider"
```

---

### Task 6: Threshold-based anomaly detector

**Files:**
- Create: `backend/services/threshold_detector.py`
- Test: `backend/tests/test_threshold_detector.py`

**Interfaces:**
- Consumes: `PriceSnapshotData` (Task 4)
- Produces: `backend/services/threshold_detector.py::check_thresholds(snapshot: PriceSnapshotData, volume_multiplier: float, price_move_pct: float) -> ThresholdResult`
```python
@dataclass
class ThresholdResult:
    crossed: bool
    trigger_type: str | None  # "volume_spike" | "price_move" | None
    raw_metrics: dict          # {"volume": .., "avg_volume_20d": .., "volume_ratio": .., "day_change_pct": ..}
```
If both volume and price cross, `trigger_type="price_move"` takes precedence (price moves are the more decisive signal) and `raw_metrics` still includes both numbers.

- [ ] **Step 1: Write the failing test** `backend/tests/test_threshold_detector.py`

```python
from providers.base import PriceSnapshotData
from services.threshold_detector import check_thresholds

def make_snapshot(volume=1_000_000, avg_volume=1_000_000, day_change_pct=0.5):
    return PriceSnapshotData(ticker="AAPL", price=190.0, volume=volume, day_change_pct=day_change_pct, avg_volume_20d=avg_volume, timestamp="2026-08-04T14:00:00Z")

def test_quiet_day_does_not_cross():
    result = check_thresholds(make_snapshot(), volume_multiplier=2.0, price_move_pct=3.0)
    assert result.crossed is False
    assert result.trigger_type is None

def test_volume_spike_crosses():
    result = check_thresholds(make_snapshot(volume=2_500_000, avg_volume=1_000_000), volume_multiplier=2.0, price_move_pct=3.0)
    assert result.crossed is True
    assert result.trigger_type == "volume_spike"
    assert result.raw_metrics["volume_ratio"] == 2.5

def test_price_move_crosses():
    result = check_thresholds(make_snapshot(day_change_pct=4.2), volume_multiplier=2.0, price_move_pct=3.0)
    assert result.crossed is True
    assert result.trigger_type == "price_move"

def test_price_move_takes_precedence_when_both_cross():
    result = check_thresholds(make_snapshot(volume=3_000_000, avg_volume=1_000_000, day_change_pct=5.0), volume_multiplier=2.0, price_move_pct=3.0)
    assert result.trigger_type == "price_move"
    assert "volume_ratio" in result.raw_metrics
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_threshold_detector.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'services.threshold_detector'`

- [ ] **Step 3: Implement** `backend/services/threshold_detector.py::check_thresholds` per spec above (pure function, no I/O).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_threshold_detector.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/threshold_detector.py backend/tests/test_threshold_detector.py
git commit -m "feat: add code-level volume/price threshold detector"
```

---

## Phase 2 — Analyst Agent

### Task 7: EDGAR filings provider

**Files:**
- Create: `backend/providers/edgar_provider.py`
- Test: `backend/tests/test_edgar_provider.py`

**Interfaces:**
- Produces: `backend/providers/edgar_provider.py::EdgarProvider` implementing `FilingsProvider` (Task 4), using SEC EDGAR full-text search (`https://efts.sec.gov/LATEST/search-index?q=...&forms=...`) for `get_filings`, and `httpx.get(filing_url)` + a simple HTML-tag-stripper for `get_filing_text`. Must set a descriptive `User-Agent` header (SEC requires this — e.g. `"Sentinel research-agent contact@example.com"`, configurable).

- [ ] **Step 1: Write the failing test** `backend/tests/test_edgar_provider.py`

```python
import respx
import httpx
from providers.edgar_provider import EdgarProvider

@respx.mock
def test_get_filings_parses_results():
    respx.get(url__regex=r"https://efts\.sec\.gov/LATEST/search-index.*").mock(
        return_value=httpx.Response(200, json={"hits": {"hits": [
            {"_source": {"form": "10-Q", "file_date": "2026-07-15", "display_names": ["APPLE INC"]},
             "_id": "0000320193-26-000050:aapl-20260630.htm"},
        ]}})
    )
    provider = EdgarProvider(user_agent="Sentinel test@example.com")
    filings = provider.get_filings("AAPL", form_types=["10-Q"], limit=5)
    assert filings[0].form_type == "10-Q"
    assert filings[0].url.startswith("https://www.sec.gov/")

@respx.mock
def test_get_filing_text_strips_html_and_truncates():
    respx.get("https://www.sec.gov/Archives/edgar/data/example.htm").mock(
        return_value=httpx.Response(200, text="<html><body><p>Revenue grew 12%.</p></body></html>")
    )
    provider = EdgarProvider(user_agent="Sentinel test@example.com")
    text = provider.get_filing_text("https://www.sec.gov/Archives/edgar/data/example.htm", max_chars=1000)
    assert "Revenue grew 12%" in text
    assert "<p>" not in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_edgar_provider.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'providers.edgar_provider'`

- [ ] **Step 3: Implement `backend/providers/edgar_provider.py`** — build the EDGAR full-text search URL from ticker/form_types/limit, parse `hits.hits[]._source` into `FilingRef` (construct the Archives URL from the `_id` field: `cik` + accession + filename), and for `get_filing_text` strip tags with a small regex/`html.parser` pass and truncate to `max_chars`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_edgar_provider.py -v`
Expected: PASS

- [ ] **Step 5: Manual live sanity check (not part of automated suite)**

```bash
cd backend && source venv/bin/activate
python -c "from providers.edgar_provider import EdgarProvider; p = EdgarProvider(user_agent='Sentinel demo@example.com'); print(p.get_filings('AAPL', ['10-Q'], 2))"
```
Expected: prints real, current AAPL 10-Q filing references (confirms live EDGAR reachability — don't fail the task if the network sandbox blocks this, just note the result).

- [ ] **Step 6: Commit**

```bash
git add backend/providers/edgar_provider.py backend/tests/test_edgar_provider.py
git commit -m "feat: add SEC EDGAR filings provider"
```

---

### Task 8: Analyst tool functions + registry

**Files:**
- Create: `backend/agents/tools/get_filings.py`, `get_filing_text.py`, `get_recent_news.py`, `get_price_history.py`, `calculate_ratios.py`, `get_prior_briefs.py`, `schemas.py`, `registry.py`, `__init__.py`
- Test: `backend/tests/test_tools.py`

**Interfaces:**
- Consumes: `MarketDataProvider`/`FilingsProvider` (Task 4/5/7), `Brief`/`AgentRun` models (Task 3), `TraceRecorder` shape (defined, implemented in Task 9)
- Produces: `backend/agents/tools/schemas.py::TOOL_SCHEMAS` — a `list[dict]` containing the exact JSON schemas from `sentinel-spec/docs/AGENT_TOOLS.md` (`get_filings`, `get_filing_text`, `get_recent_news`, `get_price_history`, `calculate_ratios`, `get_prior_briefs`, `submit_brief`), transcribed verbatim.
- Produces: `backend/agents/tools/registry.py::build_tool_dispatch(db: Session, market: MarketDataProvider, filings: FilingsProvider, ticker: str) -> dict[str, Callable[[dict], dict]]` mapping the 6 non-terminal tool names to functions taking the tool's `input` dict and returning a JSON-serializable dict/list (each individual tool function lives in its own file per the Files list, taking `(market, filings, db, ticker, **kwargs)` and returning plain dicts/lists — `registry.py` just closes over `db`/`market`/`filings`/`ticker` and forwards `**tool_input`).
- `calculate_ratios(market, ticker)` computes what's derivable from `get_price_history` alone for the MVP (no fundamentals API in scope): rolling volatility, price trend over 5/20/60 days, and volume trend — returns `{"ticker": ..., "volatility_20d_pct": ..., "trend_5d_pct": ..., "trend_20d_pct": ..., "avg_volume_20d": ..., "note": "Derived from price/volume history only; no fundamentals data source configured for this MVP."}` (be honest in the note rather than fabricating P/E from no data).
- `get_prior_briefs(db, ticker, limit)` queries `Brief` joined to `Ticker` by symbol, ordered by `created_at desc`, returns list of `{id, created_at, thesis, confidence, summary, diff_from_prior}`.

- [ ] **Step 1: Write the failing test** `backend/tests/test_tools.py`

```python
from unittest.mock import MagicMock
from providers.base import OHLCVBar, NewsItem, FilingRef
from agents.tools.get_price_history import get_price_history
from agents.tools.get_recent_news import get_recent_news
from agents.tools.calculate_ratios import calculate_ratios
from agents.tools.get_prior_briefs import get_prior_briefs
from models.ticker import Ticker
from models.brief import Brief
from models.agent_run import AgentRun
from datetime import datetime, timezone

def test_get_price_history_serializes_bars():
    market = MagicMock()
    market.get_price_history.return_value = [OHLCVBar(date="2026-08-01", open=1, high=2, low=0.5, close=1.5, volume=100)]
    result = get_price_history(market, "AAPL", days=30)
    assert result[0]["close"] == 1.5

def test_get_recent_news_serializes_items():
    market = MagicMock()
    market.get_recent_news.return_value = [NewsItem(headline="H", summary="S", published_at="2026-08-01", source="src")]
    result = get_recent_news(market, "AAPL", days=7)
    assert result[0]["headline"] == "H"

def test_calculate_ratios_uses_price_history_only():
    market = MagicMock()
    market.get_price_history.return_value = [
        OHLCVBar(date=f"2026-07-{i:02d}", open=100+i, high=101+i, low=99+i, close=100+i, volume=1000) for i in range(1, 21)
    ]
    result = calculate_ratios(market, "AAPL")
    assert "trend_20d_pct" in result
    assert "fundamentals data source" in result["note"]

def test_get_prior_briefs_returns_ordered(db_session):
    t = Ticker(symbol="AAPL", added_at=datetime.now(timezone.utc), active=True)
    db_session.add(t); db_session.commit(); db_session.refresh(t)
    run = AgentRun(ticker_id=t.id, started_at=datetime.now(timezone.utc), status="complete", trace=[])
    db_session.add(run); db_session.commit(); db_session.refresh(run)
    b1 = Brief(ticker_id=t.id, agent_run_id=run.id, created_at=datetime.now(timezone.utc), thesis="neutral", confidence=3, summary="s1", evidence=[])
    db_session.add(b1); db_session.commit()

    result = get_prior_briefs(db_session, "AAPL", limit=3)
    assert len(result) == 1
    assert result[0]["summary"] == "s1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tools.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agents'`

- [ ] **Step 3: Implement** each tool file as a thin adapter from provider dataclasses / DB rows to plain dicts, per Interfaces above, plus `backend/agents/tools/schemas.py::TOOL_SCHEMAS` (verbatim from `sentinel-spec/docs/AGENT_TOOLS.md`) and `backend/agents/tools/registry.py::build_tool_dispatch`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_tools.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/agents/tools backend/tests/test_tools.py
git commit -m "feat: add Analyst tool functions, schemas, and dispatch registry"
```

---

### Task 9: TraceRecorder + reasoning backend scaffolding

**Files:**
- Create: `backend/services/trace.py`
- Create: `backend/agents/reasoning_backend.py`, `backend/agents/backend_factory.py`, `backend/agents/__init__.py`
- Test: `backend/tests/test_trace.py`, `backend/tests/test_backend_factory.py`

**Interfaces:**
- Produces: `TraceRecorder` exactly per "Shared Interfaces" above.
- Produces: `ReasoningBackend` Protocol, `WatchdogDecision`, `AnalystBriefResult` dataclasses, exactly per "Shared Interfaces" above (`reasoning_backend.py`).
- Produces: `backend/agents/backend_factory.py::get_reasoning_backend() -> ReasoningBackend` — returns `ClaudeBackend()` (Task 10 defines it) if `settings.anthropic_api_key` is truthy and `settings.reasoning_backend != "heuristic"`; else returns `HeuristicBackend()` (Task 10 defines it) if `settings.reasoning_backend != "llm"`; raises `RuntimeError` only if `reasoning_backend == "llm"` was forced but no API key is set.

- [ ] **Step 1: Write the failing test** `backend/tests/test_trace.py`

```python
from services.trace import TraceRecorder

def test_trace_records_steps_in_order_with_incrementing_step_numbers():
    trace = TraceRecorder()
    trace.record_reasoning("Starting research on AAPL")
    trace.record_tool_call("get_price_history", {"ticker": "AAPL", "days": 30})
    trace.record_tool_result("get_price_history", [{"close": 190.0}])
    trace.record_final({"thesis": "bullish"})

    steps = trace.to_json()
    assert [s["step"] for s in steps] == [1, 2, 3, 4]
    assert steps[0]["type"] == "reasoning" and steps[0]["text"] == "Starting research on AAPL"
    assert steps[1]["type"] == "tool_call" and steps[1]["tool_name"] == "get_price_history"
    assert steps[2]["type"] == "tool_result" and steps[2]["output"] == [{"close": 190.0}]
    assert steps[3]["type"] == "final" and steps[3]["output"] == {"thesis": "bullish"}
    assert all("timestamp" in s for s in steps)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_trace.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'services.trace'`

- [ ] **Step 3: Implement `backend/services/trace.py::TraceRecorder`** per Shared Interfaces (use `datetime.now(timezone.utc).isoformat()` for timestamps).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_trace.py -v`
Expected: PASS

- [ ] **Step 5: Write the failing test** `backend/tests/test_backend_factory.py`

```python
import agents.backend_factory as backend_factory

def test_uses_heuristic_when_no_api_key(monkeypatch):
    monkeypatch.setattr(backend_factory.settings, "anthropic_api_key", None)
    monkeypatch.setattr(backend_factory.settings, "reasoning_backend", None)
    backend = backend_factory.get_reasoning_backend()
    assert type(backend).__name__ == "HeuristicBackend"

def test_uses_claude_when_api_key_present(monkeypatch):
    monkeypatch.setattr(backend_factory.settings, "anthropic_api_key", "sk-test")
    monkeypatch.setattr(backend_factory.settings, "reasoning_backend", None)
    backend = backend_factory.get_reasoning_backend()
    assert type(backend).__name__ == "ClaudeBackend"

def test_forced_heuristic_overrides_api_key(monkeypatch):
    monkeypatch.setattr(backend_factory.settings, "anthropic_api_key", "sk-test")
    monkeypatch.setattr(backend_factory.settings, "reasoning_backend", "heuristic")
    backend = backend_factory.get_reasoning_backend()
    assert type(backend).__name__ == "HeuristicBackend"
```

- [ ] **Step 6: Run test to verify it fails** (module/backends don't exist yet — expected `ModuleNotFoundError` / `ImportError`)

- [ ] **Step 7: Implement `backend/agents/reasoning_backend.py`** (Protocol + dataclasses) and a minimal `backend_factory.py` that imports `ClaudeBackend`/`HeuristicBackend` lazily inside the function body (to avoid a hard import-time dependency on `anthropic` client construction) — full backend bodies are stubbed with `raise NotImplementedError` for now, filled in Task 10 & 12.

- [ ] **Step 8: Run test to verify it passes**

Run: `pytest tests/test_backend_factory.py -v`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add backend/services/trace.py backend/agents/reasoning_backend.py backend/agents/backend_factory.py backend/tests/test_trace.py backend/tests/test_backend_factory.py
git commit -m "feat: add trace recorder and reasoning-backend selection"
```

---

### Task 10: Analyst agent loop — HeuristicBackend + ClaudeBackend

**Files:**
- Create: `backend/agents/heuristic_backend.py`, `backend/agents/claude_backend.py`, `backend/agents/claude_client.py`
- Modify: `backend/agents/backend_factory.py` (wire real imports)
- Test: `backend/tests/test_heuristic_backend.py`, `backend/tests/test_claude_backend.py`

**Interfaces:**
- Consumes: `ReasoningBackend`/`AnalystBriefResult`/`WatchdogDecision` (Task 9), `build_tool_dispatch` (Task 8), `TraceRecorder` (Task 9), `TOOL_SCHEMAS` (Task 8)
- Produces: `HeuristicBackend.run_analyst(ticker, trigger_context, tool_dispatch, trace) -> AnalystBriefResult` — calls, **in this fixed order**, `get_prior_briefs`, `get_price_history`, `get_recent_news`, `get_filings`, `calculate_ratios` from `tool_dispatch`, recording a `record_tool_call`+`record_tool_result` pair for each (matching exactly what the real loop would record), then derives `thesis`/`confidence`/`summary`/`evidence`/`diff_from_prior` from the *real* returned data with simple rules (e.g. `thesis = "bullish" if trend_20d_pct > 1 else "bearish" if trend_20d_pct < -1 else "neutral"`; `confidence` scaled by `|trend_20d_pct|` clamped to 1-5; `evidence` cites the actual numbers/headlines fetched, `source_tool` set accurately). Ends with `trace.record_final(...)`.
- Produces: `ClaudeBackend.run_analyst(...)` — the real Messages API tool-use loop per `sentinel-spec/docs/ARCHITECTURE.md` §2.2: loop calling `client.messages.create(model=settings.analyst_model, system=ANALYST_SYSTEM_PROMPT, messages=messages, tools=TOOL_SCHEMAS)`, recording each `tool_use` content block via `trace.record_tool_call`, executing it via `tool_dispatch[name](input)`, recording the result via `trace.record_tool_result`, appending a `tool_result` message, looping until a `submit_brief` tool call appears, at which point its `input` becomes the returned `AnalystBriefResult` (validate required fields are present, raise `ValueError` with a clear message if not). Cap the loop at 15 iterations, raising `RuntimeError("Analyst agent exceeded max tool-use iterations")` past that.
- Produces: `backend/agents/claude_client.py::get_anthropic_client() -> anthropic.Anthropic` — lazy singleton, constructed only when first called, using `settings.anthropic_api_key`.
- Produces: `ANALYST_SYSTEM_PROMPT` constant in `claude_backend.py`, incorporating the guidance from `sentinel-spec/docs/AGENT_TOOLS.md` "System prompt guidance" section (gather evidence from multiple tools, check `get_prior_briefs` early, cite `source_tool` per claim, call `submit_brief` as the final action).

- [ ] **Step 1: Write the failing test** `backend/tests/test_heuristic_backend.py`

```python
from services.trace import TraceRecorder
from agents.heuristic_backend import HeuristicBackend

def make_dispatch():
    calls = []
    def tool(name, result):
        def _fn(input):
            calls.append(name)
            return result
        return _fn
    dispatch = {
        "get_prior_briefs": tool("get_prior_briefs", []),
        "get_price_history": tool("get_price_history", [{"date": "2026-08-01", "close": 100}, {"date": "2026-08-02", "close": 105}]),
        "get_recent_news": tool("get_recent_news", [{"headline": "AAPL rallies", "summary": "", "published_at": "2026-08-02", "source": "x"}]),
        "get_filings": tool("get_filings", [{"form_type": "10-Q", "url": "https://example.com/f.htm", "filed_at": "2026-07-15"}]),
        "calculate_ratios": tool("calculate_ratios", {"trend_20d_pct": 5.0, "trend_5d_pct": 2.0, "volatility_20d_pct": 1.1, "avg_volume_20d": 1000, "note": "..."}),
    }
    return dispatch, calls

def test_heuristic_backend_calls_all_tools_and_produces_brief():
    dispatch, calls = make_dispatch()
    trace = TraceRecorder()
    backend = HeuristicBackend()
    result = backend.run_analyst("AAPL", trigger_context=None, tool_dispatch=dispatch, trace=trace)

    assert calls == ["get_prior_briefs", "get_price_history", "get_recent_news", "get_filings", "calculate_ratios"]
    assert result.thesis == "bullish"
    assert 1 <= result.confidence <= 5
    assert len(result.evidence) >= 1
    assert any(e["source_tool"] == "calculate_ratios" for e in result.evidence)

    steps = trace.to_json()
    tool_call_names = [s["tool_name"] for s in steps if s["type"] == "tool_call"]
    assert tool_call_names == ["get_prior_briefs", "get_price_history", "get_recent_news", "get_filings", "calculate_ratios"]
    assert steps[-1]["type"] == "final"

def test_heuristic_backend_bearish_case():
    dispatch, _ = make_dispatch()
    dispatch["calculate_ratios"] = lambda input: {"trend_20d_pct": -6.0, "trend_5d_pct": -3.0, "volatility_20d_pct": 2.0, "avg_volume_20d": 1000, "note": "..."}
    result = HeuristicBackend().run_analyst("AAPL", None, dispatch, TraceRecorder())
    assert result.thesis == "bearish"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_heuristic_backend.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agents.heuristic_backend'`

- [ ] **Step 3: Implement `backend/agents/heuristic_backend.py::HeuristicBackend`** per Interfaces above.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_heuristic_backend.py -v`
Expected: PASS

- [ ] **Step 5: Write the failing test** `backend/tests/test_claude_backend.py` (mock the Anthropic client entirely — no network/key needed)

```python
from unittest.mock import MagicMock
from services.trace import TraceRecorder
from agents.claude_backend import ClaudeBackend

class FakeContentBlock:
    def __init__(self, type_, **kwargs):
        self.type = type_
        for k, v in kwargs.items():
            setattr(self, k, v)

class FakeResponse:
    def __init__(self, stop_reason, content):
        self.stop_reason = stop_reason
        self.content = content

def test_claude_backend_loops_until_submit_brief():
    fake_client = MagicMock()
    tool_call_1 = FakeContentBlock("tool_use", id="t1", name="get_prior_briefs", input={"ticker": "AAPL", "limit": 3})
    submit = FakeContentBlock("tool_use", id="t2", name="submit_brief", input={
        "thesis": "neutral", "confidence": 3, "summary": "Mixed signals.",
        "evidence": [{"claim": "No major move", "source_tool": "get_prior_briefs"}],
    })
    fake_client.messages.create.side_effect = [
        FakeResponse("tool_use", [tool_call_1]),
        FakeResponse("tool_use", [submit]),
    ]
    dispatch = {"get_prior_briefs": lambda input: []}
    trace = TraceRecorder()

    backend = ClaudeBackend(client=fake_client)
    result = backend.run_analyst("AAPL", trigger_context=None, tool_dispatch=dispatch, trace=trace)

    assert result.thesis == "neutral"
    assert fake_client.messages.create.call_count == 2
    tool_calls = [s for s in trace.to_json() if s["type"] == "tool_call"]
    assert tool_calls[0]["tool_name"] == "get_prior_briefs"

def test_claude_backend_raises_on_missing_required_field():
    fake_client = MagicMock()
    bad_submit = FakeContentBlock("tool_use", id="t1", name="submit_brief", input={"thesis": "neutral"})
    fake_client.messages.create.side_effect = [FakeResponse("tool_use", [bad_submit])]
    backend = ClaudeBackend(client=fake_client)
    try:
        backend.run_analyst("AAPL", None, {}, TraceRecorder())
        assert False, "expected ValueError"
    except ValueError:
        pass
```

- [ ] **Step 6: Run test to verify it fails**

Run: `pytest tests/test_claude_backend.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agents.claude_backend'`

- [ ] **Step 7: Implement `backend/agents/claude_client.py`** (`get_anthropic_client`) and **`backend/agents/claude_backend.py::ClaudeBackend`** (`__init__(self, client=None)` — uses `client or get_anthropic_client()`, so tests can inject a fake without touching real credentials), plus `ANALYST_SYSTEM_PROMPT`.

- [ ] **Step 8: Run test to verify it passes**

Run: `pytest tests/test_claude_backend.py -v`
Expected: PASS

- [ ] **Step 9: Wire `backend/agents/backend_factory.py`** to import and return real `ClaudeBackend`/`HeuristicBackend` (replacing the Task 9 stubs). Re-run Task 9's `test_backend_factory.py` to confirm still green.

- [ ] **Step 10: Commit**

```bash
git add backend/agents/heuristic_backend.py backend/agents/claude_backend.py backend/agents/claude_client.py backend/agents/backend_factory.py backend/tests/test_heuristic_backend.py backend/tests/test_claude_backend.py
git commit -m "feat: implement Analyst agent loop (Claude tool-use + offline heuristic backend)"
```

---

### Task 11: Analyst orchestration service + CLI script

**Files:**
- Create: `backend/services/analyst_service.py`
- Create: `backend/scripts/run_analyst.py`
- Test: `backend/tests/test_analyst_service.py`

**Interfaces:**
- Consumes: `build_tool_dispatch` (Task 8), `get_reasoning_backend` (Task 9/10), `AgentRun`/`Brief`/`Ticker` models (Task 3), `MarketDataProvider`/`FilingsProvider` (Task 4/5/7)
- Produces: `backend/services/analyst_service.py::run_analyst_for_ticker(db: Session, ticker_symbol: str, market: MarketDataProvider, filings: FilingsProvider, anomaly_id: int | None = None, backend: ReasoningBackend | None = None) -> Brief` — looks up/creates the `Ticker` row, creates an `AgentRun` row (`status="running"`), builds the tool dispatch, runs `backend.run_analyst(...)` (default `get_reasoning_backend()`), on success writes `AgentRun.trace`, `status="complete"`, `completed_at`, creates the `Brief` row (computing `diff_from_prior` by comparing against the most recent prior `Brief` for this ticker if `run_analyst` didn't already set one — simple text diff: compare `thesis`/`confidence` and note the change, e.g. `"Thesis unchanged (neutral); confidence up from 3 to 4."` or `"Thesis flipped from bearish to bullish."` or `None` if no prior brief exists), links `AgentRun.brief_id`, commits, returns the `Brief`. On any exception from `backend.run_analyst`, sets `AgentRun.status="failed"`, `completed_at`, commits, and re-raises.

- [ ] **Step 1: Write the failing test** `backend/tests/test_analyst_service.py`

```python
from unittest.mock import MagicMock
from datetime import datetime, timezone
from services.analyst_service import run_analyst_for_ticker
from agents.reasoning_backend import AnalystBriefResult
from models.agent_run import AgentRun
from models.brief import Brief

def make_fake_backend(result):
    backend = MagicMock()
    backend.run_analyst.return_value = result
    return backend

def test_run_analyst_creates_run_and_brief(db_session):
    result = AnalystBriefResult(
        thesis="bullish", confidence=4, summary="Strong signals.",
        evidence=[{"claim": "c", "source_tool": "get_price_history", "source_ref": None}],
        diff_from_prior=None, suggested_action="buy",
    )
    backend = make_fake_backend(result)
    market, filings = MagicMock(), MagicMock()

    brief = run_analyst_for_ticker(db_session, "AAPL", market, filings, backend=backend)

    assert brief.thesis == "bullish"
    run = db_session.query(AgentRun).filter_by(id=brief.agent_run_id).one()
    assert run.status == "complete"
    assert run.brief_id == brief.id

def test_run_analyst_computes_diff_from_prior(db_session):
    from models.ticker import Ticker
    t = Ticker(symbol="AAPL", added_at=datetime.now(timezone.utc), active=True)
    db_session.add(t); db_session.commit(); db_session.refresh(t)
    prior_run = AgentRun(ticker_id=t.id, started_at=datetime.now(timezone.utc), status="complete", trace=[])
    db_session.add(prior_run); db_session.commit(); db_session.refresh(prior_run)
    prior_brief = Brief(ticker_id=t.id, agent_run_id=prior_run.id, created_at=datetime.now(timezone.utc), thesis="bearish", confidence=2, summary="s", evidence=[])
    db_session.add(prior_brief); db_session.commit()

    result = AnalystBriefResult(thesis="bullish", confidence=4, summary="Turned around.", evidence=[], diff_from_prior=None, suggested_action=None)
    backend = make_fake_backend(result)
    brief = run_analyst_for_ticker(db_session, "AAPL", MagicMock(), MagicMock(), backend=backend)

    assert brief.diff_from_prior is not None
    assert "bearish" in brief.diff_from_prior and "bullish" in brief.diff_from_prior

def test_run_analyst_marks_failed_on_exception(db_session):
    backend = MagicMock()
    backend.run_analyst.side_effect = RuntimeError("boom")
    try:
        run_analyst_for_ticker(db_session, "AAPL", MagicMock(), MagicMock(), backend=backend)
        assert False, "expected RuntimeError"
    except RuntimeError:
        pass
    run = db_session.query(AgentRun).one()
    assert run.status == "failed"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_analyst_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'services.analyst_service'`

- [ ] **Step 3: Implement `backend/services/analyst_service.py::run_analyst_for_ticker`** per spec above.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_analyst_service.py -v`
Expected: PASS

- [ ] **Step 5: Write `backend/scripts/run_analyst.py`** — CLI: `python scripts/run_analyst.py AAPL` — opens a real `SessionLocal()`, builds `DemoProvider()` for market data + `EdgarProvider(user_agent=...)` for filings (or `AlpacaProvider` if `settings.alpaca_api_key` set), calls `run_analyst_for_ticker`, pretty-prints the resulting `Brief` (thesis, confidence, summary, evidence) and the trace step count.

- [ ] **Step 6: Run it end-to-end**

```bash
cd backend && source venv/bin/activate
python scripts/run_analyst.py AAPL
```
Expected: prints a brief with thesis/confidence/summary/evidence, using the offline `HeuristicBackend` (no `ANTHROPIC_API_KEY` set) and real EDGAR data. Confirms Task 7's live EDGAR call plus the full tool loop work end-to-end.

- [ ] **Step 7: Commit**

```bash
git add backend/services/analyst_service.py backend/scripts/run_analyst.py backend/tests/test_analyst_service.py
git commit -m "feat: add Analyst orchestration service and CLI runner"
```

---

## Phase 3 — Watchdog + Wiring

### Task 12: Watchdog judgment call

**Files:**
- Modify: `backend/agents/heuristic_backend.py`, `backend/agents/claude_backend.py` (add `watchdog_judge`)
- Test: `backend/tests/test_watchdog_judge.py`

**Interfaces:**
- Consumes: `WatchdogDecision` (Task 9), `NewsItem` (Task 4)
- Produces: `HeuristicBackend.watchdog_judge(ticker, metrics: dict, headlines: list[NewsItem]) -> WatchdogDecision` — rule: `trigger=True` if `metrics` contains `volume_ratio >= 3.0` OR `abs(day_change_pct) >= 5.0` OR (threshold crossed at all AND at least one headline mentions the ticker's symbol case-insensitively, treated as corroborating news); otherwise `False`. `rationale` is a templated sentence naming the actual metric values (e.g. `f"Volume at {ratio:.1f}x average with no corroborating headlines — likely routine noise."`).
- Produces: `ClaudeBackend.watchdog_judge(...)` — single `client.messages.create(model=settings.watchdog_model, system=WATCHDOG_SYSTEM_PROMPT, messages=[...], tools=[SUBMIT_DECISION_SCHEMA], tool_choice={"type": "tool", "name": "submit_decision"})` call; parses the `submit_decision` tool_use input into `WatchdogDecision`. `SUBMIT_DECISION_SCHEMA` transcribed verbatim from `sentinel-spec/docs/AGENT_TOOLS.md`. `WATCHDOG_SYSTEM_PROMPT` per that doc's "System prompt guidance" (distinguish routine volatility from genuinely unusual activity, use headlines as context, be conservative).

- [ ] **Step 1: Write the failing test** `backend/tests/test_watchdog_judge.py`

```python
from providers.base import NewsItem
from agents.heuristic_backend import HeuristicBackend
from agents.claude_backend import ClaudeBackend
from unittest.mock import MagicMock

def test_heuristic_triggers_on_large_volume_ratio():
    decision = HeuristicBackend().watchdog_judge("AAPL", {"volume_ratio": 3.5, "day_change_pct": 1.0}, [])
    assert decision.trigger is True

def test_heuristic_does_not_trigger_on_mild_move_no_news():
    decision = HeuristicBackend().watchdog_judge("AAPL", {"volume_ratio": 2.1, "day_change_pct": 1.5}, [])
    assert decision.trigger is False

def test_heuristic_triggers_on_large_price_move():
    decision = HeuristicBackend().watchdog_judge("AAPL", {"volume_ratio": 1.0, "day_change_pct": -6.0}, [])
    assert decision.trigger is True

class FakeContentBlock:
    def __init__(self, type_, **kwargs):
        self.type = type_
        for k, v in kwargs.items():
            setattr(self, k, v)

class FakeResponse:
    def __init__(self, stop_reason, content):
        self.stop_reason = stop_reason
        self.content = content

def test_claude_backend_parses_submit_decision():
    fake_client = MagicMock()
    submit = FakeContentBlock("tool_use", id="t1", name="submit_decision", input={
        "trigger": True, "rationale": "Volume 4x average right after an earnings headline.",
    })
    fake_client.messages.create.return_value = FakeResponse("tool_use", [submit])

    backend = ClaudeBackend(client=fake_client)
    decision = backend.watchdog_judge(
        "AAPL",
        {"volume_ratio": 4.0, "day_change_pct": 2.0},
        [NewsItem(headline="AAPL beats estimates", summary="", published_at="2026-08-04", source="src")],
    )

    assert decision.trigger is True
    assert "earnings" in decision.rationale
    call_kwargs = fake_client.messages.create.call_args.kwargs
    assert call_kwargs["tool_choice"] == {"type": "tool", "name": "submit_decision"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_watchdog_judge.py -v`
Expected: FAIL — `AttributeError: 'HeuristicBackend' object has no attribute 'watchdog_judge'`

- [ ] **Step 3: Implement `watchdog_judge`** on both backends per Interfaces above. Add `SUBMIT_DECISION_SCHEMA` to `backend/agents/tools/schemas.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_watchdog_judge.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/agents/heuristic_backend.py backend/agents/claude_backend.py backend/agents/tools/schemas.py backend/tests/test_watchdog_judge.py
git commit -m "feat: add Watchdog judgment-tier reasoning to both backends"
```

---

### Task 13: Watchdog tick orchestration

**Files:**
- Create: `backend/services/watchdog_service.py`
- Test: `backend/tests/test_watchdog_service.py`

**Interfaces:**
- Consumes: `check_thresholds` (Task 6), `ReasoningBackend.watchdog_judge` (Task 12), `run_analyst_for_ticker` (Task 11), `Ticker`/`Anomaly` models (Task 3)
- Produces: `backend/services/watchdog_service.py::run_watchdog_tick(db: Session, market: MarketDataProvider, filings: FilingsProvider, backend: ReasoningBackend | None = None) -> list[dict]` — for every `active=True` `Ticker`: fetch snapshot + news via `market`, run `check_thresholds`; if not crossed, continue (no DB write — matches architecture doc's "log a quiet check" as a no-op for MVP, to avoid an unbounded `PriceSnapshot` table; note this simplification in a code comment referencing the spec's "can be ephemeral" caveat); if crossed, call `backend.watchdog_judge(...)`, create an `Anomaly` row with `raw_metrics`, `watchdog_rationale`, `trigger_type`; if `decision.trigger`, set `triggered_analyst_run=True`, call `run_analyst_for_ticker(db, ticker.symbol, market, filings, anomaly_id=anomaly.id, backend=backend if isinstance(backend, ...) else None)` — **note:** `watchdog_judge` and `run_analyst` may reasonably use different backend instances since they're different concerns; pass `backend=None` to `run_analyst_for_ticker` so it resolves its own default via `get_reasoning_backend()` unless a backend was explicitly injected for testing (accept an optional `analyst_backend` param mirroring `backend` for test injection). Returns a list of per-ticker result dicts: `{"ticker": symbol, "crossed": bool, "triggered": bool, "anomaly_id": int|None}` for the caller (API layer / seed script) to summarize.

- [ ] **Step 1: Write the failing test** `backend/tests/test_watchdog_service.py`

```python
from unittest.mock import MagicMock
from datetime import datetime, timezone
from providers.base import PriceSnapshotData
from models.ticker import Ticker
from models.anomaly import Anomaly
from agents.reasoning_backend import WatchdogDecision, AnalystBriefResult
from services.watchdog_service import run_watchdog_tick

def test_quiet_ticker_produces_no_anomaly(db_session):
    t = Ticker(symbol="AAPL", added_at=datetime.now(timezone.utc), active=True)
    db_session.add(t); db_session.commit()
    market = MagicMock()
    market.get_price_snapshot.return_value = PriceSnapshotData(ticker="AAPL", price=190, volume=1_000_000, day_change_pct=0.3, avg_volume_20d=1_000_000, timestamp="t")
    market.get_recent_news.return_value = []
    results = run_watchdog_tick(db_session, market, MagicMock())
    assert results == [{"ticker": "AAPL", "crossed": False, "triggered": False, "anomaly_id": None}]
    assert db_session.query(Anomaly).count() == 0

def test_crossed_but_not_triggered_creates_anomaly_without_analyst_run(db_session):
    t = Ticker(symbol="AAPL", added_at=datetime.now(timezone.utc), active=True)
    db_session.add(t); db_session.commit()
    market = MagicMock()
    market.get_price_snapshot.return_value = PriceSnapshotData(ticker="AAPL", price=190, volume=2_500_000, day_change_pct=0.5, avg_volume_20d=1_000_000, timestamp="t")
    market.get_recent_news.return_value = []
    backend = MagicMock()
    backend.watchdog_judge.return_value = WatchdogDecision(trigger=False, rationale="Just noise.")

    results = run_watchdog_tick(db_session, market, MagicMock(), backend=backend)

    assert results[0]["crossed"] is True
    assert results[0]["triggered"] is False
    anomaly = db_session.query(Anomaly).one()
    assert anomaly.triggered_analyst_run is False

def test_crossed_and_triggered_runs_analyst(db_session):
    t = Ticker(symbol="AAPL", added_at=datetime.now(timezone.utc), active=True)
    db_session.add(t); db_session.commit()
    market = MagicMock()
    market.get_price_snapshot.return_value = PriceSnapshotData(ticker="AAPL", price=190, volume=3_000_000, day_change_pct=4.0, avg_volume_20d=1_000_000, timestamp="t")
    market.get_recent_news.return_value = []
    backend = MagicMock()
    backend.watchdog_judge.return_value = WatchdogDecision(trigger=True, rationale="Big move, real news.")
    backend.run_analyst.return_value = AnalystBriefResult(thesis="bullish", confidence=4, summary="s", evidence=[], diff_from_prior=None, suggested_action=None)

    results = run_watchdog_tick(db_session, market, MagicMock(), backend=backend)

    assert results[0]["triggered"] is True
    anomaly = db_session.query(Anomaly).one()
    assert anomaly.triggered_analyst_run is True
    backend.run_analyst.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_watchdog_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'services.watchdog_service'`

- [ ] **Step 3: Implement `backend/services/watchdog_service.py::run_watchdog_tick`** per spec above (note the simplified single-`backend`-param signature the tests use — both `watchdog_judge` and the analyst run use the same injected `backend` when provided, defaulting each independently to `get_reasoning_backend()` otherwise).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_watchdog_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/watchdog_service.py backend/tests/test_watchdog_service.py
git commit -m "feat: wire Watchdog tick — threshold check to judgment call to Analyst trigger"
```

---

### Task 14: FastAPI app, API routers, scheduler wiring

**Files:**
- Create: `backend/main.py`
- Create: `backend/api/watchlist.py`, `backend/api/briefs.py`, `backend/api/tickers.py`, `backend/api/runs.py`, `backend/api/__init__.py`
- Create: `backend/scheduler.py`
- Test: `backend/tests/test_api.py`

**Interfaces:**
- Produces REST endpoints (all under `/api`, CORS open to `http://localhost:3000` for local dev):
  - `GET /api/watchlist` → `list[TickerOut & {latest_price, day_change_pct, status, last_brief_at}]` — `status` derived per-ticker: `"investigating"` if an `AgentRun` with `status="running"` exists for it, else `"triggered"` if the most recent `Anomaly.triggered_analyst_run` is `True` and its `AgentRun` completed within the last hour, else `"quiet"`.
  - `POST /api/watchlist` body `{"symbol": str}` → creates/reactivates a `Ticker`, returns `TickerOut`.
  - `DELETE /api/watchlist/{symbol}` → sets `active=False`, `204`.
  - `GET /api/briefs?ticker=<symbol optional>&limit=50` → `list[BriefOut]` reverse-chronological.
  - `GET /api/briefs/{brief_id}` → `BriefOut` merged with its `AgentRunOut` (including `trace`).
  - `GET /api/tickers/{symbol}/history` → `{"briefs": list[BriefOut], "diff": str | None}` where `diff` is the latest brief's `diff_from_prior`.
  - `POST /api/tickers/{symbol}/run` → synchronously calls `run_analyst_for_ticker` (manual "run now" fallback per `sentinel-spec/docs/BUILD_PLAN.md` cut list), returns the created `BriefOut`.
  - `POST /api/watchdog/tick` → synchronously calls `run_watchdog_tick` across the active watchlist, returns its result list (manual trigger for demo/testing without waiting for the scheduler).
- Produces `backend/scheduler.py::start_scheduler(app_state)` — `apscheduler.schedulers.background.BackgroundScheduler`, adds a job calling `run_watchdog_tick` every `settings.watchdog_interval_minutes` minutes; the job function builds fresh `SessionLocal()` + providers each run and closes the session after. Gate: only actually executes the tick body if `settings.environment != "production"` OR current time is within US market hours on a weekday (9:30-16:00 America/New_York) — implement the weekday/hours check inline with `datetime.now(ZoneInfo("America/New_York"))`, no external holiday calendar needed for MVP.
- Produces `backend/main.py` — FastAPI app with lifespan startup calling `start_scheduler`/shutdown calling `scheduler.shutdown()`, includes all routers, `CORSMiddleware`.

- [ ] **Step 1: Write the failing test** `backend/tests/test_api.py` — use `fastapi.testclient.TestClient`, override `get_db` dependency to use the `db_session` fixture, monkeypatch `api.watchlist`'s/`api.runs`' module-level provider/backend constructors to fakes so no network/API key is touched:

```python
from fastapi.testclient import TestClient
from datetime import datetime, timezone
import main
from database import get_db
from models.ticker import Ticker

def make_client(db_session):
    main.app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(main.app)

def test_post_and_get_watchlist(db_session):
    client = make_client(db_session)
    resp = client.post("/api/watchlist", json={"symbol": "AAPL"})
    assert resp.status_code == 200
    assert resp.json()["symbol"] == "AAPL"

    resp = client.get("/api/watchlist")
    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["symbol"] == "AAPL"
    assert body[0]["status"] == "quiet"

def test_delete_watchlist_soft_deletes(db_session):
    client = make_client(db_session)
    client.post("/api/watchlist", json={"symbol": "AAPL"})
    resp = client.delete("/api/watchlist/AAPL")
    assert resp.status_code == 204
    resp = client.get("/api/watchlist")
    assert resp.json() == []

def test_get_briefs_empty(db_session):
    client = make_client(db_session)
    resp = client.get("/api/briefs")
    assert resp.status_code == 200
    assert resp.json() == []

def test_get_brief_detail_includes_trace(db_session):
    from models.agent_run import AgentRun
    from models.brief import Brief
    t = Ticker(symbol="AAPL", added_at=datetime.now(timezone.utc), active=True)
    db_session.add(t); db_session.commit(); db_session.refresh(t)
    run = AgentRun(ticker_id=t.id, started_at=datetime.now(timezone.utc), status="complete", trace=[{"step": 1, "type": "final", "output": {}}])
    db_session.add(run); db_session.commit(); db_session.refresh(run)
    brief = Brief(ticker_id=t.id, agent_run_id=run.id, created_at=datetime.now(timezone.utc), thesis="neutral", confidence=3, summary="s", evidence=[])
    db_session.add(brief); db_session.commit(); db_session.refresh(brief)

    client = make_client(db_session)
    resp = client.get(f"/api/briefs/{brief.id}")
    assert resp.status_code == 200
    assert resp.json()["agent_run"]["trace"][0]["type"] == "final"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_api.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'main'`

- [ ] **Step 3: Implement** `backend/api/*.py` routers and `backend/main.py` per Interfaces above (do not implement `/run` or `/watchdog/tick` provider wiring yet beyond what's testable — those two endpoints construct `DemoProvider`/`EdgarProvider`/`AlpacaProvider` (real if keys set, else `DemoProvider`/`EdgarProvider`) and `get_reasoning_backend()` internally at request time, not covered by the Step 1 tests since they'd hit real EDGAR; leave them implemented but untested here — Task 15's seed script exercises them for real).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_api.py -v`
Expected: PASS

- [ ] **Step 5: Implement `backend/scheduler.py`** per Interfaces above.

- [ ] **Step 6: Boot the server and smoke-test manually**

```bash
cd backend && source venv/bin/activate
uvicorn main:app --reload &
sleep 2
curl -s -X POST localhost:8000/api/watchlist -H "content-type: application/json" -d '{"symbol":"AAPL"}'
curl -s localhost:8000/api/watchlist
kill %1
```
Expected: both curls return valid JSON, second one shows AAPL with `status: "quiet"`.

- [ ] **Step 7: Commit**

```bash
git add backend/main.py backend/api backend/scheduler.py backend/tests/test_api.py
git commit -m "feat: add FastAPI app, REST routers, and APScheduler wiring"
```

---

### Task 15: Seed/demo data script

**Files:**
- Create: `backend/scripts/seed_demo_data.py`

**Interfaces:**
- Consumes: `run_watchdog_tick` (Task 13), `run_analyst_for_ticker` (Task 11), `DemoProvider` (Task 4), `EdgarProvider` (Task 7)
- Produces: a script runnable as `python scripts/seed_demo_data.py` that: creates 8 watchlist tickers (`AAPL, MSFT, NVDA, TSLA, AMZN, GOOGL, META, AMD`), force-creates at least one `Anomaly` with `triggered_analyst_run=True` for one ticker (bypass `check_thresholds` — directly construct metrics that would cross, to guarantee demo data regardless of `DemoProvider`'s random walk that tick), runs the Analyst twice for that same ticker (a few seconds apart, in-process — second run naturally produces a non-null `diff_from_prior` against the first) so the ticker-history diff view has content, and runs one more Analyst call for a second ticker so the brief feed has >1 entries. Prints a summary (`ticker, thesis, confidence` per brief created) at the end.

- [ ] **Step 1: Write `backend/scripts/seed_demo_data.py`** per spec above, using `DemoProvider()` and `EdgarProvider(user_agent="Sentinel demo@example.com")` (never `AlpacaProvider` — seeding must not require keys).

- [ ] **Step 2: Run it and verify**

```bash
cd backend && source venv/bin/activate
rm -f sentinel.db && alembic upgrade head
python scripts/seed_demo_data.py
python -c "
from database import SessionLocal
from models.brief import Brief
from models.ticker import Ticker
db = SessionLocal()
print('tickers:', db.query(Ticker).count())
print('briefs:', db.query(Brief).count())
for b in db.query(Brief).all():
    print(b.ticker_id, b.thesis, b.confidence, b.diff_from_prior)
"
```
Expected: 8 tickers, >=3 briefs, at least one non-null `diff_from_prior`.

- [ ] **Step 3: Commit**

```bash
git add backend/scripts/seed_demo_data.py
git commit -m "feat: add demo/seed data script for offline demoability"
```

---

## Phase 4 — Frontend Dashboard

### Task 16: Next.js scaffold + API client + types

**Files:**
- Create: `frontend/` (via `create-next-app`), `frontend/lib/api.ts`, `frontend/lib/types.ts`, `frontend/.env.local.example`

**Interfaces:**
- Produces TS types in `frontend/lib/types.ts` mirroring the Pydantic `*Out` schemas from Task 3/14: `Ticker`, `TraceStep`, `AgentRun`, `Brief`, `WatchlistEntry` (Ticker + `latest_price`, `day_change_pct`, `status`, `last_brief_at`).
- Produces `frontend/lib/api.ts`:
```typescript
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
export async function getWatchlist(): Promise<WatchlistEntry[]>
export async function addTicker(symbol: string): Promise<Ticker>
export async function removeTicker(symbol: string): Promise<void>
export async function getBriefs(ticker?: string): Promise<Brief[]>
export async function getBrief(id: number): Promise<Brief & { agent_run: AgentRun }>
export async function getTickerHistory(symbol: string): Promise<{ briefs: Brief[]; diff: string | null }>
export async function runAnalystNow(symbol: string): Promise<Brief>
export async function runWatchdogTick(): Promise<{ ticker: string; crossed: boolean; triggered: boolean; anomaly_id: number | null }[]>
```

- [ ] **Step 1: Scaffold Next.js app**

```bash
cd "/Users/ignatiusmartin/Documents/Personal/Projects/Sentinel"
npx create-next-app@latest frontend --typescript --tailwind --app --eslint --no-src-dir --import-alias "@/*" --use-npm
```

- [ ] **Step 2: Write `frontend/lib/types.ts`** per Interfaces above.

- [ ] **Step 3: Write `frontend/lib/api.ts`** per Interfaces above (plain `fetch`, `cache: "no-store"` on GETs so polling always gets fresh data; throw on non-2xx with the response body text in the error message).

- [ ] **Step 4: Write `frontend/.env.local.example`** — `NEXT_PUBLIC_API_URL=http://localhost:8000`.

- [ ] **Step 5: Verify it type-checks and builds**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors (page.tsx from the scaffold still uses default content at this point — fine).

- [ ] **Step 6: Commit**

```bash
git add frontend
git commit -m "chore: scaffold Next.js frontend with typed API client"
```

---

### Task 17: Watchlist dashboard page

**Files:**
- Modify: `frontend/app/page.tsx`, `frontend/app/layout.tsx`
- Create: `frontend/components/WatchlistCard.tsx`, `frontend/components/StatusBadge.tsx`, `frontend/components/AddTickerForm.tsx`

**Interfaces:**
- Consumes: `getWatchlist`, `addTicker`, `removeTicker` (Task 16)
- Produces: `frontend/app/page.tsx` — client component (`"use client"`), polls `getWatchlist()` every 10s via `useEffect` + `setInterval`, renders a responsive grid of `WatchlistCard`, an `AddTickerForm` at top, nav links to `/briefs`.
- `WatchlistCard` props: `{ entry: WatchlistEntry; onRemove: (symbol: string) => void }` — shows symbol, price, day change (colored green/red), `StatusBadge`, last brief date, remove button, link to `/tickers/[symbol]`.
- `StatusBadge` props: `{ status: "quiet" | "triggered" | "investigating" }` — distinct colors/labels per state.

**Note:** per this plan's Global Constraints, frontend correctness is verified by `tsc --noEmit` + `next build` + a live click-through in Chrome (Task 20), not a Jest suite — keep components simple and typed rather than adding a frontend test runner for an MVP with one primary user.

- [ ] **Step 1: Implement `StatusBadge.tsx`, `AddTickerForm.tsx`, `WatchlistCard.tsx`** per Interfaces above, styled with Tailwind (dark-mode aware via `dark:` classes, since `frontend-design` conventions favor a considered, non-default look — use a focused neutral+accent palette, not default `create-next-app` boilerplate styling).

- [ ] **Step 2: Implement `frontend/app/page.tsx`** wiring polling + the components above; `frontend/app/layout.tsx` sets page title "Sentinel" and a simple top nav (`Watchlist` / `Briefs`).

- [ ] **Step 3: Type-check**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/page.tsx frontend/app/layout.tsx frontend/components
git commit -m "feat: add watchlist dashboard page"
```

---

### Task 18: Brief feed + brief detail + reasoning trace

**Files:**
- Create: `frontend/app/briefs/page.tsx`, `frontend/app/briefs/[id]/page.tsx`
- Create: `frontend/components/BriefCard.tsx`, `frontend/components/ThesisBadge.tsx`, `frontend/components/ConfidenceMeter.tsx`, `frontend/components/ReasoningTrace.tsx`

**Interfaces:**
- Consumes: `getBriefs`, `getBrief` (Task 16)
- `frontend/app/briefs/page.tsx` — polls `getBriefs()` every 10s, renders reverse-chronological list of `BriefCard` (each links to `/briefs/[id]`).
- `BriefCard` props: `{ brief: Brief }` — ticker, `ThesisBadge`, `ConfidenceMeter`, summary snippet, created date.
- `frontend/app/briefs/[id]/page.tsx` — server-or-client component fetching `getBrief(id)`, shows full brief (thesis, confidence, summary, evidence list with `source_tool`/`source_ref`, `diff_from_prior` if present, `suggested_action` if present) and an expandable `ReasoningTrace` below it.
- `ReasoningTrace` props: `{ trace: TraceStep[] }` — renders an ordered, expandable timeline: each step shows its `type` icon/label, and on click/expand shows `tool_name` + pretty-printed `input`/`output`/`text` (whichever fields are present for that step type). Collapsed by default per-step except the first, to keep the initial view scannable; a "step N of M" summary line stays visible when collapsed (name + one-line preview of input/output).

- [ ] **Step 1: Implement `ThesisBadge.tsx`, `ConfidenceMeter.tsx`** (1-5 filled/unfilled dots or bar), `BriefCard.tsx`.

- [ ] **Step 2: Implement `ReasoningTrace.tsx`** per Interfaces above — this is the demo's "wow" factor per `sentinel-spec/docs/PRD.md` §2, give it real design attention (clear visual distinction between `tool_call`/`tool_result`/`reasoning`/`final` step types, e.g. left-side colored rail + icon per type).

- [ ] **Step 3: Implement `frontend/app/briefs/page.tsx` and `frontend/app/briefs/[id]/page.tsx`** per Interfaces above.

- [ ] **Step 4: Type-check**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/app/briefs frontend/components/BriefCard.tsx frontend/components/ThesisBadge.tsx frontend/components/ConfidenceMeter.tsx frontend/components/ReasoningTrace.tsx
git commit -m "feat: add brief feed, brief detail, and reasoning trace UI"
```

---

### Task 19: Ticker history + diff view

**Files:**
- Create: `frontend/app/tickers/[symbol]/page.tsx`, `frontend/components/DiffView.tsx`

**Interfaces:**
- Consumes: `getTickerHistory` (Task 16)
- `frontend/app/tickers/[symbol]/page.tsx` — fetches `getTickerHistory(symbol)`, shows ticker header, a `DiffView` (if `diff` non-null) highlighting what changed vs. the prior brief, then the full list of past `BriefCard`s for that ticker oldest-to-newest or newest-to-oldest (newest first, consistent with the feed).
- `DiffView` props: `{ diffText: string }` — renders the diff sentence(s) from `Brief.diff_from_prior` in a visually distinct callout (not a line-level text diff algorithm — the diff content itself is already a synthesized sentence from the backend per Task 11; this component just needs to present it prominently, e.g. an amber/blue callout box with a "What changed" label).

- [ ] **Step 1: Implement `DiffView.tsx`** per Interfaces above.

- [ ] **Step 2: Implement `frontend/app/tickers/[symbol]/page.tsx`** per Interfaces above.

- [ ] **Step 3: Add navigation** — `WatchlistCard` (Task 17) already links to `/tickers/[symbol]`; verify the link target matches this route's actual path.

- [ ] **Step 4: Type-check and build**

```bash
cd frontend && npx tsc --noEmit && npm run build
```
Expected: no type errors, production build succeeds.

- [ ] **Step 5: Commit**

```bash
git add frontend/app/tickers frontend/components/DiffView.tsx
git commit -m "feat: add ticker history page with brief diff view"
```

---

### Task 20: End-to-end verification with real backend + browser

**Files:** none (verification-only task)

**Interfaces:** none — this task exercises Tasks 1-19 together.

- [ ] **Step 1: Run the full backend test suite**

```bash
cd backend && source venv/bin/activate && pytest -v
```
Expected: all tests pass, 0 failures.

- [ ] **Step 2: Reset and seed the local DB**

```bash
cd backend && source venv/bin/activate
rm -f sentinel.db && alembic upgrade head && python scripts/seed_demo_data.py
```

- [ ] **Step 3: Start both servers**

```bash
cd backend && source venv/bin/activate && uvicorn main:app --reload &
cd frontend && npm run dev &
```
Wait ~5s for both to be up; confirm with `curl -s localhost:8000/api/watchlist | head -c 200` and `curl -s localhost:3000 | head -c 200`.

- [ ] **Step 4: Drive the app in Chrome via `claude-in-chrome`** — invoke the `claude-in-chrome` skill, then:
  - Navigate to `http://localhost:3000`, confirm the watchlist grid renders 8 tickers with prices and status badges (screenshot).
  - Click into a ticker with 2+ briefs, confirm the `DiffView` callout renders with real diff text.
  - Navigate to `/briefs`, confirm the feed lists all seeded briefs newest-first.
  - Click into a brief, confirm the reasoning trace renders and expands to show tool inputs/outputs.
  - Use "Add ticker" to add one new symbol, confirm it appears in the watchlist without a page reload (polling).
  - Check the browser console (`read_console_messages`) for uncaught errors — expect none.
  - If any step fails or looks visually broken, fix the underlying component/endpoint and re-verify — repeat until all pass.

- [ ] **Step 5: Stop background servers**

```bash
kill %1 %2 2>/dev/null || true
```

- [ ] **Step 6: Final commit (if fixes were made during verification)**

```bash
git add -A
git commit -m "fix: address issues found in end-to-end browser verification"
```
(Skip if Step 4 found nothing to fix.)

---

## Explicitly out of scope for this build (documented, not silently dropped)

- **Paper Trade Log** (`sentinel-spec/docs/DATA_MODELS.md` `PaperTrade`, PRD §5.5) — spec's own stretch goal, first item on its own cut list.
- **Cloud deployment** (Vercel/Render/Neon) — requires the user's own hosting accounts and credentials; the app is deploy-ready (standard FastAPI + Next.js) but this plan stops at local `uvicorn`/`next dev`.
- **WebSocket/SSE live updates** — polling only, per `sentinel-spec/docs/ARCHITECTURE.md` §4 ("nice-to-have, not core").
- **Real Alpaca/Anthropic credentials** — the user adds their own keys to `backend/.env` post-build to switch from `DemoProvider`/`HeuristicBackend` to live data/LLM reasoning; both integrations are fully implemented and unit-tested (Tasks 5, 10, 12) against mocked HTTP/SDK calls, just not exercised live in this unattended build.
