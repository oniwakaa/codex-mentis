"""Data analysis module — load, profile, analyze, and visualize datasets.

ponytail: pandas is the core dep. Excel (.xlsx) and Parquet need optional extras
(``pip install 'pitagora[data]'``); loader degrades gracefully when the engine
is missing. No dataset fetcher — YAGNI until a real source is needed.
"""
from pitagora.data_analysis.loader import load_data, LoaderError
from pitagora.data_analysis.profiler import profile_data, DataProfile, ColumnProfile
from pitagora.data_analysis.analyzer import (
    run_ttest, run_chi_squared, run_anova, run_mann_whitney,
    linear_regression, AnalysisResult,
)
from pitagora.data_analysis.visualizer import create_plot

__all__ = [
    "load_data",
    "LoaderError",
    "profile_data",
    "DataProfile",
    "ColumnProfile",
    "run_ttest",
    "run_chi_squared",
    "run_anova",
    "run_mann_whitney",
    "linear_regression",
    "AnalysisResult",
    "create_plot",
]
