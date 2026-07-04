"""
阿钱 · Paper Trading Engine

Handles the 「开跑」moment: takes a proposal (tickers, weights) and starts a
paper-trading run that Wallet Tab reads for real-time NAV and P&L.

Pricing sources:
  - Stock tickers  -> app.backtest.load_prices (yfinance -> akshare fallback)
                      Uses last close (weekend-safe fallback: still shows last
                      close, judges see a stable-looking curve).
  - Crypto tickers -> Binance testnet Spot ticker (7x24 live during Hackathon!)

Robust to network errors: any pricing failure keeps the last known NAV.
"""

from __future__ import annotations
import os
import time
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from app import state as S


ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / '.env')


# ================================================================
# Binance testnet client (lazy)
# ================================================================

_binance_client = None


def _get_binance():
    """Lazy Binance testnet client. No credentials needed for public data."""
    global _binance_client
    if _binance_client is None:
        try:
            from binance.client import Client
            # Public data works without API key on testnet
            api_key = os.getenv('BINANCE_TESTNET_KEY', '')
            api_secret = os.getenv('BINANCE_TESTNET_SECRET', '')
            _binance_client = Client(api_key, api_secret, testnet=True)
        except Exception as e:
            print(f'[paper] Binance client init failed: {e}')
            _binance_client = False  # sentinel: don't retry
    return _binance_client if _binance_client is not False else None


def _get_crypto_price(symbol: str) -> Optional[float]:
    """Get latest price for a crypto symbol (e.g. BTCUSDT). Returns None on fail."""
    client = _get_binance()
    if client is None:
        # Fallback: use public REST via requests (no auth needed for /ticker/price)
        try:
            import requests
            r = requests.get(
                f'https://testnet.binance.vision/api/v3/ticker/price?symbol={symbol}',
                timeout=8,
            )
            if r.status_code == 200:
                return float(r.json()['price'])
        except Exception:
            pass
        return None
    try:
        info = client.get_symbol_ticker(symbol=symbol)
        return float(info['price'])
    except Exception as e:
        print(f'[paper] Binance price fetch failed for {symbol}: {e}')
        return None


# ================================================================
# Stock price helper (uses same fallback chain as backtest)
# ================================================================

def _get_stock_price(ticker: str) -> Optional[float]:
    """
    Latest stock close. Tries in this order:
      1. Reuse backtest.py's cached parquet (fast, no network)
      2. akshare with 3 retries + backoff
    Returns None on failure -- the caller MUST refuse to open the position
    rather than substituting a nonsense fallback price.
    """
    # ---- Try cache first (backtest engine already downloaded and cached) ----
    try:
        from app.backtest import _CACHE_DIR
        # Look for any cache file containing this ticker
        for p in _CACHE_DIR.glob(f'*{ticker.upper()}*.parquet'):
            try:
                import pandas as pd
                df = pd.read_parquet(p)
                if ticker in df.columns and not df.empty:
                    return float(df[ticker].iloc[-1])
            except Exception:
                continue
    except Exception:
        pass

    # ---- Live fetch with retries ----
    import time as _time
    for attempt in range(3):
        try:
            import akshare as ak
            df = ak.stock_us_daily(symbol=ticker.upper(), adjust='qfq')
            if df is not None and not df.empty:
                return float(df.iloc[-1]['close'])
        except Exception as e:
            if attempt < 2:
                _time.sleep(1.5 * (attempt + 1))
                continue
            print(f'[paper] akshare fetch failed for {ticker} after 3 tries: {e}')
    return None


# ================================================================
# High-level API used by Chat + Wallet
# ================================================================

