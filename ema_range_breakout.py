"""
EMA Crossover + Range Breakout Swing Strategy
==============================================
Entry: 10 EMA crosses above 20 EMA AND close breaks above the HIGH
       of the last N candles (range breakout confirmation).
SL:    Low of the last N candles (range low).
TP:    Entry + RR * (Entry - SL).
Long only, daily timeframe.

Versions tested:
  V1 - Base: EMA cross + range breakout, SL=range low, fixed RR
  V2 - RSI filter: V1 + RSI(14) < 70
  V3 - Volume filter: V1 + volume > 1.2x 20-day avg
  V4 - Tight SL: SL = max(range_low, entry - 1.5*ATR) for tighter risk
  V5 - Trailing: V1 entry but stepped trailing SL instead of fixed TP
  V6 - Combined: RSI + volume + tight SL + trailing

Parameter grid: lookback=[5,7,10], RR=[2.0,2.5,3.0]
"""

import pandas as pd
import numpy as np
import os
import warnings
from dataclasses import dataclass

warnings.filterwarnings("ignore")

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")


# ── Indicators ──────────────────────────────────────────────

def ema(s, p):
    return s.ewm(span=p, adjust=False).mean()

def rsi(s, p=14):
    d = s.diff()
    g = d.clip(lower=0)
    l = -d.clip(upper=0)
    ag = g.ewm(alpha=1/p, min_periods=p).mean()
    al = l.ewm(alpha=1/p, min_periods=p).mean()
    return 100 - (100 / (1 + ag / al))

def atr(df, p=14):
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift(1)).abs(),
        (df["low"] - df["close"].shift(1)).abs()
    ], axis=1).max(axis=1)
    return tr.ewm(span=p, adjust=False).mean()


# ── Data Loading ────────────────────────────────────────────

def load_and_prepare(filepath):
    df = pd.read_csv(filepath, parse_dates=["time"])
    df = df.sort_values("time").reset_index(drop=True)
    df.rename(columns={"time": "date"}, inplace=True)

    df["ema10"] = ema(df["close"], 10)
    df["ema20"] = ema(df["close"], 20)
    df["rsi14"] = rsi(df["close"], 14)
    df["atr14"] = atr(df, 14)
    df["vol_ma20"] = df["volume"].rolling(20).mean()

    # EMA crossover
    above = df["ema10"] > df["ema20"]
    df["cross_up"] = above & ~above.shift(1, fill_value=False)

    # Pre-compute rolling range highs and lows for different lookbacks
    for lb in [5, 7, 10]:
        df[f"range_high_{lb}"] = df["high"].shift(1).rolling(lb).max()
        df[f"range_low_{lb}"] = df["low"].shift(1).rolling(lb).min()

    return df


# ── Trade dataclass ─────────────────────────────────────────

@dataclass
class Trade:
    pnl_pct: float
    holding_days: int


# ── Strategy Functions ──────────────────────────────────────

def run_v1(df, lookback=5, rr=2.0):
    """V1 Base: EMA cross up + close > range high, SL = range low, fixed TP"""
    rh = f"range_high_{lookback}"
    rl = f"range_low_{lookback}"
    trades = []
    in_trade = False
    entry = sl = tp = 0.0
    edate = None

    for i in range(lookback + 1, len(df)):
        r = df.iloc[i]
        if not in_trade:
            if (r["cross_up"]
                    and pd.notna(r[rh])
                    and r["close"] > r[rh]):
                entry = r["close"]
                sl = r[rl]
                risk = entry - sl
                if risk <= 0:
                    continue
                tp = entry + risk * rr
                edate = r["date"]
                in_trade = True
        else:
            if r["low"] <= sl:
                trades.append(Trade(((sl - entry) / entry) * 100,
                                    (r["date"] - edate).days))
                in_trade = False
            elif r["high"] >= tp:
                trades.append(Trade(((tp - entry) / entry) * 100,
                                    (r["date"] - edate).days))
                in_trade = False
    return trades


