import asyncio
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable

from pitagora.agents.base import BaseAgent, AgentResponse

logger = logging.getLogger(__name__)

@dataclass
class OrchestratorResponse:
    content: str
    agent_responses: List[AgentResponse] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

class Orchestrator:
    def __init__(
        self,
        agents: Dict[str, BaseAgent],
        memory: Optional[Any] = None,
        concept_graph: Optional[Any] = None,
        self_improver: Optional[Any] = None,
    ):
        """
        Orchestrates Pitagora tasks by routing requests to specialized agents
        and running multi-step collaborative workflows.

        `self_improver` (optional) enables the WS1 feedback loop: when present,
        tutor dispatch picks a strategy via `select_strategy_for` and records
        the interaction outcome via `record_interaction`.
        """
        self.agents = agents
        self.memory = memory
        self.concept_graph = concept_graph
        self.self_improver = self_improver
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.workflow_registry: Dict[str, Callable] = {}

        self._register_default_workflows()

    def register_workflow(self, name: str, workflow_fn: Callable) -> None:
        """
        Registers a new custom workflow.
        """
        self.workflow_registry[name] = workflow_fn

    def _register_default_workflows(self) -> None:
        self.register_workflow("parallel_tutor_prover", self._run_parallel_tutor_prover)
        self.register_workflow("research_prove_review_visualize", self._run_pipeline_workflow)
        self.register_workflow("prover_reviewer_debate", self._run_debate_workflow)
        self.register_workflow("derive_verify_plot", self._run_derive_verify_plot_workflow)

    def get_session(self, session_id: str) -> Dict[str, Any]:
        """
        Retrieves or initializes a session state.
        """
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "history": [],
                "metadata": {}
            }
        return self.sessions[session_id]

    async def classify_intent(self, user_input: str) -> Dict[str, Any]:
        """
        Classify user intent into one of our workflows or single-agent routes.
        Returns a dict: {"route_type": "workflow" | "agent", "name": str}
        """
        input_lower = user_input.lower()
        
        # Rule-based fast checks
        if "debate" in input_lower or ("vs" in input_lower and ("prover" in input_lower or "reviewer" in input_lower)):
            return {"route_type": "workflow", "name": "prover_reviewer_debate"}
        if "pipeline" in input_lower or ("research" in input_lower and "prove" in input_lower and "visualize" in input_lower):
            return {"route_type": "workflow", "name": "research_prove_review_visualize"}
        if "parallel" in input_lower or ("tutor" in input_lower and "prover" in input_lower and "simultaneous" in input_lower):
            return {"route_type": "workflow", "name": "parallel_tutor_prover"}
        if "multi" in input_lower or "derive_verify_plot" in input_lower:
            return {"route_type": "workflow", "name": "derive_verify_plot"}

        # Single agent triggers
        if "explain" in input_lower or "feynman" in input_lower or "analogy" in input_lower or "simple" in input_lower:
            return {"route_type": "agent", "name": "explainer"}
        if "study" in input_lower or "teach" in input_lower or "socratic" in input_lower:
            return {"route_type": "agent", "name": "tutor"}
        if "prove" in input_lower or "derive" in input_lower or "formula" in input_lower or "math" in input_lower:
            return {"route_type": "agent", "name": "prover"}
        if "verify" in input_lower or "review" in input_lower or "critique" in input_lower:
            return {"route_type": "agent", "name": "reviewer"}
        if "plot" in input_lower or "graph" in input_lower or "visualize" in input_lower:
            return {"route_type": "agent", "name": "visualizer"}
        if "research" in input_lower or "search" in input_lower or "web" in input_lower:
            return {"route_type": "agent", "name": "researcher"}
        if "self_improve" in input_lower or "optimize prompt" in input_lower:
            return {"route_type": "agent", "name": "self_improver"}
        if "dataset" in input_lower or "dataframe" in input_lower or "csv" in input_lower or "regression" in input_lower or "correlation" in input_lower:
            return {"route_type": "agent", "name": "data_analyst"}

        # Dynamic classifier utilizing LLM if possible
        agent = self.agents.get("researcher") or self.agents.get("tutor") or list(self.agents.values())[0] if self.agents else None
        if agent:
            prompt = (
                f"Classify the intent of the following user request into one of these exact options:\n"
                f"Workflows:\n"
                f"- 'parallel_tutor_prover' (side-by-side conceptual explanation + mathematical proof)\n"
                f"- 'research_prove_review_visualize' (research -> prove -> review -> plot sequence)\n"
                f"- 'prover_reviewer_debate' (proof critique & revision debate)\n"
                f"- 'derive_verify_plot' (derivation -> verification -> plot sequence)\n"
                f"Agents:\n"
                f"- 'explainer' (simple explanations, Feynman technique, analogies)\n"
                f"- 'tutor' (Socratic tutoring, practice exercises)\n"
                f"- 'prover' (rigorous math derivation / proof)\n"
                f"- 'reviewer' (formal mathematical auditing)\n"
                f"- 'visualizer' (rendering ASCII plots)\n"
                f"- 'researcher' (knowledge lookup, web search)\n"
                f"- 'self_improver' (prompt optimization, A/B strategy outcomes)\n"
                f"- 'data_analyst' (dataset profiling, statistical analysis, plots)\n\n"
                f"User request: \"{user_input}\"\n\n"
                f"Return a JSON response conforming strictly to: {{\"route_type\": \"workflow\" or \"agent\", \"name\": \"option_name\"}}"
            )
            try:
                from pydantic import BaseModel
                class IntentClassification(BaseModel):
                    route_type: str
                    name: str
                
                result = await agent.athink_structured(prompt, IntentClassification)
                return {"route_type": result.route_type, "name": result.name}
            except Exception:
                pass
                
        return {"route_type": "agent", "name": "researcher"}

    def process(
        self,
        user_input: str,
        mode: str = "explore",
        context: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> OrchestratorResponse:
        """
        Synchronous wrapper for aprocess. Python 3.12-safe: avoids the
        deprecated asyncio.get_event_loop() which warns when no loop exists.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop is None:
            return asyncio.run(self.aprocess(user_input, mode, context, session_id))
        # We're already inside a running loop — nest_asyncio lets us re-enter.
        import nest_asyncio
        nest_asyncio.apply()
        return loop.run_until_complete(self.aprocess(user_input, mode, context, session_id))

    async def aprocess(
        self, 
        user_input: str, 
        mode: str = "explore", 
        context: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> OrchestratorResponse:
        """
        Route user input based on the classified intent and execute workflows asynchronously.
        """
        # Memory lookup
        if self.memory and not context:
            try:
                context = self.memory.get_context(user_input)
            except Exception:
                pass

        # Session tracking
        session = None
        if session_id:
            session = self.get_session(session_id)
            session["history"].append({"role": "user", "content": user_input})

        # Check if mode specifies manual routing override
        route_type = None
        route_name = None
        
        mode_clean = mode.lower().strip()
        if mode_clean in self.workflow_registry:
            route_type = "workflow"
            route_name = mode_clean
        elif mode_clean in self.agents:
            route_type = "agent"
            route_name = mode_clean
        elif mode_clean in ("multi", "multi-step", "derive_verify_plot"):
            route_type = "workflow"
            route_name = "derive_verify_plot"
        elif mode_clean in ("study", "tutor"):
            route_type = "agent"
            route_name = "tutor"
        elif mode_clean in ("explore", "research", "researcher"):
            route_type = "agent"
            route_name = "researcher"
        elif mode_clean in ("derive", "reason", "prover"):
            route_type = "agent"
            route_name = "prover"
        elif mode_clean in ("verify", "review", "reviewer"):
            route_type = "agent"
            route_name = "reviewer"
        elif mode_clean in ("plot", "visualize", "visualizer"):
            route_type = "agent"
            route_name = "visualizer"
        elif mode_clean in ("explain", "explainer"):
            route_type = "agent"
            route_name = "explainer"
        elif mode_clean in ("self_improve", "self_improver"):
            route_type = "agent"
            route_name = "self_improver"
        elif mode_clean in ("data", "data_analyst", "analyze"):
            route_type = "agent"
            route_name = "data_analyst"
            
        if not route_type or mode_clean == "explore":
            # Classify intent dynamically
            intent = await self.classify_intent(user_input)
            route_type = intent["route_type"]
            route_name = intent["name"]

        response = None

        if route_type == "workflow":
            workflow_fn = self.workflow_registry.get(route_name)
            if workflow_fn:
                response = await workflow_fn(user_input, context)
            else:
                response = await self._run_pipeline_workflow(user_input, context)
        else:
            # Single agent route
            agent_key = route_name
            agent = self.agents.get(agent_key)
            if not agent:
                # Fallback to tutor or first available
                agent_key = "tutor" if "tutor" in self.agents else list(self.agents.keys())[0]
                agent = self.agents.get(agent_key)

            if not agent:
                return OrchestratorResponse(
                    content="Error: No active agents registered in the system.",
                    agent_responses=[]
                )

            agent_response = None
            
            # Execute specific agent methods if applicable, otherwise fallback to think
            if agent_key == "tutor" and hasattr(agent, "explain_concept"):
                # WS1: when a self_improver is wired in, pick a strategy from the
                # metrics DB before teaching and record the outcome after. The
                # strategy is injected as a pedagogical-style hint in the prompt.
                if self.self_improver is not None:
                    level = "beginner"
                    try:
                        strategy = self.self_improver.select_strategy_for(user_input, level)
                    except Exception:
                        strategy = None
                    if strategy:
                        prompt = (
                            f"Explain '{user_input}' to a {level} student using a "
                            f"{strategy} teaching style. Provide a Socratic "
                            f"introduction, clear explanations with analogies, and "
                            f"end with a guiding question."
                        )
                        agent_response = await agent.athink(prompt)
                    else:
                        agent_response = await agent.explain_concept(user_input)
                    # The orchestrator one-shot tutor path has no learner reply
                    # to classify, so quality is a content-derived self-assessment:
                    # the self-improver rates its own explanation 1-5 via the LLM.
                    # The chat REPL teaching path (_run_teaching_turn) remains the
                    # source of real learner-derived quality; this is a heuristic
                    # fallback for the standalone orchestrate() path.
                    try:
                        quality = await self.self_improver.rate_explanation(
                            topic=user_input, level=level,
                            strategy=strategy or "socratic",
                            explanation=agent_response.content,
                        )
                    except Exception:
                        quality = 3
                    try:
                        self.self_improver.record_interaction(
                            topic=user_input,
                            level=level,
                            strategy_used=strategy or "socratic",
                            response_quality=quality,
                        )
                    except Exception:
                        pass
                else:
                    agent_response = await agent.explain_concept(user_input)
            elif agent_key == "explainer" and hasattr(agent, "feynman_explanation"):
                if "feynman" in user_input.lower():
                    agent_response = await agent.feynman_explanation(user_input)
                elif "analogy" in user_input.lower():
                    # extract domain
                    domain = "everyday life"
                    for d in ["cooking", "traffic", "oceans", "sports", "gardening"]:
                        if d in user_input.lower():
                            domain = d
                            break
                    # Extract the concept from the user input (strip the analogy request phrase)
                    concept = re.sub(r"^(give me an |an )?analogy for\s+", "", user_input, flags=re.IGNORECASE)
                    concept = re.sub(r"\s+using\s+.*$", "", concept).strip() or user_input
                    res_str = await agent.tool_analogy_generator(concept, domain=domain)
                    agent_response = AgentResponse(content=res_str, metadata={"analogy": True})
                else:
                    agent_response = await agent.explain_level(user_input, level="Beginner")
            elif agent_key == "prover" and hasattr(agent, "derive"):
                agent_response = await agent.derive(user_input)
            elif agent_key == "reviewer" and hasattr(agent, "review"):
                agent_response = await agent.review(user_input)
            elif agent_key == "visualizer" and hasattr(agent, "plot_expression"):
                # Try to extract expression
                expr_match = re.search(r"plot\s+([a-zA-Z0-9\s\+\-\*\/\(\)\^]+)", user_input, re.IGNORECASE)
                if expr_match:
                    expr = expr_match.group(1).strip()
                    res_str = await asyncio.to_thread(agent.plot_expression, expr)
                    agent_response = AgentResponse(content=res_str, metadata={"expr": expr})
                else:
                    agent_response = await agent.athink(user_input, context)
            else:
                agent_response = await agent.athink(user_input, context)

            response = OrchestratorResponse(
                content=agent_response.content,
                agent_responses=[agent_response],
                metadata={"routed_agent": agent_key}
            )

        # Log assistant response to memory / session
        if self.memory and response:
            try:
                self.memory.add_message({"role": "user", "content": user_input})
                self.memory.add_message({"role": "assistant", "content": response.content})
            except Exception:
                pass

        if session and response:
            session["history"].append({"role": "assistant", "content": response.content})

        return response

    async def _run_parallel_tutor_prover(self, user_input: str, context: Optional[str]) -> OrchestratorResponse:
        """
        Runs Tutor and Prover agents simultaneously and merges their output into a side-by-side conceptual vs formal display.
        """
        tutor = self.agents.get("tutor")
        prover = self.agents.get("prover")
        
        if not tutor or not prover:
            return OrchestratorResponse(
                content="Error: Both Tutor and Prover agents must be active to run parallel reasoning.",
                agent_responses=[]
            )

        # Query concurrently
        tutor_task = tutor.athink(
            f"Provide Socratic guiding principles and physical intuition for: '{user_input}'",
            context
        )
        prover_task = prover.athink(
            f"Provide a rigorous mathematical proof or algebraic derivation for: '{user_input}'",
            context
        )
        
        tutor_resp, prover_resp = await asyncio.gather(tutor_task, prover_task)
        
        # Merge response side-by-side or cleanly separated
        merged_content = (
            f"### Conceptual & Intuitive Breakdown (Tutor)\n{tutor_resp.content}\n\n"
            f"### Rigorous Mathematical Derivation (Prover)\n{prover_resp.content}"
        )
        
        return OrchestratorResponse(
            content=merged_content,
            agent_responses=[tutor_resp, prover_resp],
            metadata={"workflow": "parallel_tutor_prover"}
        )

    async def _run_pipeline_workflow(self, user_input: str, context: Optional[str]) -> OrchestratorResponse:
        """
        Executes a Research -> Prove -> Review -> Visualize pipeline sequentially.
        """
        researcher = self.agents.get("researcher")
        prover = self.agents.get("prover")
        reviewer = self.agents.get("reviewer")
        visualizer = self.agents.get("visualizer")
        
        agent_responses = []
        pipeline_log = []

        # Step 1: Research
        research_content = "No researcher active."
        if researcher:
            res_resp = await researcher.athink(f"Synthesize relevant equations and academic context for: '{user_input}'", context)
            agent_responses.append(res_resp)
            research_content = res_resp.content
            pipeline_log.append("### 1. Research Background & Equations\n" + research_content)

        # Step 2: Prove
        prove_content = "No prover active."
        if prover:
            prove_prompt = (
                f"Based on the following research equations/context, perform a step-by-step derivation or proof for the request '{user_input}':\n\n"
                f"{research_content}"
            )
            prov_resp = await prover.athink(prove_prompt, context)
            agent_responses.append(prov_resp)
            prove_content = prov_resp.content
            pipeline_log.append("### 2. Derived Proof & Calculus\n" + prove_content)

        # Step 3: Review
        review_content = "No reviewer active."
        if reviewer:
            rev_prompt = (
                f"Critique and perform adversarial mathematical verification on this proof:\n\n"
                f"{prove_content}"
            )
            rev_resp = await reviewer.athink(rev_prompt, context)
            agent_responses.append(rev_resp)
            review_content = rev_resp.content
            pipeline_log.append("### 3. Mathematical Audit & Critique\n" + review_content)

        # Step 4: Visualize
        plot_content = ""
        if visualizer:
            # Attempt to extract equation for plotting
            equations = re.findall(r"\$\$(.*?)\$\$", prove_content)
            if not equations:
                equations = re.findall(r"\$(.*?)\$", prove_content)
                
            plot_expr = None
            for eq in equations:
                if "=" in eq and "x" in eq:
                    parts = eq.split("=")
                    clean_rhs = parts[1].replace("\\sin", "sin").replace("\\cos", "cos").replace("\\exp", "exp").strip()
                    plot_expr = clean_rhs
                    break
            
            if not plot_expr:
                # Default
                plot_expr = "x**2"
                
            try:
                # Call visualizer plotter
                plot_content = visualizer.plot_expression(plot_expr)
                vis_resp = AgentResponse(content=plot_content, metadata={"plotted_expr": plot_expr})
                agent_responses.append(vis_resp)
                pipeline_log.append("### 4. ASCII Functional Plot\n```\n" + plot_content + "\n```")
            except Exception:
                pass

        final_content = "\n\n".join(pipeline_log)
        return OrchestratorResponse(
            content=final_content,
            agent_responses=agent_responses,
            metadata={"workflow": "research_prove_review_visualize"}
        )

    async def _run_debate_workflow(self, user_input: str, context: Optional[str]) -> OrchestratorResponse:
        """
        Executes an iterative debate between the Prover (creates/revises proof) and Reviewer (critiques proof).
        Loops up to 3 rounds or until Reviewer approves.
        """
        prover = self.agents.get("prover")
        reviewer = self.agents.get("reviewer")
        
        if not prover or not reviewer:
            return OrchestratorResponse(
                content="Error: Both Prover and Reviewer agents are required for debate workflow.",
                agent_responses=[]
            )

        agent_responses = []
        debate_history = []

        # Round 1: Generate initial proof
        current_proof = await prover.athink(f"Propose a proof/derivation for: '{user_input}'", context)
        agent_responses.append(current_proof)
        debate_history.append(f"#### Round 1: Prover's Initial Derivation\n{current_proof.content}")

        max_rounds = 3
        rounds_completed = 0
        for round_idx in range(1, max_rounds + 1):
            rounds_completed = round_idx
            # Reviewer critiques
            critique = await reviewer.athink(
                f"Critically audit this math/physics proof. Check for signs, steps, dimensions, and notation errors. "
                f"If correct, state 'NO ERRORS DETECTED'. Proof:\n\n{current_proof.content}",
                context
            )
            agent_responses.append(critique)
            debate_history.append(f"#### Round {round_idx}: Reviewer's Audit/Critique\n{critique.content}")
            
            # Check exit condition
            if "no errors detected" in critique.content.lower():
                debate_history.append(f"**Verification complete.** Reviewer signed off on the proof in Round {round_idx}.")
                break
                
            # Prover revises
            if round_idx < max_rounds:
                revised_proof = await prover.athink(
                    f"Revise your derivation based on this critique:\n\n{critique.content}\n\n"
                    f"Address each point and output the complete revised mathematical proof.",
                    context
                )
                agent_responses.append(revised_proof)
                current_proof = revised_proof
                debate_history.append(f"#### Round {round_idx+1}: Prover's Revised Derivation\n{current_proof.content}")

        final_content = (
            f"### Multi-Agent Debate Workflow (Prover vs Reviewer)\n\n" +
            "\n\n---\n\n".join(debate_history)
        )
        
        return OrchestratorResponse(
            content=final_content,
            agent_responses=agent_responses,
            metadata={"workflow": "prover_reviewer_debate", "rounds": rounds_completed}
        )

    async def _run_derive_verify_plot_workflow(self, user_input: str, context: Optional[str]) -> OrchestratorResponse:
        """
        Runs derive -> verify -> plot pipeline.
        1. Prover derives the equation/proof.
        2. Reviewer checks it adversarially.
        3. Visualizer plots the resulting function.
        """
        agent_responses = []
        
        # Step 1: Derive
        prover = self.agents.get("prover")
        if not prover:
            return OrchestratorResponse(content="Error: Prover agent missing for multi-step workflow.", agent_responses=[])
            
        prover_resp = await prover.athink(user_input, context)
        agent_responses.append(prover_resp)
        
        # Step 2: Verify
        reviewer = self.agents.get("reviewer")
        review_text = "Reviewer agent not available."
        if reviewer:
            reviewer_resp = await reviewer.athink(f"Review the correctness of the following math:\n\n{prover_resp.content}", context)
            agent_responses.append(reviewer_resp)
            review_text = reviewer_resp.content

        # Step 3: Visualize (Extract math expression and plot it)
        visualizer = self.agents.get("visualizer")
        plot_text = ""
        if visualizer:
            equations = re.findall(r"\$\$(.*?)\$\$", prover_resp.content)
            if not equations:
                equations = re.findall(r"\$(.*?)\$", prover_resp.content)
                
            plot_expr = None
            for eq in equations:
                if "=" in eq and "x" in eq:
                    parts = eq.split("=")
                    clean_rhs = parts[1].replace("\\sin", "sin").replace("\\cos", "cos").replace("\\exp", "exp").strip()
                    plot_expr = clean_rhs
                    break
                    
            if not plot_expr:
                plot_expr = "x**2"
                
            try:
                plot_text = visualizer.plot_expression(plot_expr)
                agent_responses.append(AgentResponse(content=plot_text, metadata={"plotted_expr": plot_expr}))
            except Exception:
                pass

        summary_content = (
            f"### 1. Mathematical Derivation\n{prover_resp.content}\n\n"
            f"### 2. Adversarial Review Verdict\n{review_text}\n\n"
            f"### 3. Visual Representation\n```\n{plot_text}\n```"
        )

        return OrchestratorResponse(
            content=summary_content,
            agent_responses=agent_responses,
            metadata={"workflow": "derive_verify_plot"}
        )

def orchestrate(query: str, mode: str, topic: str, context: str = "") -> str:
    """
    Stand-alone orchestrate function for REPL compatibility.
    Runs the agent reasoning chain in a synchronous wrapper.
    """
    from pitagora.agents.providers import ProviderConfig, get_provider
    from pitagora.agents.tutor import TutorAgent
    from pitagora.agents.researcher import ResearchAgent
    from pitagora.agents.prover import ProverAgent
    from pitagora.agents.reviewer import ReviewerAgent
    from pitagora.agents.visualizer import VisualizerAgent
    from pitagora.agents.explainer import ExplainerAgent
    from pitagora.agents.self_improver import SelfImproverAgent
    from pitagora.agents.data_analyst import DataAnalystAgent
    
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY") or os.getenv("PITAGORA_API_KEY") or "mock"

    # Resolve provider config from pitagora config or defaults
    default_provider_name = "gemini"
    default_model = os.getenv("PITAGORA_MODEL", "google/gemini-3.6-flash-high")
    base_url = os.getenv("PITAGORA_BASE_URL", "http://localhost:8317/v1")

    try:
        from pitagora.core.config import load_config
        config_obj = load_config()
        default_provider_name = config_obj.providers.default
        # Read nested provider config if available
        prov_config = config_obj.providers.config if hasattr(config_obj.providers, 'config') else {}
        if prov_config:
            default_model = prov_config.get("default_model", default_model)
            base_url = prov_config.get("base_url", base_url)
            api_key = prov_config.get("api_key", api_key)
        if config_obj.model:
            default_model = config_obj.model
    except Exception:
        pass

    config = ProviderConfig(
        api_key=api_key,
        model=default_model,
        base_url=base_url,
        max_tokens=4096
    )
    
    prov = get_provider(default_provider_name, config)
    
    agents = {
        "tutor": TutorAgent(prov),
        "researcher": ResearchAgent(prov),
        "prover": ProverAgent(prov),
        "reviewer": ReviewerAgent(prov),
        "visualizer": VisualizerAgent(prov),
        "explainer": ExplainerAgent(prov),
        "self_improver": SelfImproverAgent(prov),
        "data_analyst": DataAnalystAgent(prov)
    }
    
    orchestrator = Orchestrator(agents=agents)
    
    resp = orchestrator.process(
        user_input=query,
        mode=mode,
        context=f"Topic: {topic}\n{context}".strip()
    )
    return resp.content
