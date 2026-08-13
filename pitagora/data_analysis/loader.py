"""Dataset loader — auto-detect format and return a pandas DataFrame.

Supports local paths and URLs. Formats: CSV, TSV, JSON, Parquet, Excel.
Parquet/Excel require the optional ``data`` extra; the loader raises a clear
LoaderError when the engine is missing instead of a bare ImportError.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import pandas as pd


class LoaderError(Exception):
    """Raised when a dataset cannot be loaded or parsed."""


def _is_url(s: str) -> bool:
    return urlparse(s).scheme in ("http", "https", "ftp")


def _detect_format(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext in (".csv", ".tsv", ".txt"):
        return "csv"
    if ext in (".json", ".jsonl"):
        return "json"
    if ext in (".parquet", ".pq"):
        return "parquet"
    if ext in (".xlsx", ".xls"):
        return "excel"
    return "csv"  # default guess


def load_data(path_or_url: str, **kwargs) -> pd.DataFrame:
    """Load a dataset from a path or URL into a pandas DataFrame.

    Auto-detects format from the extension. CSV/TSV/JSON work out of the box;
    Parquet and Excel need the optional ``data`` extra. Extra kwargs are
    forwarded to the underlying pandas reader.
    """
    if not path_or_url:
        raise LoaderError("Empty path/URL")

    source = path_or_url.strip()
    fmt = _detect_format(source)

    # For local files, confirm existence before handing off to pandas so the
    # error message stays actionable.
    if not _is_url(source) and not os.path.exists(source):
        raise LoaderError(f"File not found: {source}")

    try:
        if fmt == "csv":
            sep = kwargs.pop("sep", "\t" if source.lower().endswith(".tsv") else ",")
            return pd.read_csv(source, sep=sep, **kwargs)
        if fmt == "json":
            return pd.read_json(source, **kwargs)
        if fmt == "parquet":
            try:
                return pd.read_parquet(source, **kwargs)
            except ImportError as e:
                raise LoaderError(
                    "Parquet support requires pyarrow: pip install 'pitagora[data]'"
                ) from e
        if fmt == "excel":
            try:
                return pd.read_excel(source, **kwargs)
            except ImportError as e:
                raise LoaderError(
                    "Excel support requires openpyxl: pip install 'pitagora[data]'"
                ) from e
    except LoaderError:
        raise
    except Exception as e:
        raise LoaderError(f"Failed to load {source}: {e}") from e

    raise LoaderError(f"Unsupported format: {source}")
