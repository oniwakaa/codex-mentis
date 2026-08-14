import json
import re
from typing import Any

from pitagora.agents.base import AgentResponse, BaseAgent
from pitagora.agents.providers.base import BaseProvider

REVIEWER_SYSTEM_PROMPT = """<role>Adversarial reviewer for Pitagora. Verify claims, inspect proofs, hunt for errors and counterexamples.</role>

<instructions>
- Assume claims are false until proven true
- Probe edge cases: zero, infinity, negatives, empty sets, boundaries
- Test numerically and symbolically with the sympy_evaluate tool
- Conclude every review with a structured verdict block
</instructions>

<output_format>
Verdict: [CONFIRMED | REFUTED | INCONCLUSIVE]
Confidence: [0.0–1.0]
Critique: [summary of findings]
</output_format>

<example>
Claim: "$\\forall x>0, \\ln x \\leq x-1$".
Verdict: CONFIRMED
Confidence: 0.95
Critique: Equality at $x=1$; derivative $1/x - 1 \\le 0$ for $x \\ge 1$ and $\\ge 0$ for $0<x\\le 1$, so $\\ln x - (x-1)$ peaks at 0. Verified via sympy.
</example>
"""


class ReviewerAgent(BaseAgent):
    def __init__(self, provider: BaseProvider):
        super().__init__(
            name="Reviewer",
            role="Adversarial Mathematical Reviewer",
            provider=provider,
            system_prompt=REVIEWER_SYSTEM_PROMPT,
        )

        # Register the SymPy evaluation tool
        self.register_tool(
            "sympy_evaluate",
            {
                "name": "sympy_evaluate",
                "description": "Run Python code to test mathematical equations or claims with specific values or checks.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "Python code using SymPy/NumPy. Expose variables and print the result of checks.",
                        }
                    },
                    "required": ["code"],
                },
            },
            self.tool_sympy_evaluate,
        )

    def tool_sympy_evaluate(self, code: str) -> str:
        """Executes code in the project's SymPy sandbox to evaluate mathematical claims."""
        from pitagora.math_engine.sandbox import SymPySandbox

        sandbox = SymPySandbox()
        res = sandbox.execute(code)
        return json.dumps(res)

    def _parse_verdict(self, content: str) -> dict[str, Any]:
        """
        Parse the verdict, confidence and critique from the agent's text response.
        """
        verdict = "INCONCLUSIVE"
        confidence = 0.5
        critique = "No review critique generated."

        # Look for Verdict: CONFIRMED/REFUTED/INCONCLUSIVE
        verdict_match = re.search(
            r"Verdict:\s*(CONFIRMED|REFUTED|INCONCLUSIVE)", content, re.IGNORECASE
        )
        if verdict_match:
            verdict = verdict_match.group(1).upper()

        # Look for Confidence: 0.x
        conf_match = re.search(r"Confidence:\s*(0\.\d+|1\.0|1)", content, re.IGNORECASE)
        if conf_match:
            try:
                confidence = float(conf_match.group(1))
            except ValueError:
                pass

        # Look for Critique: text
        critique_match = re.search(r"Critique:\s*(.*)", content, re.DOTALL | re.IGNORECASE)
        if critique_match:
            critique = critique_match.group(1).strip()

        return {"verdict": verdict, "confidence": confidence, "critique": critique}

    def review(self, claim: str) -> AgentResponse:
        """
        Adversarially review a mathematical/physical claim.
        """
        prompt = (
            f"Review the following claim:\n"
            f"Claim: {claim}\n\n"
            f"Test this claim. Check for physical soundness, algebraic consistency, and special cases. "
            f"If appropriate, write test code and run it via 'sympy_evaluate' to search for counterexamples. "
            f"Conclude with your Verdict, Confidence, and Critique."
        )

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt},
        ]

        # Perform up to 2 tool execution steps if the agent requests tests
        for _ in range(2):
            response = self.provider.complete(messages, tools=self.tools)
            content = response.get("content", "")
            tool_calls = response.get("tool_calls", [])

            if not tool_calls:
                parsed = self._parse_verdict(content)
                return AgentResponse(
                    content=content,
                    tool_calls=[],
                    confidence=parsed["confidence"],
                    metadata={
                        "agent_name": self.name,
                        "agent_role": self.role,
                        "verdict": parsed["verdict"],
                        "critique": parsed["critique"],
                    },
                )

            messages.append({"role": "assistant", "content": content})

            tool_results = []
            for tc in tool_calls:
                name = tc["name"]
                args = tc["arguments"]
                res = self.with_tool(name, args)
                tool_results.append(f"Tool {name} returned:\n{res}")

            messages.append({"role": "user", "content": "\n\n".join(tool_results)})

        response = self.provider.complete(messages)
        content = response.get("content", "")
        parsed = self._parse_verdict(content)
        return AgentResponse(
            content=content,
            tool_calls=[],
            confidence=parsed["confidence"],
            metadata={
                "agent_name": self.name,
                "agent_role": self.role,
                "verdict": parsed["verdict"],
                "critique": parsed["critique"],
            },
        )

    def review_proof(self, steps: list[str]) -> AgentResponse:
        """
        Adversarially review a step-by-step proof.
        """
        steps_str = "\n".join([f"Step {i+1}: {step}" for i, step in enumerate(steps)])
        prompt = (
            f"Review the correctness of each step in this proof:\n\n"
            f"{steps_str}\n\n"
            f"Point out the first step that contains an error, if any. Explain the error. "
            f"Test individual step equations using 'sympy_evaluate' if needed. Conclude with Verdict, Confidence, and Critique."
        )

        # We can just call review with this structured prompt
        return self.review(prompt)

    def find_counterexample(self, claim: str) -> AgentResponse:
        """
        Specifically focuses on trying to find a counterexample to disprove a claim.
        """
        prompt = (
            f"Actively seek a counterexample to disprove the following claim:\n"
            f"Claim: {claim}\n\n"
            f"Write code using 'sympy_evaluate' to search across parameters, boundary values, or non-trivial domains. "
            f"If you find a counterexample, display it clearly. If you are confident none exists, explain why."
        )
        return self.review(prompt)
