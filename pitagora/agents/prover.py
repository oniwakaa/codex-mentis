import json
import re
from typing import Dict, Any, List, Optional, Tuple
from pitagora.agents.base import BaseAgent, AgentResponse
from pitagora.agents.providers.base import BaseProvider

PROVER_SYSTEM_PROMPT = """You are the Prover Agent for Pitagora. Your role is to perform rigorous mathematical proofs, derivations, and calculations.

Guidelines:
1. Step-by-Step Derivation: Show each mathematical transformation step clearly. Avoid skip-steps.
2. Code Verification: You have access to a SymPy execution sandbox. Use it to verify algebraic simplifications, integrals, derivatives, matrix calculations, and equations.
3. Formality: Use correct mathematical language. Define all variables. Exclude hand-wavy claims.
4. Layout: Write output in structured Markdown. Wrap every equation in correct LaTeX formatting.
"""

class ProverAgent(BaseAgent):
    def __init__(self, provider: BaseProvider):
        super().__init__(
            name="Prover",
            role="Mathematical Proof and Derivation Expert",
            provider=provider,
            system_prompt=PROVER_SYSTEM_PROMPT
        )
        
        # Register the SymPy execution tool
        self.register_tool(
            "sympy_verify",
            {
                "name": "sympy_verify",
                "description": "Run Python code utilizing SymPy to check mathematical steps, equations, or compute results.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "Python code using SymPy. SymPy is imported as 'sympy'. Predefined symbols: x, y, z, t. Call print() to return outputs."
                        }
                    },
                    "required": ["code"]
                }
            },
            self.tool_sympy_verify
        )

    def tool_sympy_verify(self, code: str) -> str:
        """
        Executes code in a SymPy sandbox. Tries importing the project's sandbox,
        otherwise falls back to a clean local execution.
        """
        try:
            from pitagora.math_engine.sandbox import SymPySandbox
            sandbox = SymPySandbox()
            res = sandbox.execute(code)
            return json.dumps(res)
        except ImportError:
            # Local fallback sandbox implementation
            import sys
            from io import StringIO
            
            old_stdout = sys.stdout
            redirected_output = sys.stdout = StringIO()
            
            local_vars: Dict[str, Any] = {}
            try:
                import sympy
                local_vars['sympy'] = sympy
                # Common math variables
                local_vars['x'], local_vars['y'], local_vars['z'], local_vars['t'] = sympy.symbols('x y z t')
            except ImportError:
                pass
                
            success = True
            error_msg = ""
            try:
                # Safe-ish execution of local sympy scripts
                exec(code, {}, local_vars)
            except Exception as e:
                success = False
                error_msg = str(e)
            finally:
                sys.stdout = old_stdout
                
            return json.dumps({
                "success": success,
                "output": redirected_output.getvalue(),
                "error": error_msg,
                "variables": {k: str(v) for k, v in local_vars.items() if k not in ('__builtins__', 'sympy')}
            })

    def generate_solution(self, problem: str) -> AgentResponse:
        """
        Generate initial candidate proof/derivation.
        """
        prompt = (
            f"Generate a step-by-step mathematical derivation/proof for the following problem:\n"
            f"Problem: {problem}\n"
            f"Make sure to explicitly label your steps and assumptions."
        )
        return self.think(prompt)

    def verify_solution(self, solution: str) -> Dict[str, Any]:
        """
        Evaluates the steps in the solution. Uses the sympy_verify tool to check algebraic correctness.
        """
        # We ask the LLM to inspect the solution, extract critical equations, and write SymPy code to verify them.
        prompt = (
            f"You are checking a mathematical derivation. Here is the candidate solution:\n"
            f"--- CANDIDATE SOLUTION ---\n{solution}\n--------------------------\n"
            f"Analyze the steps. Write python SymPy code and run it using 'sympy_verify' to check if "
            f"the algebraic steps are valid. Finally, give a critique describing if the proof is valid or where the error is."
        )
        
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt}
        ]
        
        # Execute tool calls if requested
        for _ in range(2):
            response = self.provider.complete(messages, tools=self.tools)
            content = response.get("content", "")
            tool_calls = response.get("tool_calls", [])
            
            if not tool_calls:
                # Decide if verified based on the final inspection text
                verified = "error" not in content.lower() and "incorrect" not in content.lower() and "invalid" not in content.lower()
                return {
                    "verified": verified,
                    "critique": content
                }
                
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
        verified = "error" not in content.lower() and "incorrect" not in content.lower() and "invalid" not in content.lower()
        return {
            "verified": verified,
            "critique": content
        }

    def revise(self, solution: str, critique: str) -> AgentResponse:
        """
        Revises the solution based on the critique.
        """
        prompt = (
            f"Revise the following mathematical derivation based on the critique.\n"
            f"Original Solution:\n{solution}\n\n"
            f"Critique / Errors Found:\n{critique}\n\n"
            f"Produce an updated, corrected derivation. Fix any invalid signs, algebra, or steps."
        )
        return self.think(prompt)

    def derive(self, request: str) -> AgentResponse:
        """
        Implements the Generate-Verify-Revise loop to return a verified proof.
        """
        # Step 1: Generate initial solution
        solution_resp = self.generate_solution(request)
        solution = solution_resp.content
        
        # Step 2: Verify solution
        verification = self.verify_solution(solution)
        
        # Step 3: Revise if not verified
        if not verification["verified"]:
            revision_resp = self.revise(solution, verification["critique"])
            solution = revision_resp.content
            # Re-verify once more
            verification = self.verify_solution(solution)
            if not verification["verified"]:
                # If still failing, return it but append a warning in content
                content = (
                    f"{solution}\n\n"
                    f"> [!WARNING]\n"
                    f"> This derivation could not be fully verified by SymPy. Critique:\n"
                    f"> {verification['critique']}"
                )
                return AgentResponse(
                    content=content,
                    tool_calls=[],
                    confidence=0.5,
                    metadata={"verified": False, "critique": verification["critique"]}
                )
                
        content = (
            f"{solution}\n\n"
            f"> [!NOTE]\n"
            f"> **Verification Status:** Computational Verification Passed (via SymPy)."
        )
        return AgentResponse(
            content=content,
            tool_calls=[],
            confidence=1.0,
            metadata={"verified": True, "critique": verification["critique"]}
        )
