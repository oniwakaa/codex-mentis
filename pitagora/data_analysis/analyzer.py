"""Statistical analysis engine — thin wrappers around scipy.stats + numpy.

The data agent decides which test is appropriate; these functions execute it
and return a structured AnalysisResult. No magic selection — explicit calls.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from scipy import stats as sps


class AnalysisResult(BaseModel):
    test: str
    statistic: float
    p_value: float
    effect_size: Optional[float] = None
    extra: Dict[str, float] = Field(default_factory=dict)
    interpretation: str = ""


def _clean_numeric(series) -> np.ndarray:
    s = pd.Series(series) if not isinstance(series, pd.Series) else series
    arr = pd.to_numeric(s, errors="coerce").dropna().to_numpy(dtype=float)
    return arr


def run_ttest(a, b, equal_var: bool = True) -> AnalysisResult:
    """Two-sample t-test. Cohen's d as effect size."""
    x, y = _clean_numeric(a), _clean_numeric(b)
    if len(x) < 2 or len(y) < 2:
        return AnalysisResult(test="ttest", statistic=0.0, p_value=1.0,
                              interpretation="insufficient data (need ≥2 per group)")
    t, p = sps.ttest_ind(x, y, equal_var=equal_var)
    # Cohen's d
    pooled = np.sqrt(((len(x) - 1) * x.var(ddof=1) + (len(y) - 1) * y.var(ddof=1))
                     / max(len(x) + len(y) - 2, 1))
    d = float((x.mean() - y.mean()) / pooled) if pooled else 0.0
    return AnalysisResult(test="ttest", statistic=float(t), p_value=float(p),
                          effect_size=d)


def run_mann_whitney(a, b) -> AnalysisResult:
    """Mann-Whitney U non-parametric two-sample test."""
    x, y = _clean_numeric(a), _clean_numeric(b)
    if len(x) < 1 or len(y) < 1:
        return AnalysisResult(test="mann_whitney", statistic=0.0, p_value=1.0,
                              interpretation="insufficient data")
    u, p = sps.mannwhitneyu(x, y, alternative="two-sided")
    return AnalysisResult(test="mann_whitney", statistic=float(u), p_value=float(p))


def run_anova(*groups) -> AnalysisResult:
    """One-way ANOVA across ≥3 groups. Eta-squared as effect size."""
    cleaned = [_clean_numeric(g) for g in groups]
    cleaned = [c for c in cleaned if len(c) > 0]
    if len(cleaned) < 2:
        return AnalysisResult(test="anova", statistic=0.0, p_value=1.0,
                              interpretation="need ≥2 groups")
    f, p = sps.f_oneway(*cleaned)
    # eta-squared = SS_between / SS_total
    all_vals = np.concatenate(cleaned)
    grand_mean = all_vals.mean()
    ss_total = float(((all_vals - grand_mean) ** 2).sum())
    ss_between = sum(len(c) * (c.mean() - grand_mean) ** 2 for c in cleaned)
    eta2 = float(ss_between / ss_total) if ss_total else 0.0
    return AnalysisResult(test="anova", statistic=float(f), p_value=float(p),
                          effect_size=eta2)


def run_chi_squared(table) -> AnalysisResult:
    """Chi-squared test of independence on a contingency table (DataFrame or 2D)."""
    if hasattr(table, "to_numpy"):
        arr = table.to_numpy()
    else:
        arr = np.asarray(table)
    if arr.ndim != 2 or arr.shape[0] < 2 or arr.shape[1] < 2:
        return AnalysisResult(test="chi_squared", statistic=0.0, p_value=1.0,
                              interpretation="need a 2D contingency table")
    chi2, p, dof, _ = sps.chi2_contingency(arr)
    # Cramér's V
    n = arr.sum()
    r, c = arr.shape
    v = float(np.sqrt(chi2 / (n * (min(r, c) - 1)))) if n and min(r, c) > 1 else 0.0
    return AnalysisResult(test="chi_squared", statistic=float(chi2), p_value=float(p),
                          effect_size=v, extra={"dof": float(dof)})