def run_v2(df, lookback=5, rr=2.0):
    """V2 RSI filter: V1 + RSI < 70"""
    rh = f"range_high_{lookback}"
    rl = f"range_low_{lookback}"
    trades = []
    in_trade = False
    entry = sl = tp = 0.0
    edate = None

    for i in range(lookback + 1, len(df)):
        r = df.iloc[i]
        if not in_trade:
            if (r["cross_up"]
                    and pd.notna(r[rh])
                    and r["close"] > r[rh]
                    and r["rsi14"] < 70):
                entry = r["close"]
                sl = r[rl]
                risk = entry - sl
                if risk <= 0:
                    continue
                tp = entry + risk * rr
                edate = r["date"]
                in_trade = True
        else:
            if r["low"] <= sl:
                trades.append(Trade(((sl - entry) / entry) * 100,
                                    (r["date"] - edate).days))
                in_trade = False
            elif r["high"] >= tp:
                trades.append(Trade(((tp - entry) / entry) * 100,
                                    (r["date"] - edate).days))
                in_trade = False
    return trades


def run_v3(df, lookback=5, rr=2.0):
    """V3 Volume filter: V1 + volume > 1.2x 20-day avg"""
    rh = f"range_high_{lookback}"
    rl = f"range_low_{lookback}"
    trades = []
    in_trade = False
    entry = sl = tp = 0.0
    edate = None

    for i in range(lookback + 1, len(df)):
        r = df.iloc[i]
        if not in_trade:
            vol_ok = pd.notna(r["vol_ma20"]) and r["volume"] > 1.2 * r["vol_ma20"]
            if (r["cross_up"]
                    and pd.notna(r[rh])
                    and r["close"] > r[rh]
                    and vol_ok):
                entry = r["close"]
                sl = r[rl]
                risk = entry - sl
                if risk <= 0:
                    continue
                tp = entry + risk * rr
                edate = r["date"]
                in_trade = True
        else:
            if r["low"] <= sl:
                trades.append(Trade(((sl - entry) / entry) * 100,
                                    (r["date"] - edate).days))
                in_trade = False
            elif r["high"] >= tp:
                trades.append(Trade(((tp - entry) / entry) * 100,
                                    (r["date"] - edate).days))
                in_trade = False
    return trades


def run_v4(df, lookback=5, rr=2.0):
    """V4 Tight SL: SL = max(range_low, entry - 1.5*ATR) — whichever is closer"""
    rh = f"range_high_{lookback}"
    rl = f"range_low_{lookback}"
    trades = []
    in_trade = False
    entry = sl = tp = 0.0
    edate = None

    for i in range(lookback + 1, len(df)):
        r = df.iloc[i]
        if not in_trade:
            if (r["cross_up"]
                    and pd.notna(r[rh])
                    and r["close"] > r[rh]):
                entry = r["close"]
                atr_sl = entry - 1.5 * r["atr14"]
                sl = max(r[rl], atr_sl)  # tighter of the two
                risk = entry - sl
                if risk <= 0:
                    continue
                tp = entry + risk * rr
                edate = r["date"]
                in_trade = True
        else:
            if r["low"] <= sl:
                trades.append(Trade(((sl - entry) / entry) * 100,
                                    (r["date"] - edate).days))
                in_trade = False
            elif r["high"] >= tp:
                trades.append(Trade(((tp - entry) / entry) * 100,
                                    (r["date"] - edate).days))
                in_trade = False
    return trades


