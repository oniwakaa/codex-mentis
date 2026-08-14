"""Dataset visualizer — terminal (plotext) + file (matplotlib) charts."""

from __future__ import annotations

import os
import sys
from io import StringIO

import numpy as np
import pandas as pd


def create_plot(
    df: pd.DataFrame,
    plot_type: str = "line",
    x: str | None = None,
    y: str | None = None,
    save_path: str | None = None,
    title: str | None = None,
) -> str:
    """Generate a terminal ASCII plot and optionally save a PNG.

    plot_type: line | scatter | hist | bar
    """
    plot_type = (plot_type or "line").lower()
    out = ""

    try:
        import plotext as plt

        plt.clear_data()
        plt.clear_terminal()

        if plot_type == "hist":
            data = _series_numeric(df, y or x)
            plt.hist(data)
            plt.title(title or f"Histogram of {y or x}")
        elif plot_type == "bar":
            xs = _series(df, x) if x else list(range(len(df)))
            ys = _series_numeric(df, y)
            plt.bar(xs, ys)
            plt.title(title or f"Bar: {y} by {x}")
        elif plot_type == "scatter":
            xv = _series_numeric(df, x)
            yv = _series_numeric(df, y)
            plt.scatter(xv, yv)
            plt.title(title or f"Scatter: {y} vs {x}")
            plt.xlabel(x or "")
            plt.ylabel(y or "")
        else:  # line
            xv = _series_numeric(df, x) if x else list(range(len(df)))
            yv = _series_numeric(df, y)
            plt.plot(xv, yv)
            plt.title(title or f"Line: {y}")
            plt.xlabel(x or "")
            plt.ylabel(y or "")

        old = sys.stdout
        captured = sys.stdout = StringIO()
        plt.show()
        sys.stdout = old
        out = captured.getvalue()
    except ImportError:
        out = f"[plotext not installed; cannot render {plot_type} plot]"

    if save_path:
        out += "\n" + _save_matplotlib(df, plot_type, x, y, save_path, title)
    return out


def _series(df: pd.DataFrame, col: str | None):
    if not col or col not in df.columns:
        return list(range(len(df)))
    return [str(v) for v in df[col].tolist()]


def _series_numeric(df: pd.DataFrame, col: str | None) -> np.ndarray:
    if not col or col not in df.columns:
        return np.arange(len(df))
    return pd.to_numeric(df[col], errors="coerce").dropna().to_numpy(dtype=float)


def _save_matplotlib(df, plot_type, x, y, save_path, title) -> str:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return "[matplotlib not installed; PNG not saved]"

    fig, ax = plt.subplots(figsize=(8, 5))
    if plot_type == "hist":
        ax.hist(_series_numeric(df, y or x), bins=20)
        ax.set_xlabel(y or x)
    elif plot_type == "bar":
        ax.bar(_series(df, x), _series_numeric(df, y))
        ax.set_xlabel(x or "")
        ax.set_ylabel(y or "")
    elif plot_type == "scatter":
        ax.scatter(_series_numeric(df, x), _series_numeric(df, y))
        ax.set_xlabel(x or "")
        ax.set_ylabel(y or "")
    else:
        ax.plot(_series_numeric(df, x) if x else range(len(df)), _series_numeric(df, y))
        ax.set_xlabel(x or "")
        ax.set_ylabel(y or "")
    ax.set_title(title or f"{plot_type}: {y or x}")
    ax.grid(True, alpha=0.3)
    os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
    plt.tight_layout()
    plt.savefig(save_path)
    plt.close(fig)
    return f"Saved plot to {save_path}"
