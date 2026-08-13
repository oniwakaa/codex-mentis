"""Data analyst agent — profile datasets, run statistical analyses, explain findings."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from pitagora.agents.base import BaseAgent, AgentResponse
from pitagora.agents.providers.base import BaseProvider

DATA_ANALYST_PROMPT = """<role>Data analyst in Pitagora. Explore datasets, run statistical analyses, and explain findings clearly.</role>

<instructions>
- Profile a dataset before diving into analysis
- Recommend analyses based on data characteristics and the user's question
- Generate and run Python code for computations (pandas, scipy, numpy)
- Present results with clear explanations — no jargon without definition
- Visualize when it adds clarity (distributions, correlations, trends)
- State assumptions and limitations of any analysis
- For statistical tests, report effect size and confidence, not just p-values
</instructions>

<tools>
- load_data(path_or_url) → DataFrame
- profile_data(df) → DataProfile
- run_analysis(df, analysis_type, columns, params) → AnalysisResult
- create_plot(df, plot_type, x, y, save_path) → plot_path
</tools>
"""

class AnalysisRequest(BaseModel):
    """Structured request describing which analysis to run."""
    analysis_type: str = Field(description="ttest | mann_whitney | anova | chi_squared | linear_regression")
    columns: List[str] = Field(description="Columns involved in the analysis")
    params: Dict[str, Any] = Field(default_factory=dict, description="Extra parameters (e.g. group column)")


class DataAnalystAgent(BaseAgent):
    def __init__(self, provider: BaseProvider):
        super().__init__(
            name="DataAnalyst",
            role="Statistical Data Analyst",
            provider=provider,
            system_prompt=DATA_ANALYST_PROMPT,
        )
        # In-session dataset registry: name → DataFrame
        self._datasets: Dict[str, Any] = {}

        self.register_tool(
            "load_data",
            {
                "name": "load_data",
                "description": "Load a CSV/TSV/JSON/Parquet/Excel dataset from a path or URL.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path_or_url": {"type": "string", "description": "File path or URL"},
                        "name": {"type": "string", "description": "Optional handle to reference the dataset later"},
                    },
                    "required": ["path_or_url"],
                },
            },
            self.tool_load_data,
        )
        self.register_tool(
            "profile_data",
            {
                "name": "profile_data",
                "description": "Profile a loaded dataset: types, missing values, stats, correlations.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Dataset handle (default: 'default')"},
                    },
                },
            },
            self.tool_profile_data,
        )
        self.register_tool(
            "run_analysis",
            {
                "name": "run_analysis",
                "description": "Run a statistical analysis (ttest, mann_whitney, anova, chi_squared, linear_regression).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Dataset handle"},
                        "analysis_type": {"type": "string", "description": "ttest | mann_whitney | anova | chi_squared | linear_regression"},
                        "columns": {"type": "array", "items": {"type": "string"}},
                        "params": {"type": "object"},
                    },
                    "required": ["analysis_type", "columns"],
                },
            },
            self.tool_run_analysis,
        )
        self.register_tool(
            "create_plot",
            {
                "name": "create_plot",
                "description": "Generate a plot (line, scatter, hist, bar) for a loaded dataset.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Dataset handle"},
                        "plot_type": {"type": "string", "description": "line | scatter | hist | bar"},
                        "x": {"type": "string"},
                        "y": {"type": "string"},
                        "save_path": {"type": "string", "description": "Optional path to save a PNG"},
                    },
                    "required": ["plot_type"],
                },
            },
            self.tool_create_plot,
        )

    def _df(self, name: str):
        if not self._datasets:
            raise KeyError("No dataset loaded. Call load_data first.")
        return self._datasets[name or "default" or list(self._datasets)[0]]

    async def tool_load_data(self, path_or_url: str, name: str = "default") -> str:
        from pitagora.data_analysis.loader import load_data, LoaderError
        try:
            df = load_data(path_or_url)
        except LoaderError as e:
            return json.dumps({"status": "error", "message": str(e)})
        self._datasets[name] = df
        return json.dumps({
            "status": "ok",
            "name": name,
            "rows": int(df.shape[0]),
            "cols": int(df.shape[1]),
            "columns": list(df.columns),
        })

    async def tool_profile_data(self, name: str = "default") -> str:
        from pitagora.data_analysis.profiler import profile_data
        try:
            df = self._df(name)
        except KeyError as e:
            return json.dumps({"status": "error", "message": str(e)})
        prof = profile_data(df)
        return prof.model_dump_json(indent=2)

    async def tool_run_analysis(
        self, analysis_type: str, columns: List[str], name: str = "default",
        params: Optional[Dict[str, Any]] = None,
    ) -> str:
        from pitagora.data_analysis import analyzer
        params = params or {}
        try:
            df = self._df(name)
        except KeyError as e:
            return json.dumps({"status": "error", "message": str(e)})

        at = (analysis_type or "").lower()
        try:
            if at == "ttest":
                res = analyzer.run_ttest(df[columns[0]], df[columns[1]],
                                         equal_var=bool(params.get("equal_var", True)))
            elif at == "mann_whitney":
                res = analyzer.run_mann_whitney(df[columns[0]], df[columns[1]])
            elif at == "anova":
                res = analyzer.run_anova(*[df[c] for c in columns])
            elif at == "chi_squared":
                tbl = df.pivot_table(index=columns[0], columns=columns[1],
                                      values=params.get("values", columns[0]),
                                      aggfunc="size", fill_value=0)
                res = analyzer.run_chi_squared(tbl)
            elif at == "linear_regression":
                res = analyzer.linear_regression(df, columns[0], columns[1:])
            else:
                return json.dumps({"status": "error", "message": f"unknown analysis: {at}"})
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})
        return res.model_dump_json(indent=2)

    async def tool_create_plot(
        self, plot_type: str, x: str = "", y: str = "", name: str = "default",
        save_path: str = "",
    ) -> str:
        from pitagora.data_analysis.visualizer import create_plot
        try:
            df = self._df(name)
        except KeyError as e:
            return json.dumps({"status": "error", "message": str(e)})
        out = create_plot(df, plot_type=plot_type, x=x or None, y=y or None,
                          save_path=save_path or None)
        return json.dumps({"status": "ok", "plot": out})

    async def analyze(self, question: str, path_or_url: str = "") -> AgentResponse:
        """High-level entry: load a dataset (if given) and answer a question."""
        prompt = question
        if path_or_url:
            load = await self.tool_load_data(path_or_url)
            prompt = f"Loaded dataset ({load}). Question: {question}"
        return await self.athink(prompt)