def linear_regression(df: pd.DataFrame, y_col: str, x_cols: Sequence[str]) -> AnalysisResult:
    """Ordinary least-squares linear regression with full inference diagnostics.

    Coefficients via numpy lstsq; standard errors, t-stats, p-values, and 95%
    CIs from the analytic OLS variance  σ²·(X'X)⁻¹  (scipy.stats.t for the cdf).
    No statsmodels dependency.
    """
    y = pd.to_numeric(df[y_col], errors="coerce")
    X = df[list(x_cols)].apply(pd.to_numeric, errors="coerce")
    mask = y.notna() & X.notna().all(axis=1)
    yv = y[mask].to_numpy(dtype=float)
    Xv = X[mask].to_numpy(dtype=float)
    n, k = Xv.shape
    if n < k + 2:  # need ≥ k+2 for residual df ≥ 1
        return AnalysisResult(test="linear_regression", statistic=0.0, p_value=1.0,
                              interpretation=f"insufficient rows ({n}) for {k} predictors (need ≥{k+2})")

    Xd = np.column_stack([np.ones(n), Xv])
    beta, *_ = np.linalg.lstsq(Xd, yv, rcond=None)
    resid = yv - Xd @ beta
    ss_res = float((resid ** 2).sum())
    ss_tot = float(((yv - yv.mean()) ** 2).sum())
    r2 = 1.0 - (ss_res / ss_tot) if ss_tot else 0.0

    df_reg = k
    df_res = n - k - 1
    # Overall F-statistic
    f = (r2 / df_reg) / ((1 - r2) / df_res) if df_res > 0 and r2 < 1 else 0.0
    p_f = 1.0 - sps.f.cdf(f, df_reg, df_res) if df_res > 0 and f > 0 else 1.0

    # Standard errors: σ² = SSR / df_res,  Var(β) = σ²·(X'X)⁻¹
    sigma2 = ss_res / df_res if df_res > 0 else 0.0
    try:
        xtx_inv = np.linalg.inv(Xd.T @ Xd)
    except np.linalg.LinAlgError:
        # Singular (perfect multicollinearity) — SEs undefined
        xtx_inv = np.zeros((k + 1, k + 1))
    se = np.sqrt(np.maximum(np.diag(sigma2 * xtx_inv), 0.0))
    # t-stats + two-sided p-values per coefficient
    t_stats = np.where(se > 0, beta / se, 0.0)
    p_vals = np.where(se > 0, 2.0 * (1.0 - sps.t.cdf(np.abs(t_stats), df_res)), 1.0)
    t_crit = sps.t.ppf(0.975, df_res) if df_res > 0 else 0.0
    ci_low = beta - t_crit * se
    ci_high = beta + t_crit * se

    names = ["intercept", *x_cols]
    extra = {f"coef_{nm}": float(b) for nm, b in zip(names, beta)}
    for nm, s, t, pv, lo, hi in zip(names, se, t_stats, p_vals, ci_low, ci_high):
        extra[f"se_{nm}"] = float(s)
        extra[f"t_{nm}"] = float(t)
        extra[f"p_{nm}"] = float(pv)
        extra[f"ci95_{nm}_low"] = float(lo)
        extra[f"ci95_{nm}_high"] = float(hi)

    sig = [nm for nm, pv in zip(names, p_vals) if pv < 0.05]
    interp = (f"R²={r2:.4f}, F({df_reg},{df_res})={f:.3f} (p={p_f:.4g}). "
              f"Significant (p<0.05): {', '.join(sig) if sig else 'none'}")
    return AnalysisResult(
        test="linear_regression",
        statistic=float(f),
        p_value=float(p_f),
        effect_size=float(r2),
        extra=extra,
        interpretation=interp,
    )
