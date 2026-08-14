"""Tests for WS5: data analysis module + data agent + data CLI."""

import os
import tempfile

import numpy as np
import pandas as pd
import pytest
from typer.testing import CliRunner

from pitagora.cli.app import app

runner = CliRunner()


@pytest.fixture
def sample_csv(tmp_path):
    p = tmp_path / "sample.csv"
    df = pd.DataFrame(
        {
            "group": ["a", "a", "a", "b", "b", "b"],
            "value": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
            "score": [10, 20, 30, 40, 50, 60],
            "label": ["x", "y", "x", "y", "x", "y"],
        }
    )
    df.to_csv(p, index=False)
    return str(p)


# ─── loader ─────────────────────────────────────────────────────────────────


def test_loader_csv(sample_csv):
    from pitagora.data_analysis.loader import LoaderError, load_data

    df = load_data(sample_csv)
    assert df.shape == (6, 4)
    assert "value" in df.columns


def test_loader_missing_file():
    from pitagora.data_analysis.loader import LoaderError, load_data

    with pytest.raises(LoaderError):
        load_data("/nonexistent/path.csv")


# ─── profiler ───────────────────────────────────────────────────────────────


def test_profiler(sample_csv):
    from pitagora.data_analysis.profiler import profile_data

    df = pd.read_csv(sample_csv)
    prof = profile_data(df)
    assert prof.rows == 6
    assert prof.cols == 4
    types = {c.name: c.inferred_type for c in prof.columns}
    assert types["value"] == "numeric"
    assert types["group"] in ("categorical", "text")
    # correlation between value and score (perfectly correlated)
    assert prof.correlation["value"]["score"] == pytest.approx(1.0, abs=0.01)
    val = next(c for c in prof.columns if c.name == "value")
    assert val.mean == pytest.approx(3.5)


# ─── analyzer ───────────────────────────────────────────────────────────────


def test_analyzer_ttest():
    from pitagora.data_analysis.analyzer import run_ttest

    a = [1.0, 2.0, 3.0, 4.0]
    b = [10.0, 11.0, 12.0, 13.0]
    res = run_ttest(a, b)
    assert res.test == "ttest"
    assert res.p_value < 0.05
    assert res.effect_size is not None


def test_analyzer_chi_squared():
    from pitagora.data_analysis.analyzer import run_chi_squared

    table = pd.DataFrame({"yes": [10, 20], "no": [30, 40]})
    res = run_chi_squared(table)
    assert res.test == "chi_squared"
    assert res.p_value >= 0.0


def test_analyzer_linear_regression(sample_csv):
    from pitagora.data_analysis.analyzer import linear_regression

    df = pd.read_csv(sample_csv)
    res = linear_regression(df, "score", ["value"])
    # value and score are perfectly correlated → R² ≈ 1
    assert res.effect_size == pytest.approx(1.0, abs=0.02)
    # New schema: coefficients + SEs + t-stats + p-values + CIs per term
    assert "coef_value" in res.extra
    assert res.extra["coef_value"] == pytest.approx(10.0, abs=0.05)
    assert "se_value" in res.extra
    assert "p_value" in res.extra  # per-coefficient p-value
    assert "ci95_value_low" in res.extra and "ci95_value_high" in res.extra
    # value is a significant predictor
    assert "value" in res.interpretation


def test_analyzer_anova_insufficient():
    from pitagora.data_analysis.analyzer import run_anova

    res = run_anova([1.0, 2.0])
    assert res.p_value == 1.0
    assert "insufficient" in res.interpretation or "need" in res.interpretation


# ─── visualizer ─────────────────────────────────────────────────────────────


def test_visualizer_hist(sample_csv):
    from pitagora.data_analysis.visualizer import create_plot

    df = pd.read_csv(sample_csv)
    out = create_plot(df, plot_type="hist", y="value")
    assert isinstance(out, str)
    assert len(out) > 0


def test_visualizer_save_png(sample_csv, tmp_path):
    from pitagora.data_analysis.visualizer import create_plot

    df = pd.read_csv(sample_csv)
    out_path = str(tmp_path / "plot.png")
    out = create_plot(df, plot_type="scatter", x="value", y="score", save_path=out_path)
    assert os.path.exists(out_path)
    assert "Saved" in out


# ─── data agent ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_data_agent_load_and_profile(sample_csv, mock_provider):
    from pitagora.agents.data_analyst import DataAnalystAgent

    agent = DataAnalystAgent(mock_provider)
    load_res = await agent.tool_load_data(sample_csv)
    import json

    d = json.loads(load_res)
    assert d["status"] == "ok"
    assert d["rows"] == 6

    prof_res = await agent.tool_profile_data()
    d = json.loads(prof_res)
    assert d["rows"] == 6
    assert d["cols"] == 4


@pytest.mark.asyncio
async def test_data_agent_run_analysis(sample_csv, mock_provider):
    from pitagora.agents.data_analyst import DataAnalystAgent

    agent = DataAnalystAgent(mock_provider)
    await agent.tool_load_data(sample_csv)
    res = await agent.tool_run_analysis("ttest", ["value", "score"])
    import json

    d = json.loads(res)
    assert d["test"] == "ttest"


# ─── data CLI ───────────────────────────────────────────────────────────────


def test_data_cli_help():
    result = runner.invoke(app, ["data", "--help"])
    assert result.exit_code == 0
    for sub in ["load", "profile", "analyze", "plot"]:
        assert sub in result.output


def test_data_cli_load(sample_csv):
    result = runner.invoke(app, ["data", "load", sample_csv])
    assert result.exit_code == 0
    assert "6 rows" in result.output


def test_data_cli_profile(sample_csv):
    result = runner.invoke(app, ["data", "profile", "--path", sample_csv])
    assert result.exit_code == 0
    assert "Rows: 6" in result.output


def test_data_cli_plot(sample_csv):
    result = runner.invoke(app, ["data", "plot", "hist", "--y", "value", "--path", sample_csv])
    assert result.exit_code == 0
