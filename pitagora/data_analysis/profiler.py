"""Dataset profiler — auto-profile a DataFrame into structured stats.

Returns a DataProfile (pydantic model) with per-column type, missing-value
counts, basic stats, cardinality, correlation matrix, and distribution shape.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

try:
    from scipy import stats as _scipy_stats

    _HAVE_SCIPY = True
except Exception:  # pragma: no cover - scipy is a core dep
    _HAVE_SCIPY = False


class ColumnProfile(BaseModel):
    name: str
    inferred_type: str  # numeric | categorical | datetime | text | boolean
    missing_count: int
    missing_pct: float
    cardinality: int
    # numeric-only stats (None otherwise)
    mean: float | None = None
    median: float | None = None
    std: float | None = None
    min: float | None = None
    max: float | None = None
    skewness: float | None = None
    kurtosis: float | None = None


class DataProfile(BaseModel):
    rows: int
    cols: int
    columns: list[ColumnProfile]
    correlation: dict[str, dict[str, float]] = Field(default_factory=dict)


def _infer_type(series: pd.Series) -> str:
    if pd.api.types.is_bool_dtype(series):
        return "boolean"
    if pd.api.types.is_numeric_dtype(series):
        # numeric with very high cardinality vs rows could be an id, but keep simple
        return "numeric"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"
    nunique = series.nunique(dropna=True)
    if nunique <= max(20, len(series) // 100):
        return "categorical"
    return "text"


def profile_data(df: pd.DataFrame) -> DataProfile:
    """Profile a DataFrame: per-column stats, missing values, correlations."""
    rows, cols = df.shape
    col_profiles: list[ColumnProfile] = []

    for name in df.columns:
        series = df[name]
        inferred = _infer_type(series)
        missing = int(series.isna().sum())
        cardinality = int(series.nunique(dropna=True))

        cp = ColumnProfile(
            name=str(name),
            inferred_type=inferred,
            missing_count=missing,
            missing_pct=round(missing / rows, 4) if rows else 0.0,
            cardinality=cardinality,
        )

        if inferred == "numeric":
            cleaned = series.dropna()
            if len(cleaned):
                cp.mean = float(cleaned.mean())
                cp.median = float(cleaned.median())
                cp.std = float(cleaned.std(ddof=0)) if len(cleaned) > 1 else 0.0
                cp.min = float(cleaned.min())
                cp.max = float(cleaned.max())
                if _HAVE_SCIPY and len(cleaned) >= 3:
                    cp.skewness = float(_scipy_stats.skew(cleaned))
                    cp.kurtosis = float(_scipy_stats.kurtosis(cleaned))
                else:
                    # ponytail: numpy fallback when scipy unavailable or too few pts
                    cp.skewness = float(_np_skew(cleaned))
                    cp.kurtosis = float(_np_kurt(cleaned))

        col_profiles.append(cp)

    correlation: dict[str, dict[str, float]] = {}
    numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    if len(numeric_cols) >= 2:
        corr = df[numeric_cols].corr()
        # pydantic-friendly: round + replace NaN with 0
        for a in corr.columns:
            correlation[str(a)] = {
                str(b): (0.0 if pd.isna(corr.loc[a, b]) else round(float(corr.loc[a, b]), 4))
                for b in corr.columns
            }

    return DataProfile(rows=rows, cols=cols, columns=col_profiles, correlation=correlation)


def _np_skew(x: pd.Series) -> float:
    arr = x.to_numpy(dtype=float)
    if len(arr) < 2:
        return 0.0
    m = arr.mean()
    s = arr.std(ddof=0)
    if s == 0:
        return 0.0
    return float(np.mean(((arr - m) / s) ** 3))


def _np_kurt(x: pd.Series) -> float:
    arr = x.to_numpy(dtype=float)
    if len(arr) < 4:
        return 0.0
    m = arr.mean()
    s = arr.std(ddof=0)
    if s == 0:
        return 0.0
    return float(np.mean(((arr - m) / s) ** 4) - 3.0)