def run_v5(df, lookback=5, rr=2.0):
    """V5 Trailing: entry same as V1, but stepped trailing SL instead of fixed TP.
    At 1R profit -> SL to breakeven, 2R -> SL to 1R, 3R -> SL to 2R.
    Also exit on EMA cross down."""
    rh = f"range_high_{lookback}"
    rl = f"range_low_{lookback}"
    trades = []
    in_trade = False
    entry = sl = initial_risk = highest = 0.0
    edate = None

    for i in range(lookback + 1, len(df)):
        r = df.iloc[i]
        if not in_trade:
            if (r["cross_up"]
                    and pd.notna(r[rh])
                    and r["close"] > r[rh]):
                entry = r["close"]
                sl = r[rl]
                initial_risk = entry - sl
                if initial_risk <= 0:
                    continue
                highest = r["high"]
                edate = r["date"]
                in_trade = True
        else:
            highest = max(highest, r["high"])
            ir = initial_risk
            if highest >= entry + ir:
                sl = max(sl, entry)
            if highest >= entry + 2 * ir:
                sl = max(sl, entry + ir)
            if highest >= entry + 3 * ir:
                sl = max(sl, entry + 2 * ir)

            # Check cross down for exit
            cross_dn = r["ema10"] < r["ema20"]

            if r["low"] <= sl:
                trades.append(Trade(((sl - entry) / entry) * 100,
                                    (r["date"] - edate).days))
                in_trade = False
            elif cross_dn and r["close"] < r["ema20"]:
                trades.append(Trade(((r["close"] - entry) / entry) * 100,
                                    (r["date"] - edate).days))
                in_trade = False
    return trades


def run_v6(df, lookback=5, rr=2.0):
    """V6 Combined: RSI<70 + Vol>1.2x + tight SL + trailing exit"""
    rh = f"range_high_{lookback}"
    rl = f"range_low_{lookback}"
    trades = []
    in_trade = False
    entry = sl = initial_risk = highest = 0.0
    edate = None

    for i in range(lookback + 1, len(df)):
        r = df.iloc[i]
        if not in_trade:
            vol_ok = pd.notna(r["vol_ma20"]) and r["volume"] > 1.2 * r["vol_ma20"]
            if (r["cross_up"]
                    and pd.notna(r[rh])
                    and r["close"] > r[rh]
                    and r["rsi14"] < 70
                    and vol_ok):
                entry = r["close"]
                atr_sl = entry - 1.5 * r["atr14"]
                sl = max(r[rl], atr_sl)
                initial_risk = entry - sl
                if initial_risk <= 0:
                    continue
                highest = r["high"]
                edate = r["date"]
                in_trade = True
        else:
            highest = max(highest, r["high"])
            ir = initial_risk
            if highest >= entry + ir:
                sl = max(sl, entry)
            if highest >= entry + 2 * ir:
                sl = max(sl, entry + ir)
            if highest >= entry + 3 * ir:
                sl = max(sl, entry + 2 * ir)

            cross_dn = r["ema10"] < r["ema20"]

            if r["low"] <= sl:
                trades.append(Trade(((sl - entry) / entry) * 100,
                                    (r["date"] - edate).days))
                in_trade = False
            elif cross_dn and r["close"] < r["ema20"]:
                trades.append(Trade(((r["close"] - entry) / entry) * 100,
                                    (r["date"] - edate).days))
                in_trade = False
    return trades


# ── Metrics ─────────────────────────────────────────────────

