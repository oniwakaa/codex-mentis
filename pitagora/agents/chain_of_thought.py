import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple

from pitagora.agents.base import BaseAgent, AgentResponse

logger = logging.getLogger(__name__)

@dataclass
class ReasoningNode:
    step_id: str
    thought: str
    verified: bool
    critique: str
    parent: Optional['ReasoningNode'] = None
    children: List['ReasoningNode'] = field(default_factory=list)

class ReasoningChain:
    def __init__(
        self, 
        prover: BaseAgent, 
        reviewer: BaseAgent,
        max_depth: int = 5,
        max_branches: int = 2,
        max_revisions: int = 2
    ):
        self.prover = prover
        self.reviewer = reviewer
        self.max_depth = max_depth
        self.max_branches = max_branches
        self.max_revisions = max_revisions
        self.root: Optional[ReasoningNode] = None
        self.problem: str = ""

    async def solve(self, problem: str) -> Dict[str, Any]:
        """
        Solves a problem by searching for a verified sequence of reasoning steps
        using branching and backtracking.
        """
        self.problem = problem
        self.root = ReasoningNode(
            step_id="0",
            thought=f"Start: {problem}",
            verified=True,
            critique="",
            parent=None
        )
        
        success = await self._explore(self.root, current_depth=1)
        tree_visualization = self.render_tree()
        
        # Reconstruct successful path
        successful_path = []
        leaf = self._find_successful_leaf(self.root)
        curr = leaf
        while curr and curr.parent:
            successful_path.insert(0, curr.thought)
            curr = curr.parent
            
        final_solution = "\n\n".join(successful_path) if success else "Failed to find a verified derivation."
        
        return {
            "success": success,
            "solution": final_solution,
            "tree_visualization": tree_visualization,
            "root": self.root
        }

    async def _explore(self, parent_node: ReasoningNode, current_depth: int) -> bool:
        if current_depth > self.max_depth:
            return False

        # Get ancestral path for context
        path = []
        curr = parent_node
        while curr and curr.parent:
            path.insert(0, curr.thought)
            curr = curr.parent
        path_str = "\n".join(f"Step {i+1}: {step}" for i, step in enumerate(path))

        # Explore branches
        for branch_idx in range(self.max_branches):
            step_id = f"{parent_node.step_id}.{branch_idx + 1}" if parent_node.step_id != "0" else f"{branch_idx + 1}"
            branch_desc = " (alternative path)" if branch_idx > 0 else ""
            logger.info(f"Reasoning Chain: Generating step {step_id}{branch_desc}...")
            
            prompt = (
                f"Problem to solve: '{self.problem}'\n\n"
                f"Reasoning steps taken so far:\n{path_str or 'None (Starting)'}\n\n"
                f"Propose the NEXT logical step of derivation or reasoning. Be precise, concise, "
                f"and include any necessary mathematical formulas."
            )
            if branch_idx > 0:
                prompt += "\nProvide a COMPLETELY DIFFERENT reasoning path or approach than prior attempts."
            else:
                prompt += "\nIf this step concludes the entire proof, end your response with 'Q.E.D.'."

            resp = await self.prover.athink(prompt)
            thought = resp.content.strip()

            # Verify the step
            verified, critique = await self._verify_step(thought)
            
            node = ReasoningNode(
                step_id=step_id,
                thought=thought,
                verified=verified,
                critique=critique,
                parent=parent_node
            )
            parent_node.children.append(node)

            # Revision loop if verification fails
            revision_count = 0
            while not node.verified and revision_count < self.max_revisions:
                logger.info(f"Reasoning Chain: Step {step_id} failed verification. Revising (Attempt {revision_count+1}/{self.max_revisions})...")
                revise_prompt = (
                    f"Problem: '{self.problem}'\n"
                    f"Steps so far:\n{path_str or 'None'}\n\n"
                    f"You proposed this next step:\n{node.thought}\n\n"
                    f"However, verification failed with the following critique:\n{node.critique}\n\n"
                    f"Please revise this step to address the critique and output a corrected next step."
                )
                rev_resp = await self.prover.athink(revise_prompt)
                node.thought = rev_resp.content.strip()
                node.verified, node.critique = await self._verify_step(node.thought)
                revision_count += 1

            if node.verified:
                logger.info(f"Reasoning Chain: Step {step_id} verified successfully!")
                
                # Check for Q.E.D.
                if "q.e.d." in node.thought.lower() or "qed" in node.thought.lower() or current_depth == self.max_depth:
                    return True
                
                # Recurse
                success = await self._explore(node, current_depth + 1)
                if success:
                    return True
                else:
                    logger.info(f"Reasoning Chain: Path from step {step_id} did not lead to a solution. Backtracking...")
            else:
                logger.info(f"Reasoning Chain: Step {step_id} failed verification after revisions. Backtracking...")

        return False

    async def _verify_step(self, step_content: str) -> Tuple[bool, str]:
        """
        Verify correctness of a single reasoning step using the Reviewer agent.
        """
        prompt = (
            f"Critically audit this single reasoning/mathematical step. Check for algebraic correctness, sign errors, and logical flow.\n"
            f"Step to audit: \"{step_content}\"\n\n"
            f"If the step is fully correct, start your response with 'VERIFIED'. "
            f"If incorrect, explain the errors clearly."
        )
        resp = await self.reviewer.athink(prompt)
        content = resp.content.strip()
        verified = content.upper().startswith("VERIFIED")
        return verified, content

    def _find_successful_leaf(self, node: ReasoningNode) -> Optional[ReasoningNode]:
        # A successful leaf is a verified node that either has "qed" or has no verified children but is verified itself and is a leaf.
        # Since we use depth-first search and return on first success, the first leaf that is verified and leads to completion is the successful one.
        if not node.verified:
            return None
        
        # If it's a leaf node in the successful path
        if not node.children:
            return node
            
        for child in node.children:
            res = self._find_successful_leaf(child)
            if res:
                return res
        return node

    def render_tree(self) -> str:
        """
        Renders the reasoning search tree in ASCII format.
        """
        if not self.root:
            return "Empty Tree"
            
        lines = []
        
        def traverse(node: ReasoningNode, prefix: str = "", is_last: bool = True):
            if node.step_id == "0":
                lines.append(f"{node.thought}")
                new_prefix = ""
            else:
                connector = "└── " if is_last else "├── "
                status = "[VERIFIED]" if node.verified else "[FAILED]"
                
                # Trim thought to a single line for visualization
                first_line = node.thought.split("\n")[0].strip()
                trimmed_thought = first_line[:60]
                if len(first_line) > 60:
                    trimmed_thought += "..."
                    
                lines.append(f"{prefix}{connector}Step {node.step_id}: {trimmed_thought} {status}")
                new_prefix = prefix + ("    " if is_last else "│   ")
                
            for i, child in enumerate(node.children):
                traverse(child, new_prefix, i == len(node.children) - 1)
                
        traverse(self.root)
        return "\n".join(lines)
