"""
EMA Crossover + Range Breakout — Trailing SL Variants
=====================================================
Entry (all versions): 10 EMA crosses above 20 EMA + close > range high of last N candles.
SL base: range low of last N candles.

Exit variations tested:
  V1 - Fixed RR (baseline for comparison)
  V2 - EMA Cross Exit: exit when 10 EMA crosses below 20 EMA (no fixed TP)
  V3 - SL + EMA Cross: initial SL at range low, exit on EMA cross down (no TP)
  V4 - Breakeven + EMA Cross: move SL to breakeven at 1R profit, exit on EMA cross down
  V5 - 20 EMA Trail: once 1R profit hit, trail SL at 20 EMA, exit on cross down
  V6 - 20 EMA Trail tight: trail SL at 20 EMA - 0.5*ATR for buffer, exit on cross
  V7 - Stepped trail + EMA cross: 1R->BE, 2R->1R, 3R->2R, also exit on cross down
  V8 - Close below 20 EMA exit (not cross, just close < 20 EMA after 1R profit)
"""

import pandas as pd
import numpy as np
import os
import warnings

warnings.filterwarnings("ignore")

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")


def ema(s, p):
    return s.ewm(span=p, adjust=False).mean()

def atr(df, p=14):
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift(1)).abs(),
        (df["low"] - df["close"].shift(1)).abs()
    ], axis=1).max(axis=1)
    return tr.ewm(span=p, adjust=False).mean()


def load(filepath):
    df = pd.read_csv(filepath, parse_dates=["time"])
    df = df.sort_values("time").reset_index(drop=True)
    df.rename(columns={"time": "date"}, inplace=True)
    df["ema10"] = ema(df["close"], 10)
    df["ema20"] = ema(df["close"], 20)
    df["atr14"] = atr(df, 14)
    above = df["ema10"] > df["ema20"]
    df["cross_up"] = above & ~above.shift(1, fill_value=False)
    df["cross_down"] = ~above & above.shift(1, fill_value=True)
    for lb in [5, 7, 10]:
        df[f"rh_{lb}"] = df["high"].shift(1).rolling(lb).max()
        df[f"rl_{lb}"] = df["low"].shift(1).rolling(lb).min()
    return df


def entry_ok(r, lb):
    rh = f"rh_{lb}"
    return r["cross_up"] and pd.notna(r[rh]) and r["close"] > r[rh]


# ── V1: Fixed RR ────────────────────────────────────────────
def v1(df, lb=10, rr=3.0):
    rl = f"rl_{lb}"
    trades = []
    in_t = False
    ent = sl = tp = 0.0
    ed = None
    for i in range(lb + 1, len(df)):
        r = df.iloc[i]
        if not in_t:
            if entry_ok(r, lb):
                ent = r["close"]; sl = r[rl]; risk = ent - sl
                if risk <= 0: continue
                tp = ent + risk * rr; ed = r["date"]; in_t = True
        else:
            if r["low"] <= sl:
                trades.append(((sl - ent) / ent * 100, (r["date"] - ed).days))
                in_t = False
            elif r["high"] >= tp:
                trades.append(((tp - ent) / ent * 100, (r["date"] - ed).days))
                in_t = False
    return trades


# ── V2: Pure EMA cross down exit ────────────────────────────
def v2(df, lb=10, **_):
    rl = f"rl_{lb}"
    trades = []
    in_t = False
    ent = sl = 0.0
    ed = None
    for i in range(lb + 1, len(df)):
        r = df.iloc[i]
        if not in_t:
            if entry_ok(r, lb):
                ent = r["close"]; sl = r[rl]
                if ent - sl <= 0: continue
                ed = r["date"]; in_t = True
        else:
            if r["low"] <= sl:
                trades.append(((sl - ent) / ent * 100, (r["date"] - ed).days))
                in_t = False
            elif r["cross_down"]:
                trades.append(((r["close"] - ent) / ent * 100, (r["date"] - ed).days))
                in_t = False
    return trades


# ── V3: SL + EMA cross (close on cross, no TP) ─────────────
def v3(df, lb=10, **_):
    rl = f"rl_{lb}"
    trades = []
    in_t = False
    ent = sl = 0.0
    ed = None
    for i in range(lb + 1, len(df)):
        r = df.iloc[i]
        if not in_t:
            if entry_ok(r, lb):
                ent = r["close"]; sl = r[rl]
                if ent - sl <= 0: continue
                ed = r["date"]; in_t = True
        else:
            if r["low"] <= sl:
                trades.append(((sl - ent) / ent * 100, (r["date"] - ed).days))
                in_t = False
            elif r["cross_down"] and r["close"] < r["ema20"]:
                trades.append(((r["close"] - ent) / ent * 100, (r["date"] - ed).days))
                in_t = False
    return trades