def calc(trades):
    if not trades:
        return None
    pnls = [t.pnl_pct for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    tw = sum(wins) if wins else 0
    tl = abs(sum(losses)) if losses else 0
    pf = tw / tl if tl > 0 else (float("inf") if tw > 0 else 0)
    wr = len(wins) / len(pnls) * 100
    aw = np.mean(wins) if wins else 0
    al = np.mean(losses) if losses else 0
    exp = (wr / 100 * aw) + ((1 - wr / 100) * al)
    equity = [100]
    for p in pnls:
        equity.append(equity[-1] * (1 + p / 100))
    peak = equity[0]
    mdd = 0
    for e in equity:
        peak = max(peak, e)
        mdd = max(mdd, (peak - e) / peak * 100)
    return {
        "trades": len(trades), "wr": round(wr, 1),
        "exp": round(exp, 2), "pf": round(pf, 2),
        "aw": round(aw, 2), "al": round(al, 2),
        "total": round(sum(pnls), 1), "mdd": round(mdd, 1),
        "days": round(np.mean([t.holding_days for t in trades]), 1),
    }


# ── Main ────────────────────────────────────────────────────

VERSIONS = {
    "V1_Base":        run_v1,
    "V2_RSI":         run_v2,
    "V3_Volume":      run_v3,
    "V4_TightSL":     run_v4,
    "V5_Trailing":    run_v5,
    "V6_Combined":    run_v6,
}


def main():
    files = sorted([f for f in os.listdir(DATA_DIR) if f.endswith(".csv")])
    print(f"Loading {len(files)} stocks...")

    all_dfs = {}
    for fname in files:
        ticker = fname.replace("NSE_", "").replace("-EQ.csv", "")
        try:
            df = load_and_prepare(os.path.join(DATA_DIR, fname))
            if len(df) >= 50:
                all_dfs[ticker] = df
        except Exception:
            continue
    print(f"Loaded {len(all_dfs)} stocks.\n")

    # ── Phase 1: Compare all 6 versions with default params ──
    print("=" * 130)
    print(f"{'PHASE 1: VERSION COMPARISON (lookback=5, RR=2.0)':^130}")
    print("=" * 130)
    hdr = (f"  {'Version':<18} {'Trades':>7} {'Win%':>7} {'Expect':>8} {'PF':>6} "
           f"{'AvgWin':>8} {'AvgLoss':>9} {'TotalPnL':>10} {'MaxDD':>8} {'AvgDays':>8}")
    print(hdr)
    print("-" * 130)

    phase1 = []
    for vname, vfn in VERSIONS.items():
        all_trades = []
        for ticker, df in all_dfs.items():
            all_trades.extend(vfn(df, lookback=5, rr=2.0))
        m = calc(all_trades)
        if m:
            print(f"  {vname:<18} {m['trades']:>7} {m['wr']:>5.1f}% {m['exp']:>7.2f}% "
                  f"{m['pf']:>5.2f} {m['aw']:>7.2f}% {m['al']:>8.2f}% "
                  f"{m['total']:>9.1f}% {m['mdd']:>7.1f}% {m['days']:>7.1f}")
            phase1.append({"version": vname, **m})

    # ── Phase 2: Full parameter grid for ALL versions ──
    print(f"\n{'=' * 130}")
    print(f"{'PHASE 2: FULL PARAMETER GRID (all versions x lookbacks x RR)':^130}")
    print("=" * 130)
    hdr2 = (f"  {'Config':<40} {'Trades':>7} {'Win%':>7} {'Expect':>8} {'PF':>6} "
            f"{'AvgWin':>8} {'AvgLoss':>9} {'TotalPnL':>10} {'MaxDD':>8} {'AvgDays':>8}")
    print(hdr2)
    print("-" * 130)

    all_results = []
    for vname, vfn in VERSIONS.items():
        for lb in [5, 7, 10]:
            for rr in [2.0, 2.5, 3.0]:
                all_trades = []
                for ticker, df in all_dfs.items():
                    all_trades.extend(vfn(df, lookback=lb, rr=rr))
                m = calc(all_trades)
                if m and m["trades"] > 50:
                    label = f"{vname} LB={lb} RR={rr}"
                    print(f"  {label:<40} {m['trades']:>7} {m['wr']:>5.1f}% {m['exp']:>7.2f}% "
                          f"{m['pf']:>5.2f} {m['aw']:>7.2f}% {m['al']:>8.2f}% "
                          f"{m['total']:>9.1f}% {m['mdd']:>7.1f}% {m['days']:>7.1f}")
                    all_results.append({"config": label, **m})

    # ── Find winners ──
    best_exp = max(all_results, key=lambda x: x["exp"])
    best_pf = max(all_results, key=lambda x: x["pf"] if x["trades"] > 200 else -999)
    best_total = max(all_results, key=lambda x: x["total"])

    print(f"\n{'=' * 130}")
    print(f"{'WINNERS':^130}")
    print("=" * 130)

    print(f"\nBEST BY EXPECTANCY:")
    print(f"  {best_exp['config']}")
    print(f"  Trades: {best_exp['trades']} | Win Rate: {best_exp['wr']}%")
    print(f"  Expectancy: {best_exp['exp']}% per trade")
    print(f"  Profit Factor: {best_exp['pf']}")
    print(f"  Avg Win: {best_exp['aw']}% | Avg Loss: {best_exp['al']}%")
    rr_realized = abs(best_exp['aw'] / best_exp['al']) if best_exp['al'] != 0 else 0
    print(f"  Realized R:R: 1:{rr_realized:.1f}")
    print(f"  Total PnL: {best_exp['total']}%")

    print(f"\nBEST BY PROFIT FACTOR (200+ trades):")
    print(f"  {best_pf['config']}")
    print(f"  Trades: {best_pf['trades']} | PF: {best_pf['pf']} | Expectancy: {best_pf['exp']}%")

    print(f"\nBEST BY TOTAL PnL:")
    print(f"  {best_total['config']}")
    print(f"  Trades: {best_total['trades']} | Total PnL: {best_total['total']}% | PF: {best_total['pf']}")

    # ── Phase 3: Top 15 stocks for the winner ──
    # Parse winner config
    winner = best_exp
    parts = winner["config"].split()
    w_version = parts[0]
    w_lb = int(parts[1].split("=")[1])
    w_rr = float(parts[2].split("=")[1])
    w_fn = VERSIONS[w_version]

    print(f"\n{'=' * 130}")
    print(f"TOP 15 STOCKS FOR: {winner['config']}")
    print("=" * 130)
    print(f"  {'Stock':<20} {'Trades':>7} {'Win%':>7} {'TotalPnL':>10} {'Expect':>8} {'PF':>7} {'AvgDays':>8}")
    print(f"  {'-' * 80}")

    stock_results = []
    for ticker, df in all_dfs.items():
        trades = w_fn(df, lookback=w_lb, rr=w_rr)
        m = calc(trades)
        if m and m["trades"] > 0:
            stock_results.append({"stock": ticker, **m})

    stock_results.sort(key=lambda x: x["total"], reverse=True)
    for s in stock_results[:15]:
        print(f"  {s['stock']:<20} {s['trades']:>7} {s['wr']:>5.1f}% "
              f"{s['total']:>9.1f}% {s['exp']:>7.2f}% {s['pf']:>6.2f} {s['days']:>7.1f}")

    print(f"\nBOTTOM 5:")
    for s in stock_results[-5:]:
        if s["trades"] > 0:
            print(f"  {s['stock']:<20} {s['trades']:>7} {s['wr']:>5.1f}% "
                  f"{s['total']:>9.1f}% {s['pf']:>6.2f}")

    # ── PnL Distribution ──
    all_trades = []
    for ticker, df in all_dfs.items():
        all_trades.extend(w_fn(df, lookback=w_lb, rr=w_rr))

    pnls = [t.pnl_pct for t in all_trades]
    print(f"\n{'=' * 130}")
    print(f"PnL DISTRIBUTION FOR: {winner['config']}")
    print("=" * 130)
    bins = [(-100, -10), (-10, -5), (-5, -2), (-2, 0), (0, 2), (2, 5), (5, 10), (10, 20), (20, 50), (50, 500)]
    for lo, hi in bins:
        cnt = sum(1 for p in pnls if lo <= p < hi)
        bar = "#" * min(cnt, 80)
        print(f"  {lo:>6.0f}% to {hi:>5.0f}%: {cnt:>5}  {bar}")

    # ── Save ──
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    pd.DataFrame(all_results).to_csv(os.path.join(OUTPUT_DIR, "ema_range_breakout_grid.csv"), index=False)
    pd.DataFrame(stock_results).to_csv(os.path.join(OUTPUT_DIR, "ema_range_breakout_best_per_stock.csv"), index=False)
    print(f"\nSaved: {OUTPUT_DIR}/ema_range_breakout_grid.csv")
    print(f"Saved: {OUTPUT_DIR}/ema_range_breakout_best_per_stock.csv")


if __name__ == "__main__":
    main()
