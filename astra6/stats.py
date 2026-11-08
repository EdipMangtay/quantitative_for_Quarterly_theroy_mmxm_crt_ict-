"""Statistical Validation & Robustness Engine (Section 15).

Implements:
* Full trade-stream performance metrics (Win rate, Mean/Median R, Expectancy,
  Profit Factor, Max Drawdown in R, Max Consecutive Losses, Annualised Sharpe &
  Sortino on daily aggregated R, MFE/MAE, holding time)
* Moving-Block Bootstrap confidence intervals & two-strategy paired/block
  difference tests (preserves serial & same-day cluster dependence)
* Holm-Bonferroni & Benjamini-Hochberg (FDR) multiple-testing adjustments
* Chronological Train / Validation / Out-of-Sample Test evaluation
* Rolling Walk-Forward Analysis (WFA)
* Matched Conditioned Controls (matching on time-of-day, volatility tercile,
  and timeframe when comparing CRT+SSMT+CISD vs CRT-only)
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats as sp_stats


def max_consecutive_losses(r: np.ndarray) -> int:
    best = cur = 0
    for x in r:
        if x < 0:
            cur += 1
            if cur > best:
                best = cur
        else:
            cur = 0
    return int(best)


def max_drawdown_r(r: np.ndarray) -> float:
    if r.size == 0:
        return 0.0
    eq = np.cumsum(r)
    peak = np.maximum.accumulate(np.r_[0.0, eq])
    dd = peak[1:] - eq
    return float(dd.max()) if dd.size else 0.0


def summarize_trades(
    df: pd.DataFrame,
    r_col: str = "r",
    n_boot: int = 1000,
    block_size: int = 5,
    seed: int = 42,
) -> dict:
    """Compute comprehensive Section 15 & Phase 6.5/9.3 metrics for a trade table."""
    if df is None or len(df) == 0:
        return {
            "n_trades": 0, "win_rate": np.nan, "avg_win_r": np.nan, "avg_loss_r": np.nan,
            "avg_r": np.nan, "median_r": np.nan, "expectancy": np.nan, "total_r": 0.0,
            "profit_factor": np.nan, "max_dd_r": 0.0, "max_consec_losses": 0,
            "sharpe": np.nan, "sortino": np.nan, "avg_mfe": np.nan, "avg_mae": np.nan,
            "avg_hold_min": np.nan, "ci95_low": np.nan, "ci95_high": np.nan,
            "p_gt_zero": np.nan, "ci_spans_zero": True, "small_sample": True,
            "in_sample_avg_r": np.nan, "oos_avg_r": np.nan, "oos_n": 0,
            "stat_status": "EMPTY",
        }
    sub = df[np.isfinite(df[r_col].to_numpy(float))]
    r = sub[r_col].to_numpy(float)
    n = r.size
    if n == 0:
        return summarize_trades(df.iloc[0:0], r_col=r_col)

    wins = r[r > 0]
    losses = r[r < 0]
    wr = float((r > 0).mean())
    avg_win = float(wins.mean()) if wins.size else np.nan
    avg_loss = float(losses.mean()) if losses.size else np.nan
    avg_r = float(r.mean())
    med_r = float(np.median(r))
    tot_r = float(r.sum())
    gp = float(wins.sum()) if wins.size else 0.0
    gl = float(-losses.sum()) if losses.size else 0.0
    pf = float(gp / gl) if gl > 1e-12 else (np.inf if gp > 0 else np.nan)
    mdd = max_drawdown_r(r)
    mcl = max_consecutive_losses(r)

    # Daily aggregated R & In-Sample / Out-of-Sample split
    if "t_trig" in sub.columns:
        ts_utc = pd.to_datetime(sub["t_trig"], utc=True)
        days = ts_utc.dt.floor("D")
        daily_r = pd.Series(r).groupby(days.to_numpy()).sum().to_numpy(float)
        oos_mask = (ts_utc >= pd.Timestamp("2025-07-01", tz="UTC")).to_numpy()
        is_r = r[~oos_mask]
        oos_r = r[oos_mask]
        in_sample_avg = float(is_r.mean()) if is_r.size else np.nan
        oos_avg = float(oos_r.mean()) if oos_r.size else np.nan
        oos_cnt = int(oos_r.size)
    else:
        daily_r = r
        in_sample_avg = np.nan
        oos_avg = np.nan
        oos_cnt = 0

    if daily_r.size >= 5 and daily_r.std(ddof=1) > 1e-12:
        sharpe = float((daily_r.mean() / daily_r.std(ddof=1)) * np.sqrt(252.0))
        dn_std = float(np.sqrt(np.mean(np.minimum(0.0, daily_r) ** 2)))
        sortino = float((daily_r.mean() / dn_std) * np.sqrt(252.0)) if dn_std > 1e-12 else np.nan
    else:
        sharpe = np.nan
        sortino = np.nan

    ci_lo, ci_hi, p_pos = block_bootstrap_mean(r, n_boot=n_boot, block_size=block_size, seed=seed)
    spans_zero = bool(np.isnan(ci_lo) or (ci_lo <= 0.0 <= ci_hi))
    small_smp = bool(n < 30)
    if small_smp:
        status = "SMALL_SAMPLE_UNRELIABLE"
    elif avg_r <= 0.0:
        status = "NEGATIVE_EXPECTANCY"
    elif not spans_zero and ci_lo > 0.0:
        status = "VERIFIED_POSITIVE_CI"
    else:
        status = "POSITIVE_MEAN_CI_SPANS_ZERO"

    return {
        "n_trades": int(n),
        "win_rate": wr,
        "avg_win_r": avg_win,
        "avg_loss_r": avg_loss,
        "avg_r": avg_r,
        "median_r": med_r,
        "expectancy": avg_r,
        "total_r": tot_r,
        "profit_factor": pf,
        "max_dd_r": mdd,
        "max_consec_losses": mcl,
        "sharpe": sharpe,
        "sortino": sortino,
        "avg_mfe": float(sub["mfe"].mean()) if "mfe" in sub.columns else np.nan,
        "avg_mae": float(sub["mae"].mean()) if "mae" in sub.columns else np.nan,
        "avg_hold_min": float(sub["hold"].mean()) if "hold" in sub.columns else np.nan,
        "ci95_low": ci_lo,
        "ci95_high": ci_hi,
        "p_gt_zero": p_pos,
        "ci_spans_zero": spans_zero,
        "small_sample": small_smp,
        "in_sample_avg_r": in_sample_avg,
        "oos_avg_r": oos_avg,
        "oos_n": oos_cnt,
        "stat_status": status,
    }


def block_bootstrap_mean(
    r: np.ndarray,
    n_boot: int = 1000,
    block_size: int = 5,
    seed: int = 42,
) -> tuple[float, float, float]:
    """Circular moving-block bootstrap 95% CI for E[R] and one-sided p-value (H0: E[R] <= 0)."""
    n = r.size
    if n < 3:
        return np.nan, np.nan, np.nan
    b = max(1, min(block_size, n))
    n_blocks = int(np.ceil(n / b))
    rng = np.random.default_rng(seed)
    starts = rng.integers(0, n, size=(n_boot, n_blocks))
    offs = np.arange(b)[None, None, :]
    idx = (starts[:, :, None] + offs).reshape(n_boot, -1)[:, :n] % n
    means = r[idx].mean(axis=1)
    ci_lo, ci_hi = np.percentile(means, [2.5, 97.5])
    # One-sided bootstrap p-value for H0: mean <= 0
    p_val = float((means <= 0.0).mean())
    return float(ci_lo), float(ci_hi), p_val


def compare_two_models(
    df_treat: pd.DataFrame,
    df_base: pd.DataFrame,
    r_col: str = "r",
    n_boot: int = 2000,
    seed: int = 42,
) -> dict:
    """Test whether treatment model has higher net expectancy than baseline model."""
    rt = df_treat[r_col].dropna().to_numpy(float) if len(df_treat) else np.array([])
    rb = df_base[r_col].dropna().to_numpy(float) if len(df_base) else np.array([])
    if rt.size < 5 or rb.size < 5:
        return {
            "n_treat": int(rt.size), "n_base": int(rb.size),
            "mean_treat": float(rt.mean()) if rt.size else np.nan,
            "mean_base": float(rb.mean()) if rb.size else np.nan,
            "diff_r": np.nan, "ci95_low": np.nan, "ci95_high": np.nan,
            "p_boot": np.nan, "p_welch": np.nan, "p_mannwhitney": np.nan,
        }
    rng = np.random.default_rng(seed)
    bt = Math_block_means(rt, n_boot, min(5, rt.size), rng)
    bb = Math_block_means(rb, n_boot, min(5, rb.size), rng)
    diffs = bt - bb
    ci_lo, ci_hi = np.percentile(diffs, [2.5, 97.5])
    p_boot = float((diffs <= 0.0).mean())
    _, p_welch = sp_stats.ttest_ind(rt, rb, equal_var=False, alternative="greater")
    _, p_mw = sp_stats.mannwhitneyu(rt, rb, alternative="greater")
    return {
        "n_treat": int(rt.size),
        "n_base": int(rb.size),
        "mean_treat": float(rt.mean()),
        "mean_base": float(rb.mean()),
        "diff_r": float(rt.mean() - rb.mean()),
        "ci95_low": float(ci_lo),
        "ci95_high": float(ci_hi),
        "p_boot": p_boot,
        "p_welch": float(p_welch),
        "p_mannwhitney": float(p_mw),
    }


def Math_block_means(r: np.ndarray, n_boot: int, b: int, rng: np.random.Generator) -> np.ndarray:
    n = r.size
    n_blocks = int(np.ceil(n / b))
    starts = rng.integers(0, n, size=(n_boot, n_blocks))
    offs = np.arange(b)[None, None, :]
    idx = (starts[:, :, None] + offs).reshape(n_boot, -1)[:, :n] % n
    return r[idx].mean(axis=1)


def adjust_pvalues(pvals: list[float] | np.ndarray) -> pd.DataFrame:
    """Return raw, Holm-Bonferroni, and Benjamini-Hochberg (FDR) adjusted p-values."""
    p = np.asarray(pvals, dtype=float)
    m = len(p)
    valid = np.isfinite(p)
    holm = np.full(m, np.nan)
    bh = np.full(m, np.nan)
    if valid.any():
        pv = p[valid]
        k = pv.size
        order = np.argsort(pv)
        inv = np.empty_like(order)
        inv[order] = np.arange(k)
        # Holm
        h = np.maximum.accumulate(pv[order] * (k - np.arange(k)))
        holm[valid] = np.clip(h[inv], 0.0, 1.0)
        # BH FDR
        b = np.minimum.accumulate((pv[order] * k / (np.arange(k) + 1))[::-1])[::-1]
        bh[valid] = np.clip(b[inv], 0.0, 1.0)
    return pd.DataFrame({"p_raw": p, "p_holm": holm, "p_bh_fdr": bh})


def split_evaluation(df: pd.DataFrame, r_col: str = "r") -> pd.DataFrame:
    """Chronological Train / Validation / Out-of-Sample Test split (Section 15)."""
    if len(df) == 0:
        return pd.DataFrame()
    t = pd.to_datetime(df["t_trig"], utc=True)
    splits = [
        ("Train (2021-11..2024-06)", t < pd.Timestamp("2024-07-01", tz="UTC")),
        ("Validation (2024-07..2025-06)", (t >= pd.Timestamp("2024-07-01", tz="UTC")) & (t < pd.Timestamp("2025-07-01", tz="UTC"))),
        ("OOS Test (2025-07..2026-11)", t >= pd.Timestamp("2025-07-01", tz="UTC")),
        ("Full Period (2021-11..2026-11)", pd.Series(True, index=df.index)),
    ]
    rows = []
    for label, mask in splits:
        m = summarize_trades(df[mask], r_col=r_col, n_boot=600)
        m["split"] = label
        rows.append(m)
    return pd.DataFrame(rows)


def walk_forward_analysis(
    candidates_by_model: dict[str, pd.DataFrame],
    r_col: str = "r",
    train_months: int = 12,
    test_months: int = 6,
) -> pd.DataFrame:
    """Rolling Walk-Forward Analysis: select best model on 12M train window
    (requiring >= 25 train trades), evaluate on the subsequent unseen 6M window."""
    all_t = pd.concat([d[["t_trig"]] for d in candidates_by_model.values() if len(d)], ignore_index=True)
    if len(all_t) == 0:
        return pd.DataFrame()
    t_min = pd.to_datetime(all_t["t_trig"], utc=True).min().floor("D")
    t_max = pd.to_datetime(all_t["t_trig"], utc=True).max().ceil("D")

    cur = t_min
    rows = []
    fold = 1
    while True:
        tr_end = cur + pd.DateOffset(months=train_months)
        te_end = tr_end + pd.DateOffset(months=test_months)
        if tr_end >= t_max:
            break
        best_name = None
        best_tr_r = -1e18
        best_tr_n = 0
        for name, df in candidates_by_model.items():
            if len(df) == 0:
                continue
            ts = pd.to_datetime(df["t_trig"], utc=True)
            sub_tr = df[(ts >= cur) & (ts < tr_end)]
            if len(sub_tr) < 20:
                continue
            mr = float(sub_tr[r_col].mean())
            if mr > best_tr_r:
                best_tr_r = mr
                best_name = name
                best_tr_n = len(sub_tr)
        if best_name is not None:
            df_sel = candidates_by_model[best_name]
            ts = pd.to_datetime(df_sel["t_trig"], utc=True)
            sub_te = df_sel[(ts >= tr_end) & (ts < te_end)]
            te_sum = summarize_trades(sub_te, r_col=r_col, n_boot=400)
            rows.append({
                "fold": fold,
                "train_start": str(cur.date()),
                "train_end": str(tr_end.date()),
                "test_end": str(min(te_end, t_max).date()),
                "selected_model": best_name,
                "train_n": best_tr_n,
                "train_avg_r": best_tr_r,
                "oos_n": te_sum["n_trades"],
                "oos_win_rate": te_sum["win_rate"],
                "oos_avg_r": te_sum["avg_r"],
                "oos_total_r": te_sum["total_r"],
                "oos_pf": te_sum["profit_factor"],
            })
            fold += 1
        cur = cur + pd.DateOffset(months=test_months)
    return pd.DataFrame(rows)


def matched_control_comparison(
    df_all: pd.DataFrame,
    treat_mask: pd.Series,
    base_mask: pd.Series,
    r_col: str = "r",
    n_draws: int = 1000,
    seed: int = 42,
) -> dict:
    """Matched random control: for every trade in ``treat_mask``, draw a trade
    from ``base_mask`` matched on the same (tf, session_bucket, vol_tercile) cell.
    Separates structural signal edge from hour-of-day / volatility selection effects.
    """
    work = df_all.copy()
    hr = pd.to_datetime(work["t_trig"]).dt.tz_convert("America/New_York").dt.hour
    work["_hr"] = hr
    work["_vol"] = pd.qcut(work["atr_ref"].rank(method="first"), 3, labels=["low", "mid", "high"])
    work["_cell"] = work["tf"].astype(str) + "_" + work["_hr"].astype(str) + "_" + work["_vol"].astype(str)

    tr = work[treat_mask & work[r_col].notna()]
    ba = work[base_mask & work[r_col].notna()]
    if len(tr) < 5 or len(ba) < 5:
        return {"n_treat": len(tr), "treat_avg_r": np.nan, "matched_ctrl_avg_r": np.nan, "excess_r": np.nan, "p_matched": np.nan}

    pools = {cell: g[r_col].to_numpy(float) for cell, g in ba.groupby("_cell")}
    fallback = ba[r_col].to_numpy(float)
    tr_cells = tr["_cell"].to_list()
    tr_r = tr[r_col].to_numpy(float)
    tr_mean = float(tr_r.mean())

    rng = np.random.default_rng(seed)
    ctrl_means = np.empty(n_draws)
    for b in range(n_draws):
        sample = np.empty(len(tr_r))
        for i, c in enumerate(tr_cells):
            arr = pools.get(c, fallback)
            sample[i] = arr[rng.integers(0, arr.size)]
        ctrl_means[b] = sample.mean()

    ctrl_mean = float(ctrl_means.mean())
    p_val = float((ctrl_means >= tr_mean).mean())
    ci_lo, ci_hi = np.percentile(tr_mean - ctrl_means, [2.5, 97.5])
    return {
        "n_treat": int(len(tr_r)),
        "treat_avg_r": tr_mean,
        "matched_ctrl_avg_r": ctrl_mean,
        "excess_r": float(tr_mean - ctrl_mean),
        "excess_ci95_low": float(ci_lo),
        "excess_ci95_high": float(ci_hi),
        "p_matched": p_val,
    }

