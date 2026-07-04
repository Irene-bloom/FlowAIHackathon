"""
Chang - Backtest Engine (Option B)

Supports:
  - Daily-frequency portfolio backtest
  - Periodic rebalancing (monthly / quarterly)
  - Threshold rebalancing (when any weight drifts > X% from target)
  - Stop-loss (portfolio drawdown > X% -> switch to conservative weights)
  - Per-asset weight limits (min/max, enforced at each rebalance)
  - Extreme scenario stress test (2008 crisis / 2020 COVID / 2022 rate hikes)

Look-ahead prevention:
  Portfolio return on day t uses weights set at day t-1's close.
  Rebalance decisions on day t are executed at day t's close.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional
import time

import numpy as np
import pandas as pd


# ================================================================
# Config
# ================================================================

@dataclass
class BacktestConfig:
    """
    A portfolio backtest configuration.

    tickers / weights: parallel lists, weights must sum to 1.
    Convention: order tickers from most risky to least risky, so the
    default stop-loss target (100% last ticker) lands on the safest asset.
    """
    tickers: list[str]
    weights: list[float]
    start_date: str = '2015-01-01'
    end_date: Optional[str] = None
    initial_capital: float = 10000.0

    # Rebalancing rules
    rebalance_freq: str = 'M'          # 'M' monthly, 'Q' quarterly, 'None' never
    rebalance_threshold: float = 0.05  # trigger if max weight drift > 5%

    # Stop-loss
    stop_loss_drawdown: Optional[float] = 0.20  # switch when portfolio DD < -20%
    stop_loss_target_weights: Optional[list[float]] = None  # defaults to last ticker

    # Weight limits (per-asset, applied at rebalance, then renormalized)
    weight_min: Optional[dict] = None  # {ticker: float}
    weight_max: Optional[dict] = None

    def __post_init__(self):
        if len(self.tickers) != len(self.weights):
            raise ValueError('tickers and weights must have same length')
        w = np.array(self.weights, dtype=float)
        if abs(w.sum() - 1.0) > 1e-6:
            raise ValueError(f'weights must sum to 1, got {w.sum():.6f}')
        if (w < -1e-9).any():
            raise ValueError('weights must be non-negative')


# ================================================================
# Result
# ================================================================

@dataclass
class BacktestResult:
    equity_curve: pd.Series           # portfolio value over time
    returns: pd.Series                # daily portfolio returns
    weights_history: pd.DataFrame     # end-of-day weights per ticker
    metrics: dict                     # summary metrics
    trades: list                      # list of rebalance events
    config: BacktestConfig
    stopped_out: bool = False

    def summary(self) -> dict:
        """JSON-serializable summary for LLM tool return."""
        m = self.metrics
        final_val = float(self.equity_curve.iloc[-1])
        return {
            'tickers': self.config.tickers,
            'weights': self.config.weights,
            'period': f'{self.config.start_date} .. {self.config.end_date or "today"}',
            'initial_capital': self.config.initial_capital,
            'final_value': final_val,
            'pnl': final_val - self.config.initial_capital,
            'total_return': m.get('total_return'),
            'annual_return': m.get('annual_return'),
            'annual_vol': m.get('annual_vol'),
            'sharpe': m.get('sharpe'),
            'sortino': m.get('sortino'),
            'max_drawdown': m.get('max_drawdown'),
            'max_drawdown_period': f"{m.get('dd_start_date')} .. {m.get('dd_end_date')}",
            'recovery_days': m.get('recovery_days'),
            'win_rate': m.get('win_rate'),
            'num_trades': len(self.trades),
            'stopped_out': self.stopped_out,
        }


# ================================================================
# Data loading  (with disk cache)
# ================================================================

_CACHE_DIR = Path('data')
_CACHE_MAX_AGE_HOURS = 6  # only when end_date is None ("today")


def load_prices(tickers: list[str], start: str,
                end: Optional[str] = None, use_cache: bool = True) -> pd.DataFrame:
    """
    Load adjusted close prices from yfinance.
    Returns DataFrame indexed by date, columns = tickers (in given order).
    Cached to data/*.parquet to keep agent tool calls fast.
    """
    cache_key = f'{"_".join(tickers)}__{start}__{end or "today"}'.replace('/', '-')
    cache_path = _CACHE_DIR / f'{cache_key}.parquet'

    if use_cache and cache_path.exists():
        # For "today" queries, only reuse if cache is fresh
        if end is None:
            age_h = (time.time() - cache_path.stat().st_mtime) / 3600
            if age_h < _CACHE_MAX_AGE_HOURS:
                return pd.read_parquet(cache_path)
        else:
            return pd.read_parquet(cache_path)

    prices = _fetch_yfinance(tickers, start, end)
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    prices.to_parquet(cache_path)
    return prices


def _fetch_yfinance(tickers: list[str], start: str, end: Optional[str]) -> pd.DataFrame:
    """
    Try yfinance first; if it fails / gets rate-limited, fall back to akshare
    (works reliably from mainland China, no key required).
    """
    try:
        return _fetch_yfinance_only(tickers, start, end)
    except Exception as e:
        print(f'[data] yfinance failed ({type(e).__name__}), falling back to akshare...')
        return _fetch_akshare(tickers, start, end)


def _fetch_yfinance_only(tickers: list[str], start: str, end: Optional[str]) -> pd.DataFrame:
    import yfinance as yf
    data = yf.download(
        tickers,
        start=start,
        end=end,
        auto_adjust=True,
        progress=False,
        threads=True,
    )
    if data is None or data.empty:
        raise ValueError(f'yfinance returned no data for {tickers}')

    if isinstance(data.columns, pd.MultiIndex):
        if 'Close' in data.columns.get_level_values(0):
            prices = data['Close']
        else:
            raise ValueError('unexpected yfinance columns structure')
    else:
        if 'Close' in data.columns:
            prices = data[['Close']].rename(columns={'Close': tickers[0]})
        else:
            raise ValueError('unexpected yfinance columns structure')

    prices = prices[tickers]
    prices = prices.ffill().dropna(how='any')
    if len(prices) < 30:
        raise ValueError(f'yfinance only returned {len(prices)} rows')
    return prices


def _fetch_akshare(tickers: list[str], start: str, end: Optional[str]) -> pd.DataFrame:
    """
    akshare fallback. Routes each ticker by market:
      - "XXX.HK"          -> Hong Kong stocks
      - "600xxx" / "0xxx" -> A-shares (6 digits)
      - default           -> US stocks
    """
    import akshare as ak

    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end) if end else pd.Timestamp.today()

    series = {}
    for orig in tickers:
        t = orig.upper()
        try:
            if t.endswith('.HK'):
                sym = t.replace('.HK', '').lstrip('0') or '0'
                df = ak.stock_hk_daily(symbol=sym, adjust='qfq')
            elif t.isdigit() and len(t) == 6:
                df = ak.stock_zh_a_daily(symbol=t, adjust='qfq')
            else:
                df = ak.stock_us_daily(symbol=t, adjust='qfq')
        except Exception as e:
            raise ValueError(f'akshare fetch failed for {orig}: {type(e).__name__}: {e}')

        if df is None or df.empty or 'close' not in df.columns:
            raise ValueError(f'akshare returned no usable data for {orig}')

        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date').sort_index()
        df = df[(df.index >= start_ts) & (df.index <= end_ts)]
        series[orig] = df['close']

    prices = pd.DataFrame(series)[tickers]
    prices = prices.sort_index().ffill().dropna(how='any')
    if len(prices) < 30:
        raise ValueError(f'akshare only returned {len(prices)} usable rows')
    return prices


# ================================================================
# Metrics
# ================================================================

def compute_metrics(returns: pd.Series, risk_free_rate: float = 0.0) -> dict:
    """
    Compute standard performance metrics from a daily return series.
    All ratios are annualized assuming 252 trading days per year.
    """
    if len(returns) < 2:
        return {}

    ann_ret = (1 + returns.mean()) ** 252 - 1
    ann_vol = returns.std() * np.sqrt(252)
    sharpe = (ann_ret - risk_free_rate) / ann_vol if ann_vol > 1e-12 else 0.0

    equity = (1 + returns).cumprod()
    running_max = equity.cummax()
    dd = equity / running_max - 1
    max_dd = dd.min()

    dd_end = dd.idxmin()
    dd_start = equity.loc[:dd_end].idxmax()
    dd_duration = int((dd_end - dd_start).days)

    # Recovery = days from trough back to peak (None if never)
    recovery_days = None
    peak_val = equity.loc[dd_start]
    post = equity.loc[dd_end:]
    recovered = post[post >= peak_val]
    if len(recovered) > 0:
        recovery_days = int((recovered.index[0] - dd_end).days)

    # Sortino = downside-vol-adjusted return
    downside = returns[returns < 0]
    downside_vol = downside.std() * np.sqrt(252) if len(downside) > 0 else 0.0
    sortino = (ann_ret - risk_free_rate) / downside_vol if downside_vol > 1e-12 else 0.0

    return {
        'annual_return': float(ann_ret),
        'annual_vol': float(ann_vol),
        'sharpe': float(sharpe),
        'sortino': float(sortino),
        'max_drawdown': float(max_dd),
        'dd_start_date': str(dd_start.date()),
        'dd_end_date': str(dd_end.date()),
        'dd_duration_days': dd_duration,
        'recovery_days': recovery_days,
        'total_return': float(equity.iloc[-1] - 1),
        'win_rate': float((returns > 0).mean()),
        'best_day': float(returns.max()),
        'worst_day': float(returns.min()),
        'num_days': int(len(returns)),
    }


# ================================================================
# Helpers
# ================================================================

def _apply_weight_limits(weights: np.ndarray, tickers: list,
                        w_min: Optional[dict], w_max: Optional[dict]) -> np.ndarray:
    """Clip weights to per-asset limits, then renormalize to sum=1."""
    if w_min is None and w_max is None:
        return weights
    w = weights.copy()
    for i, t in enumerate(tickers):
        if w_min and t in w_min:
            w[i] = max(w[i], w_min[t])
        if w_max and t in w_max:
            w[i] = min(w[i], w_max[t])
    s = w.sum()
    return w / s if s > 0 else weights


def _month_key(date) -> int:
    return date.year * 12 + date.month


def _quarter_key(date) -> int:
    return date.year * 4 + (date.month - 1) // 3


# ================================================================
# Core backtest loop
# ================================================================

def run_backtest(config: BacktestConfig) -> BacktestResult:
    """
    Run the backtest. Returns a BacktestResult with:
      - equity_curve (pd.Series indexed by date)
      - returns (daily portfolio returns)
      - weights_history (end-of-day weights)
      - metrics (dict of performance stats)
      - trades (list of rebalance events)
    """
    prices = load_prices(config.tickers, config.start_date, config.end_date)
    if len(prices) < 30:
        raise ValueError(f'Only {len(prices)} price rows; need >=30 for backtest')

    daily_returns = prices.pct_change().dropna()
    dates = daily_returns.index
    n_assets = len(config.tickers)

    # Target weights (after limits)
    target_weights = _apply_weight_limits(
        np.array(config.weights, dtype=float),
        config.tickers, config.weight_min, config.weight_max,
    )
    current_weights = target_weights.copy()

    # Stop-loss target: user-provided or default = 100% last asset (assumed safest)
    if config.stop_loss_target_weights is not None:
        stop_loss_weights = np.array(config.stop_loss_target_weights, dtype=float)
    else:
        stop_loss_weights = np.zeros(n_assets)
        stop_loss_weights[-1] = 1.0

    # State
    portfolio_value = config.initial_capital
    peak_value = portfolio_value
    stopped_out = False

    # Series (start with initial state at prices.index[0])
    equity_values = [portfolio_value]
    equity_dates = [prices.index[0]]
    weights_history = [current_weights.copy()]
    trades = []

    for i, date in enumerate(dates):
        r_vec = daily_returns.loc[date].values.astype(float)

        # Today's portfolio return using yesterday's weights
        port_r = float(np.dot(current_weights, r_vec))
        portfolio_value *= (1 + port_r)
        peak_value = max(peak_value, portfolio_value)

        # Drift weights
        denom = 1.0 + port_r
        if abs(denom) > 1e-12:
            current_weights = current_weights * (1 + r_vec) / denom

        # === Decide whether to rebalance (priority: stop-loss > scheduled > threshold) ===
        should_rebalance = False
        reason = None
        new_target = None

        # 1) Stop-loss
        current_dd = (portfolio_value - peak_value) / peak_value
        if (not stopped_out
                and config.stop_loss_drawdown is not None
                and current_dd <= -config.stop_loss_drawdown):
            stopped_out = True
            new_target = stop_loss_weights.copy()
            reason = f'stop_loss (dd={current_dd:.2%})'
            should_rebalance = True

        # 2) Scheduled rebalance (skipped once stopped out)
        if not should_rebalance and not stopped_out and i > 0:
            prev_date = dates[i - 1]
            if config.rebalance_freq == 'M' and _month_key(date) != _month_key(prev_date):
                should_rebalance = True
                reason = 'monthly'
                new_target = target_weights
            elif config.rebalance_freq == 'Q' and _quarter_key(date) != _quarter_key(prev_date):
                should_rebalance = True
                reason = 'quarterly'
                new_target = target_weights

        # 3) Threshold rebalance
        if not should_rebalance and not stopped_out and config.rebalance_threshold:
            drift = np.abs(current_weights - target_weights)
            if drift.max() > config.rebalance_threshold:
                should_rebalance = True
                reason = f'threshold (max_drift={drift.max():.2%})'
                new_target = target_weights

        if should_rebalance and new_target is not None:
            current_weights = _apply_weight_limits(
                new_target.copy(), config.tickers,
                config.weight_min, config.weight_max,
            )
            trades.append({
                'date': str(date.date()),
                'reason': reason,
                'weights': {t: float(w) for t, w in zip(config.tickers, current_weights)},
                'portfolio_value': float(portfolio_value),
            })

        equity_values.append(portfolio_value)
        equity_dates.append(date)
        weights_history.append(current_weights.copy())

    equity = pd.Series(equity_values, index=equity_dates, name='equity')
    weights_df = pd.DataFrame(weights_history, index=equity_dates, columns=config.tickers)
    port_returns = equity.pct_change().dropna()
    metrics = compute_metrics(port_returns)

    return BacktestResult(
        equity_curve=equity,
        returns=port_returns,
        weights_history=weights_df,
        metrics=metrics,
        trades=trades,
        config=config,
        stopped_out=stopped_out,
    )


# ================================================================
# Extreme scenario stress test
# ================================================================

STRESS_SCENARIOS = {
    '2008_crisis': ('2007-10-01', '2009-06-30'),
    '2020_covid':  ('2020-02-01', '2020-06-30'),
    '2022_hike':   ('2022-01-01', '2022-12-31'),
}


def stress_test(config: BacktestConfig) -> dict:
    """Run the same portfolio through 3 historical extreme periods."""
    out = {}
    for name, (start, end) in STRESS_SCENARIOS.items():
        try:
            cfg_dict = asdict(config)
            cfg_dict['start_date'] = start
            cfg_dict['end_date'] = end
            cfg = BacktestConfig(**cfg_dict)
            result = run_backtest(cfg)
            out[name] = result.summary()
        except Exception as e:
            out[name] = {'error': f'{type(e).__name__}: {e}'}
    return out


# ================================================================
# Standalone sanity test
# ================================================================

def _demo():
    """Run a sample 40/30/30 SPY/GLD/AGG portfolio for quick sanity check."""
    print('=' * 60)
    print('Chang backtest engine - sanity check')
    print('=' * 60)

    # Convention: order tickers from most risky to least risky
    # so default stop-loss (100% last asset) lands on the safest.
    cfg = BacktestConfig(
        tickers=['SPY', 'GLD', 'AGG'],  # US equity / gold / US bonds
        weights=[0.40, 0.30, 0.30],
        start_date='2015-01-01',
        initial_capital=10000.0,
        rebalance_freq='M',
        rebalance_threshold=0.05,
        stop_loss_drawdown=0.20,
    )

    print(f'\nPortfolio: {dict(zip(cfg.tickers, cfg.weights))}')
    print(f'Period: {cfg.start_date} to today')
    print(f'Initial capital: ${cfg.initial_capital:,.0f}\n')

    print('[1/2] Running main backtest...')
    result = run_backtest(cfg)
    s = result.summary()

    print(f'\n--- Results ---')
    print(f'Final value:      ${s["final_value"]:,.2f}')
    print(f'Total PnL:        ${s["pnl"]:+,.2f}')
    print(f'Total return:     {s["total_return"]:+.2%}')
    print(f'Annual return:    {s["annual_return"]:+.2%}')
    print(f'Annual vol:       {s["annual_vol"]:.2%}')
    print(f'Sharpe:           {s["sharpe"]:.2f}')
    print(f'Sortino:          {s["sortino"]:.2f}')
    print(f'Max drawdown:     {s["max_drawdown"]:.2%}')
    print(f'DD period:        {s["max_drawdown_period"]}')
    print(f'Recovery days:    {s["recovery_days"]}')
    print(f'Win rate:         {s["win_rate"]:.2%}')
    print(f'Rebalance trades: {s["num_trades"]}')
    print(f'Stopped out:      {s["stopped_out"]}')

    print(f'\n[2/2] Running stress test (2008/2020/2022)...')
    stress = stress_test(cfg)
    for name, res in stress.items():
        if 'error' in res:
            print(f'  {name}: ERROR - {res["error"]}')
        else:
            print(f'  {name}: total_return={res["total_return"]:+.2%}, '
                  f'max_dd={res["max_drawdown"]:.2%}, '
                  f'sharpe={res["sharpe"]:.2f}')

    print('\n' + '=' * 60)
    print('Sanity check complete.')
    print('=' * 60)


if __name__ == '__main__':
    _demo()
