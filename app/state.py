"""
阿钱 · Central UserState + SQLite persistence

Everything a user does lives in ONE UserState object, persisted to SQLite so
state survives restart. Every Tab reads and writes through this — no Tab has
its own hidden copy.

Layout:
  UserState
    ├── profile       (capital / risk_level / horizon / goal)
    ├── portfolio     (planned tickers/weights, before 开跑)
    ├── paper_run     (open paper-trading run: start ts, snapshot, current NAV)
    ├── vocab         (dict term -> plain explanation, added when AI teaches)
    └── chat          (message list; assistant messages may have `metadata`)

Tables:
  state (id INTEGER PRIMARY KEY, kv TEXT)   -- single-row JSON blob
"""

from __future__ import annotations
import json
import sqlite3
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional


DB_PATH = Path(__file__).resolve().parent.parent / 'data' / 'aqian.db'


# ================================================================
# Data classes
# ================================================================

@dataclass
class UserProfile:
    capital: float = 5000.0
    risk_level: str = 'balanced'     # conservative / balanced / growth
    horizon_years: int = 3
    goal: str = ''
    # Free-form facts the AI has learned about the user (name, job, etc.)
    facts: list[str] = field(default_factory=list)


@dataclass
class PlannedPortfolio:
    """The portfolio the user has *chosen* but not yet 开跑."""
    tickers: list[str] = field(default_factory=list)
    weights: list[float] = field(default_factory=list)
    kind: str = 'mixed'  # 'stock' / 'crypto' / 'mixed'
    label: str = ''      # human name of the strategy
    rationale: str = ''  # AI's brief reason


@dataclass
class PaperRun:
    """A live paper-trading run (post-开跑)."""
    started_at: Optional[float] = None      # unix ts
    initial_capital: float = 0.0
    tickers: list[str] = field(default_factory=list)
    weights: list[float] = field(default_factory=list)
    kind: str = 'mixed'
    label: str = ''
    # Snapshot at 开跑 moment: {ticker: entry_price}
    entry_prices: dict = field(default_factory=dict)
    # NAV history: list of {ts, nav, pnl_pct}
    nav_history: list[dict] = field(default_factory=list)
    # Latest computed NAV (kept for cheap render)
    current_nav: float = 0.0
    current_pnl_pct: float = 0.0
    # Trade log (rebalances, stop-loss triggers)
    trades: list[dict] = field(default_factory=list)
    # Whether stop-loss has fired
    stopped_out: bool = False


@dataclass
class ChatMessage:
    role: str                # 'user' or 'assistant'
    text: str
    ts: float = field(default_factory=time.time)
    # Structured payload for special messages (proposals, backtest cards, etc.)
    kind: str = 'text'       # 'text' / 'proposal' / 'backtest' / 'news_ctx'
    data: dict = field(default_factory=dict)


@dataclass
class UserState:
    profile: UserProfile = field(default_factory=UserProfile)
    planned: PlannedPortfolio = field(default_factory=PlannedPortfolio)
    paper: Optional[PaperRun] = None      # None = 未开跑
    vocab: dict = field(default_factory=dict)   # term -> plain
    chat: list[ChatMessage] = field(default_factory=list)
    # Rolling summary of older chat (for long memory)
    chat_summary: str = ''

    # ---- serialization ----
    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> 'UserState':
        prof = UserProfile(**d.get('profile', {}))
        plan = PlannedPortfolio(**d.get('planned', {}))
        paper_d = d.get('paper')
        paper = PaperRun(**paper_d) if paper_d else None
        chat = [ChatMessage(**m) for m in d.get('chat', [])]
        return cls(
            profile=prof,
            planned=plan,
            paper=paper,
            vocab=d.get('vocab', {}),
            chat=chat,
            chat_summary=d.get('chat_summary', ''),
        )


# ================================================================
# SQLite persistence  (single-row JSON blob is fine for a demo)
# ================================================================

def _ensure_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute('CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY, kv TEXT NOT NULL)')
    con.commit()
    con.close()


def load_state() -> UserState:
    """Read the singleton state row. Return a fresh UserState if none exists."""
    _ensure_db()
    con = sqlite3.connect(DB_PATH)
    try:
        row = con.execute('SELECT kv FROM state WHERE id = 1').fetchone()
    finally:
        con.close()
    if row is None:
        return UserState()
    try:
        return UserState.from_dict(json.loads(row[0]))
    except Exception:
        # Corrupt row -> fresh state (safer than crashing)
        return UserState()


def save_state(state: UserState) -> None:
    _ensure_db()
    kv = json.dumps(state.to_dict(), ensure_ascii=False, default=str)
    con = sqlite3.connect(DB_PATH)
    try:
        con.execute(
            'INSERT INTO state (id, kv) VALUES (1, ?) '
            'ON CONFLICT(id) DO UPDATE SET kv = excluded.kv',
            (kv,),
        )
        con.commit()
    finally:
        con.close()


def reset_state() -> None:
    """Nuke the singleton (useful for demo prep)."""
    _ensure_db()
    con = sqlite3.connect(DB_PATH)
    try:
        con.execute('DELETE FROM state WHERE id = 1')
        con.commit()
    finally:
        con.close()


# ================================================================
# Module-level singleton (loaded on first access, saved on every mutator call)
# ================================================================

_state: Optional[UserState] = None


def get() -> UserState:
    global _state
    if _state is None:
        _state = load_state()
    return _state


def commit() -> None:
    """Persist the current in-memory state to disk."""
    if _state is not None:
        save_state(_state)


def reset() -> None:
    """Reset both in-memory and on-disk state."""
    global _state
    reset_state()
    _state = UserState()


# ================================================================
# Small helpers used across Tabs
# ================================================================

RISK_LABELS = {
    'conservative': '😴 稳当型 · 少赚不亏',
    'balanced':     '😐 平衡型 · 稳中有进',
    'growth':       '😤 进取型 · 敢博更大',
}

TICKER_PLAIN = {
    # Stocks / ETFs
    'SPY': '美股大盘 (500 只大公司)',
    'QQQ': '美股科技 (纳指 100)',
    'GLD': '黄金',
    'AGG': '美国债券',
    'TLT': '美国长期国债',
    'VNQ': '美国房地产',
    'IEF': '美国中期国债',
    # Crypto (used in Binance testnet)
    'BTCUSDT': '比特币',
    'ETHUSDT': '以太坊',
    'BNBUSDT': '币安币',
    'SOLUSDT': 'Solana',
}


def plain_name(ticker: str) -> str:
    return TICKER_PLAIN.get(ticker.upper(), ticker)


def money(x: float) -> str:
    """Format money the way a real person would say it."""
    if abs(x) >= 10000:
        return f'{x/10000:.1f} 万'
    if abs(x) >= 100:
        return f'{x:,.0f} 元'
    return f'{x:.2f} 元'


def is_crypto(ticker: str) -> bool:
    return ticker.upper().endswith('USDT') or ticker.upper() in {'BTC', 'ETH'}
