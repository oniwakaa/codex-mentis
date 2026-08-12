import asyncio
import logging
import os
import yaml
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Union

from codex_mentis.agents.base import BaseAgent, AgentResponse

logger = logging.getLogger(__name__)

@dataclass
class WorkflowStep:
    name: str
    agent: str
    prompt_template: str
    inputs_from: List[str] = field(default_factory=list)
    tools: Optional[List[str]] = None
    retry_count: int = 3

@dataclass
class WorkflowDefinition:
    name: str
    description: str
    steps: List[WorkflowStep]
    parallel_groups: List[List[str]] = field(default_factory=field)
    merge_strategy: str = "concat"

class WorkflowEngine:
    def __init__(
        self, 
        agents: Dict[str, BaseAgent], 
        memory: Optional[Any] = None, 
        concept_graph: Optional[Any] = None
    ):
        self.agents = agents
        self.memory = memory
        self.concept_graph = concept_graph
        self.workflow: Optional[WorkflowDefinition] = None

    def load_workflow(self, yaml_path: str) -> WorkflowDefinition:
        """
        Loads a workflow definition from a YAML file.
        """
        with open(yaml_path, 'r') as f:
            data = yaml.safe_load(f)

        steps = []
        for s in data.get("steps", []):
            steps.append(WorkflowStep(
                name=s["name"],
                agent=s["agent"],
                prompt_template=s["prompt_template"],
                inputs_from=s.get("inputs_from", []),
                tools=s.get("tools"),
                retry_count=s.get("retry_count", 3)
            ))

        self.workflow = WorkflowDefinition(
            name=data["name"],
            description=data.get("description", ""),
            steps=steps,
            parallel_groups=data.get("parallel_groups", []),
            merge_strategy=data.get("merge_strategy", "concat")
        )
        return self.workflow

    async def execute(
        self, 
        inputs: Dict[str, Any], 
        workflow_name_or_def: Optional[Union[str, WorkflowDefinition]] = None
    ) -> Dict[str, Any]:
        """
        Executes a workflow definition using parallel execution via asyncio.gather and step chaining.
        """
        if workflow_name_or_def is None:
            if self.workflow is None:
                raise ValueError("No workflow loaded. Please load a workflow first or specify the workflow name/definition.")
            w_def = self.workflow
        elif isinstance(workflow_name_or_def, str):
            # Resolve path
            base_dir = os.path.dirname(os.path.dirname(__file__))
            yaml_path = os.path.join(base_dir, "data", "workflows", f"{workflow_name_or_def}.yaml")
            w_def = self.load_workflow(yaml_path)
        else:
            w_def = workflow_name_or_def
            self.workflow = w_def

        # A map of step name -> Future which will resolve with the step output content
        step_futures: Dict[str, asyncio.Future] = {step.name: asyncio.Future() for step in w_def.steps}
        step_outputs: Dict[str, str] = {}
        agent_responses: List[AgentResponse] = []

        async def run_step(step: WorkflowStep) -> str:
            try:
                # 1. Await dependency outputs
                dep_results = {}
                for dep_name in step.inputs_from:
                    if dep_name not in step_futures:
                        raise ValueError(f"Step '{step.name}' depends on non-existent step '{dep_name}'")
                    dep_results[dep_name] = await step_futures[dep_name]

                # 2. Construct prompt by formatting template with inputs + dependency results
                fmt_args = {**inputs, **dep_results}
                prompt = step.prompt_template.format(**fmt_args)

                # 3. Resolve agent
                agent = self.agents.get(step.agent)
                if not agent:
                    raise ValueError(f"Agent '{step.agent}' not found for step '{step.name}'")

                # 4. Execute with retry logic
                last_err = None
                response_content = None
                for attempt in range(step.retry_count):
                    try:
                        logger.info(f"Executing step '{step.name}' using agent '{step.agent}' (Attempt {attempt+1}/{step.retry_count})")
                        response = await agent.athink(prompt)
                        agent_responses.append(response)
                        response_content = response.content
                        break
                    except Exception as e:
                        logger.warning(f"Step '{step.name}' attempt {attempt+1} failed: {e}")
                        last_err = e
                        await asyncio.sleep(0.5 * (attempt + 1))

                if response_content is None:
                    raise RuntimeError(f"Step '{step.name}' failed after {step.retry_count} attempts. Last error: {last_err}")

                step_outputs[step.name] = response_content
                step_futures[step.name].set_result(response_content)
                return response_content

            except Exception as e:
                # Set exception on our future to avoid blocking dependent steps, then re-raise
                if not step_futures[step.name].done():
                    step_futures[step.name].set_exception(e)
                raise e

        # Schedule all steps in parallel; steps will await their respective dependency futures
        tasks = [asyncio.create_task(run_step(step)) for step in w_def.steps]
        await asyncio.gather(*tasks)

        # Merge strategy to reconcile or concatenate results
        final_output = ""
        if w_def.merge_strategy == "concat":
            sections = []
            for step in w_def.steps:
                sections.append(f"### {step.name.replace('_', ' ').title()}\n{step_outputs[step.name]}")
            final_output = "\n\n".join(sections)
        elif w_def.merge_strategy == "synthesize":
            # Reconcile via an agent (default to tutor or explainer)
            synthesizer = self.agents.get("tutor") or self.agents.get("explainer") or list(self.agents.values())[0]
            synth_prompt = (
                f"Synthesize the outputs of the workflow steps into a final cohesive response.\n"
                f"Workflow Name: {w_def.name}\n"
                f"Description: {w_def.description}\n"
                f"Original Inputs: {inputs}\n\n"
                f"Step Outputs:\n"
            )
            for step in w_def.steps:
                synth_prompt += f"--- Step '{step.name}' ---\n{step_outputs[step.name]}\n\n"
            synth_prompt += "Produce a final master report synthesizing the outputs clearly and professionally."
            
            synth_response = await synthesizer.athink(synth_prompt)
            final_output = synth_response.content
        else:
            final_output = "\n\n".join(step_outputs.values())

        return {
            "workflow_name": w_def.name,
            "final_output": final_output,
            "step_outputs": step_outputs,
            "agent_responses": agent_responses
        }