# ── V4: Move SL to breakeven at 1R, exit on EMA cross ──────
def v4(df, lb=10, **_):
    rl = f"rl_{lb}"
    trades = []
    in_t = False
    ent = sl = ir = hi = 0.0
    ed = None
    for i in range(lb + 1, len(df)):
        r = df.iloc[i]
        if not in_t:
            if entry_ok(r, lb):
                ent = r["close"]; sl = r[rl]; ir = ent - sl
                if ir <= 0: continue
                hi = r["high"]; ed = r["date"]; in_t = True
        else:
            hi = max(hi, r["high"])
            if hi >= ent + ir:
                sl = max(sl, ent)  # breakeven
            if r["low"] <= sl:
                trades.append(((sl - ent) / ent * 100, (r["date"] - ed).days))
                in_t = False
            elif r["cross_down"]:
                trades.append(((r["close"] - ent) / ent * 100, (r["date"] - ed).days))
                in_t = False
    return trades


# ── V5: Trail SL at 20 EMA after 1R profit ─────────────────
def v5(df, lb=10, **_):
    rl = f"rl_{lb}"
    trades = []
    in_t = False
    ent = sl = ir = hi = 0.0
    be_hit = False
    ed = None
    for i in range(lb + 1, len(df)):
        r = df.iloc[i]
        if not in_t:
            if entry_ok(r, lb):
                ent = r["close"]; sl = r[rl]; ir = ent - sl
                if ir <= 0: continue
                hi = r["high"]; be_hit = False; ed = r["date"]; in_t = True
        else:
            hi = max(hi, r["high"])
            if hi >= ent + ir:
                be_hit = True
            if be_hit:
                sl = max(sl, r["ema20"])  # trail at 20 EMA
            if r["low"] <= sl:
                trades.append(((sl - ent) / ent * 100, (r["date"] - ed).days))
                in_t = False
            elif r["cross_down"] and be_hit:
                trades.append(((r["close"] - ent) / ent * 100, (r["date"] - ed).days))
                in_t = False
    return trades


# ── V6: Trail SL at 20 EMA - 0.5*ATR (buffer) ──────────────
def v6(df, lb=10, **_):
    rl = f"rl_{lb}"
    trades = []
    in_t = False
    ent = sl = ir = hi = 0.0
    be_hit = False
    ed = None
    for i in range(lb + 1, len(df)):
        r = df.iloc[i]
        if not in_t:
            if entry_ok(r, lb):
                ent = r["close"]; sl = r[rl]; ir = ent - sl
                if ir <= 0: continue
                hi = r["high"]; be_hit = False; ed = r["date"]; in_t = True
        else:
            hi = max(hi, r["high"])
            if hi >= ent + ir:
                be_hit = True
            if be_hit:
                sl = max(sl, r["ema20"] - 0.5 * r["atr14"])
            if r["low"] <= sl:
                trades.append(((sl - ent) / ent * 100, (r["date"] - ed).days))
                in_t = False
            elif r["cross_down"] and be_hit:
                trades.append(((r["close"] - ent) / ent * 100, (r["date"] - ed).days))
                in_t = False
    return trades


# ── V7: Stepped trail (1R->BE, 2R->1R, 3R->2R) + EMA cross ─
def v7(df, lb=10, **_):
    rl = f"rl_{lb}"
    trades = []
    in_t = False
    ent = sl = ir = hi = 0.0
    ed = None
    for i in range(lb + 1, len(df)):
        r = df.iloc[i]
        if not in_t:
            if entry_ok(r, lb):
                ent = r["close"]; sl = r[rl]; ir = ent - sl
                if ir <= 0: continue
                hi = r["high"]; ed = r["date"]; in_t = True
        else:
            hi = max(hi, r["high"])
            if hi >= ent + ir:      sl = max(sl, ent)
            if hi >= ent + 2 * ir:  sl = max(sl, ent + ir)
            if hi >= ent + 3 * ir:  sl = max(sl, ent + 2 * ir)
            if r["low"] <= sl:
                trades.append(((sl - ent) / ent * 100, (r["date"] - ed).days))
                in_t = False
            elif r["cross_down"] and r["close"] < r["ema20"]:
                trades.append(((r["close"] - ent) / ent * 100, (r["date"] - ed).days))
                in_t = False
    return trades