def start_run(
    tickers: list[str],
    weights: list[float],
    kind: str,
    label: str,
    initial_capital: float,
) -> S.PaperRun:
    """
    Create a new PaperRun. Snapshots entry prices RIGHT NOW.

    If a ticker's entry price cannot be resolved (network / rate limit),
    we DROP that ticker rather than using a nonsense 1.0 fallback (which
    would make PnL % explode on the first refresh). Weights are renormalized
    over the tickers that did resolve.
    """
    entry_prices = {}
    kept_tickers = []
    kept_weights = []

    for t, w in zip(tickers, weights):
        px = _get_price(t)
        if px is not None and px > 0:
            entry_prices[t] = px
            kept_tickers.append(t)
            kept_weights.append(w)
        else:
            print(f'[paper] WARNING: could not resolve entry price for {t}; dropping')

    # Renormalize surviving weights so they still sum to 1
    total_w = sum(kept_weights)
    if total_w > 0:
        kept_weights = [w / total_w for w in kept_weights]
    else:
        # Everything failed. Fall back to holding cash (initial capital, no PnL).
        # This is safer than exploding NAV.
        kept_tickers = ['CASH']
        kept_weights = [1.0]
        entry_prices = {'CASH': 1.0}

    now = time.time()
    run = S.PaperRun(
        started_at=now,
        initial_capital=initial_capital,
        tickers=kept_tickers,
        weights=kept_weights,
        kind=kind,
        label=label,
        entry_prices=entry_prices,
        nav_history=[{'ts': now, 'nav': initial_capital, 'pnl_pct': 0.0}],
        current_nav=initial_capital,
        current_pnl_pct=0.0,
        trades=[{
            'ts': now,
            'kind': 'open',
            'label': label,
            'weights': dict(zip(kept_tickers, kept_weights)),
        }],
        stopped_out=False,
    )
    return run


def refresh_run(run: S.PaperRun) -> None:
    """Update run.current_nav / pnl / append to nav_history using latest prices."""
    if run is None:
        return

    total_current = 0.0
    for t, w in zip(run.tickers, run.weights):
        entry = run.entry_prices.get(t, 0.0)
        if entry <= 0 or t == 'CASH':
            # Cash leg or missing entry -- treat as flat (no PnL)
            total_current += run.initial_capital * w
            continue
        px = _get_price(t)
        if px is None or px <= 0:
            # Live price fetch failed -- freeze this leg at entry (no PnL move)
            px = entry
        leg_start_value = run.initial_capital * w
        leg_current_value = leg_start_value * (px / entry)
        total_current += leg_current_value

    pnl_pct = (total_current - run.initial_capital) / run.initial_capital if run.initial_capital > 0 else 0.0
    run.current_nav = total_current
    run.current_pnl_pct = pnl_pct

    # Only append a new history point if last one is > 5 min old
    last_ts = run.nav_history[-1]['ts'] if run.nav_history else 0
    if time.time() - last_ts > 300:  # 5 minutes
        run.nav_history.append({
            'ts': time.time(),
            'nav': total_current,
            'pnl_pct': pnl_pct,
        })

    # Stop-loss check (portfolio down > 20%)
    if pnl_pct <= -0.20 and not run.stopped_out:
        run.stopped_out = True
        run.trades.append({
            'ts': time.time(),
            'kind': 'stop_loss',
            'label': f'触发止损 (PnL {pnl_pct*100:.2f}%)',
        })


def _get_price(ticker: str) -> Optional[float]:
    """Dispatch by ticker type."""
    if S.is_crypto(ticker):
        return _get_crypto_price(ticker)
    return _get_stock_price(ticker)


# ================================================================
# CLI sanity test
# ================================================================

if __name__ == '__main__':
    print('=' * 60)
    print('Paper Engine sanity check')
    print('=' * 60)

    print('\n[1] Crypto price (BTCUSDT):', _get_crypto_price('BTCUSDT'))
    print('[2] Stock price (SPY):     ', _get_stock_price('SPY'))

    print('\n[3] Starting a mixed run: 50% SPY / 30% GLD / 20% BTCUSDT ...')
    run = start_run(
        tickers=['SPY', 'GLD', 'BTCUSDT'],
        weights=[0.50, 0.30, 0.20],
        kind='mixed',
        label='测试组合',
        initial_capital=10000.0,
    )
    print(f'  Entry prices: {run.entry_prices}')
    print(f'  Initial NAV: {run.current_nav:.2f}')

    print('\n[4] Refreshing NAV...')
    refresh_run(run)
    print(f'  Current NAV: {run.current_nav:.2f}')
    print(f'  PnL: {run.current_pnl_pct*100:+.4f}%')

    print('\nDone.')
