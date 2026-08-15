import asyncio
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any

from pitagora.agents.guards import LoopGuard


class LoopState(Enum):
    CONTEXT_CHECK = auto()
    THINKING = auto()
    ACTION = auto()
    TOOL_EXECUTION = auto()
    DECISION = auto()
    TERMINATED = auto()


@dataclass
class LoopConfig:
    max_iterations: int = 25
    max_cost_usd: float = 2.0
    wall_clock_timeout_s: int = 300
    compaction_threshold: float = 0.80
    thinking_enabled: bool = True
    parallel_read_tools: int = 5


@dataclass
class LoopResult:
    response: str
    iterations: int
    total_tokens: int
    total_cost_usd: float
    tool_calls: list[dict]
    session_id: str
    stop_reason: str  # "completed" | "max_iterations" | "timeout" | "cost_exceeded" | "doom_loop"


class AgentLoop:
    def __init__(
        self,
        provider: Any,
        tools: list | None = None,
        config: LoopConfig | None = None,
        guard: LoopGuard | None = None,
        tool_executor: Callable[[dict], Awaitable[dict]] | None = None,
    ):
        self.provider = provider
        self.tools = tools or []
        self.config = config or LoopConfig()
        self.guard = guard or LoopGuard(
            max_iterations=self.config.max_iterations,
            max_cost_usd=self.config.max_cost_usd,
            wall_clock_timeout_s=self.config.wall_clock_timeout_s,
        )
        self.tool_executor = tool_executor
        self._state = LoopState.CONTEXT_CHECK
        self._messages: list[dict] = []
        self._total_tokens = 0
        self._total_cost = 0.0
        self._iteration = 0
        self._recorded_tool_calls: list[dict] = []
        self._session_id = f"session_{uuid.uuid4().hex[:8]}"

    def _estimate_tokens(self) -> int:
        total_chars = sum(len(m.get("content", "")) for m in self._messages)
        return total_chars // 4

    def _compact_context(self) -> None:
        """Summarize old messages when approaching token budget."""
        if len(self._messages) <= 6:
            return
        system_msg = [m for m in self._messages if m.get("role") == "system"]
        user_msg = [m for m in self._messages if m.get("role") == "user"][:1]
        older = self._messages[2:-4]
        recent = self._messages[-4:]

        if not older:
            return

        summary_lines = []
        for m in older:
            r = m.get("role", "unknown")
            c = str(m.get("content", ""))[:150]
            summary_lines.append(f"[{r}] {c}")

        compacted_msg = {
            "role": "system",
            "content": "[Previous context summary]\n" + "\n".join(summary_lines),
        }
        self._messages = system_msg + user_msg + [compacted_msg] + recent

    async def _execute_tool(self, tool_call: dict) -> dict:
        name = tool_call.get("name", "")
        args = tool_call.get("arguments", {})
        if self.tool_executor:
            return await self.tool_executor(tool_call)

        if hasattr(self.tools, "execute"):
            return await self.tools.execute(name, args)

        for spec in self.tools:
            spec_name = spec.get("name") if isinstance(spec, dict) else getattr(spec, "name", "")
            if spec_name == name:
                handler = (
                    spec.get("handler")
                    if isinstance(spec, dict)
                    else getattr(spec, "handler", None)
                )
                if handler:
                    res = handler(**args)
                    if asyncio.iscoroutine(res) or hasattr(res, "__await__"):
                        res = await res
                    return {"tool_name": name, "result": res, "error": None}

        return {"tool_name": name, "result": None, "error": f"Unknown tool: {name}"}

    async def _execute_tools_parallel(self, tool_calls: list[dict]) -> list[dict]:
        reads = []
        writes = []
        for tc in tool_calls:
            name = tc.get("name", "")
            perm = "read"
            if hasattr(self.tools, "_tools"):
                spec = self.tools._tools.get(name)
                if spec:
                    perm = getattr(spec, "required_permission", "read")
            else:
                for spec in self.tools:
                    spec_name = getattr(spec, "name", "") or (
                        spec.get("name") if isinstance(spec, dict) else ""
                    )
                    if spec_name == name:
                        perm = getattr(spec, "required_permission", "read")
                        if isinstance(spec, dict):
                            perm = spec.get("required_permission", "read")

            if perm == "read":
                reads.append(tc)
            else:
                writes.append(tc)

        results = []
        if reads:
            read_tasks = [self._execute_tool(tc) for tc in reads]
            read_results = await asyncio.gather(*read_tasks, return_exceptions=True)
            for tc, res in zip(reads, read_results, strict=False):
                if isinstance(res, Exception):
                    results.append(
                        {"tool_name": tc.get("name", ""), "result": None, "error": str(res)}
                    )
                else:
                    results.append(res)

        for tc in writes:
            try:
                res = await self._execute_tool(tc)
                results.append(res)
            except Exception as e:
                results.append({"tool_name": tc.get("name", ""), "result": None, "error": str(e)})

        return results

    async def run(self, user_input: str, system_prompt: str = "") -> LoopResult:
        """Execute the full 6-phase ReAct agent loop."""
        self._state = LoopState.CONTEXT_CHECK
        self._messages = []
        if system_prompt:
            self._messages.append({"role": "system", "content": system_prompt})
        self._messages.append({"role": "user", "content": user_input})

        last_response = ""
        stop_reason = "completed"

        while True:
            # Phase 0: Context Check
            self._state = LoopState.CONTEXT_CHECK
            if self._estimate_tokens() > 1000:  # Check token budget threshold
                self._compact_context()

            # Phase 1: Thinking (optional, no tools)
            if self.config.thinking_enabled:
                self._state = LoopState.THINKING
                think_messages = self._messages + [
                    {"role": "user", "content": "Think through the problem step by step."}
                ]
                try:
                    think_res = await self.provider.acomplete(think_messages)
                    usage = think_res.get("usage", {})
                    self._total_tokens += usage.get("prompt_tokens", 0) + usage.get(
                        "completion_tokens", 0
                    )
                    cost = think_res.get("cost_usd", 0.0)
                    self._total_cost += cost
                except Exception:
                    pass

            # Phase 2: Action (LLM call with tools)
            self._state = LoopState.ACTION
            if hasattr(self.tools, "get_schemas"):
                tool_schemas = self.tools.get_schemas("admin")
            elif self.tools:
                tool_schemas = [
                    {
                        "name": getattr(
                            t, "name", t.get("name", "") if isinstance(t, dict) else ""
                        ),
                        "description": getattr(
                            t,
                            "description",
                            t.get("description", "") if isinstance(t, dict) else "",
                        ),
                        "input_schema": getattr(
                            t,
                            "input_schema",
                            t.get("input_schema", {}) if isinstance(t, dict) else {},
                        ),
                    }
                    for t in self.tools
                ]
            else:
                tool_schemas = None

            action_res = await self.provider.acomplete(self._messages, tools=tool_schemas)
            usage = action_res.get("usage", {})
            self._total_tokens += usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)
            self._total_cost += action_res.get("cost_usd", 0.0)

            last_response = action_res.get("content", "")
            tool_calls = action_res.get("tool_calls", [])

            self._messages.append({"role": "assistant", "content": last_response})

            # Phase 3: Tool Execution
            if tool_calls:
                self._state = LoopState.TOOL_EXECUTION
                exec_results = await self._execute_tools_parallel(tool_calls)
                for tc, res in zip(tool_calls, exec_results, strict=False):
                    self._recorded_tool_calls.append({"call": tc, "result": res})
                    self._messages.append(
                        {
                            "role": "tool",
                            "name": tc.get("name", ""),
                            "content": str(res.get("result") or res.get("error")),
                        }
                    )

            # Phase 4: Decision (Guard checks)
            self._state = LoopState.DECISION
            self._iteration += 1

            if not self.guard.check_iteration(self._iteration):
                if self._iteration >= self.guard.max_iterations:
                    stop_reason = "max_iterations"
                else:
                    stop_reason = "timeout"
                break

            if not self.guard.check_cost(self._total_cost):
                stop_reason = "cost_exceeded"
                break

            resp_hash = LoopGuard.hash_response(last_response)
            if not self.guard.check_loop_detection("agent_loop", resp_hash):
                stop_reason = "doom_loop"
                break

            if not tool_calls:
                stop_reason = "completed"
                break

        self._state = LoopState.TERMINATED
        return LoopResult(
            response=last_response,
            iterations=self._iteration,
            total_tokens=self._total_tokens,
            total_cost_usd=self._total_cost,
            tool_calls=self._recorded_tool_calls,
            session_id=self._session_id,
            stop_reason=stop_reason,
        )