# ── V8: Close below 20 EMA exit (after breakeven) ──────────
def v8(df, lb=10, **_):
    rl = f"rl_{lb}"
    trades = []
    in_t = False
    ent = sl = ir = hi = 0.0
    be_hit = False
    ed = None
    for i in range(lb + 1, len(df)):
        r = df.iloc[i]
        if not in_t:
            if entry_ok(r, lb):
                ent = r["close"]; sl = r[rl]; ir = ent - sl
                if ir <= 0: continue
                hi = r["high"]; be_hit = False; ed = r["date"]; in_t = True
        else:
            hi = max(hi, r["high"])
            if hi >= ent + ir:
                be_hit = True
                sl = max(sl, ent)
            if r["low"] <= sl:
                trades.append(((sl - ent) / ent * 100, (r["date"] - ed).days))
                in_t = False
            elif be_hit and r["close"] < r["ema20"]:
                trades.append(((r["close"] - ent) / ent * 100, (r["date"] - ed).days))
                in_t = False
    return trades


# ── Metrics ─────────────────────────────────────────────────
def calc(trades):
    if not trades:
        return None
    pnls = [t[0] for t in trades]
    days = [t[1] for t in trades]
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
        "days": round(np.mean(days), 1),
    }


VERSIONS = {
    "V1_FixedRR":       v1,
    "V2_PureCrossExit": v2,
    "V3_SL+CrossExit":  v3,
    "V4_BE+CrossExit":  v4,
    "V5_EMA20Trail":    v5,
    "V6_EMA20+ATRBuf":  v6,
    "V7_StepTrail+Cross": v7,
    "V8_ClsBelowEMA":   v8,
}


def main():
    files = sorted([f for f in os.listdir(DATA_DIR) if f.endswith(".csv")])
    print(f"Loading {len(files)} stocks...")
    all_dfs = {}
    for fname in files:
        ticker = fname.replace("NSE_", "").replace("-EQ.csv", "")
        try:
            df = load(os.path.join(DATA_DIR, fname))
            if len(df) >= 50:
                all_dfs[ticker] = df
        except Exception:
            continue
    print(f"Loaded {len(all_dfs)} stocks.\n")

    # ═══════════════════════════════════════════════════════════
    # PHASE 1: All versions at LB=10 (compare exit methods)
    # ═══════════════════════════════════════════════════════════
    print("=" * 140)
    print(f"{'PHASE 1: EXIT METHOD COMPARISON (Lookback=10)':^140}")
    print("=" * 140)
    hdr = (f"  {'Version':<22} {'Trades':>7} {'Win%':>7} {'Expect':>8} {'PF':>6} "
           f"{'AvgWin':>8} {'AvgLoss':>9} {'TotalPnL':>10} {'MaxDD':>8} {'AvgDays':>8}")
    print(hdr)
    print("-" * 140)

    phase1 = []
    for vname, vfn in VERSIONS.items():
        all_t = []
        for df in all_dfs.values():
            all_t.extend(vfn(df, lb=10, rr=3.0))
        m = calc(all_t)
        if m:
            print(f"  {vname:<22} {m['trades']:>7} {m['wr']:>5.1f}% {m['exp']:>7.2f}% "
                  f"{m['pf']:>5.2f} {m['aw']:>7.2f}% {m['al']:>8.2f}% "
                  f"{m['total']:>9.1f}% {m['mdd']:>7.1f}% {m['days']:>7.1f}")
            phase1.append({"version": vname, **m})

    # ═══════════════════════════════════════════════════════════
    # PHASE 2: Full grid for trailing versions
    # ═══════════════════════════════════════════════════════════
    print(f"\n{'=' * 140}")
    print(f"{'PHASE 2: FULL PARAMETER GRID (trailing versions x lookbacks)':^140}")
    print("=" * 140)
    hdr2 = (f"  {'Config':<42} {'Trades':>7} {'Win%':>7} {'Expect':>8} {'PF':>6} "
            f"{'AvgWin':>8} {'AvgLoss':>9} {'TotalPnL':>10} {'MaxDD':>8} {'AvgDays':>8}")
    print(hdr2)
    print("-" * 140)

    all_results = []
    for vname, vfn in VERSIONS.items():
        for lb in [5, 7, 10]:
            all_t = []
            for df in all_dfs.values():
                all_t.extend(vfn(df, lb=lb, rr=3.0))
            m = calc(all_t)
            if m and m["trades"] > 50:
                label = f"{vname} LB={lb}"
                print(f"  {label:<42} {m['trades']:>7} {m['wr']:>5.1f}% {m['exp']:>7.2f}% "
                      f"{m['pf']:>5.2f} {m['aw']:>7.2f}% {m['al']:>8.2f}% "
                      f"{m['total']:>9.1f}% {m['mdd']:>7.1f}% {m['days']:>7.1f}")
                all_results.append({"config": label, **m})

    # ═══════════════════════════════════════════════════════════
    # WINNERS
    # ═══════════════════════════════════════════════════════════
    best_exp = max(all_results, key=lambda x: x["exp"])
    best_pf = max(all_results, key=lambda x: x["pf"] if x["trades"] > 200 else -999)
    best_total = max(all_results, key=lambda x: x["total"])

    # Among trailing only (exclude V1)
    trailing_only = [r for r in all_results if not r["config"].startswith("V1")]
    best_trail_exp = max(trailing_only, key=lambda x: x["exp"]) if trailing_only else None
    best_trail_pf = max(trailing_only, key=lambda x: x["pf"] if x["trades"] > 200 else -999) if trailing_only else None

    print(f"\n{'=' * 140}")
    print(f"{'WINNERS':^140}")
    print("=" * 140)

    print(f"\nOVERALL BEST (Expectancy):")
    b = best_exp
    print(f"  {b['config']}")
    print(f"  Trades: {b['trades']} | Win%: {b['wr']}% | Expectancy: {b['exp']}% | PF: {b['pf']}")
    print(f"  Avg Win: {b['aw']}% | Avg Loss: {b['al']}% | R:R: 1:{abs(b['aw']/b['al']) if b['al'] else 0:.1f}")
    print(f"  Total PnL: {b['total']}% | MaxDD: {b['mdd']}% | Avg Hold: {b['days']} days")

    if best_trail_exp:
        print(f"\nBEST TRAILING EXIT (Expectancy):")
        b = best_trail_exp
        print(f"  {b['config']}")
        print(f"  Trades: {b['trades']} | Win%: {b['wr']}% | Expectancy: {b['exp']}% | PF: {b['pf']}")
        print(f"  Avg Win: {b['aw']}% | Avg Loss: {b['al']}% | R:R: 1:{abs(b['aw']/b['al']) if b['al'] else 0:.1f}")
        print(f"  Total PnL: {b['total']}% | MaxDD: {b['mdd']}% | Avg Hold: {b['days']} days")

    if best_trail_pf:
        print(f"\nBEST TRAILING EXIT (Profit Factor, 200+ trades):")
        b = best_trail_pf
        print(f"  {b['config']}")
        print(f"  Trades: {b['trades']} | PF: {b['pf']} | Expectancy: {b['exp']}%")

    # ═══════════════════════════════════════════════════════════
    # PHASE 3: Top stocks for best trailing version
    # ═══════════════════════════════════════════════════════════
    if best_trail_exp:
        winner = best_trail_exp
        parts = winner["config"].split()
        w_ver = parts[0]
        w_lb = int(parts[1].split("=")[1])
        w_fn = VERSIONS[w_ver]

        print(f"\n{'=' * 140}")
        print(f"TOP 15 STOCKS FOR: {winner['config']}")
        print("=" * 140)
        print(f"  {'Stock':<20} {'Trades':>7} {'Win%':>7} {'TotalPnL':>10} {'Expect':>8} {'PF':>7} {'AvgWin':>8} {'AvgLoss':>9} {'AvgDays':>8}")
        print(f"  {'-' * 95}")

        stock_res = []
        for ticker, df in all_dfs.items():
            trades = w_fn(df, lb=w_lb, rr=3.0)
            m = calc(trades)
            if m and m["trades"] > 0:
                stock_res.append({"stock": ticker, **m})

        stock_res.sort(key=lambda x: x["total"], reverse=True)
        for s in stock_res[:15]:
            print(f"  {s['stock']:<20} {s['trades']:>7} {s['wr']:>5.1f}% "
                  f"{s['total']:>9.1f}% {s['exp']:>7.2f}% {s['pf']:>6.2f} "
                  f"{s['aw']:>7.2f}% {s['al']:>8.2f}% {s['days']:>7.1f}")

        print(f"\nBOTTOM 5:")
        for s in stock_res[-5:]:
            print(f"  {s['stock']:<20} {s['trades']:>7} {s['wr']:>5.1f}% "
                  f"{s['total']:>9.1f}% {s['pf']:>6.2f}")

        # Save
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        pd.DataFrame(all_results).to_csv(
            os.path.join(OUTPUT_DIR, "ema_breakout_trailing_grid.csv"), index=False)
        pd.DataFrame(stock_res).to_csv(
            os.path.join(OUTPUT_DIR, "ema_breakout_trailing_best_per_stock.csv"), index=False)
        print(f"\nSaved: {OUTPUT_DIR}/ema_breakout_trailing_grid.csv")
        print(f"Saved: {OUTPUT_DIR}/ema_breakout_trailing_best_per_stock.csv")


if __name__ == "__main__":
    main()
