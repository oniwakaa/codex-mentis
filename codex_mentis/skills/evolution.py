import os
import sqlite3
import numpy as np
from datetime import datetime
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple
from sqlite_utils import Database
from codex_mentis.skills.engine import Skill

@dataclass
class Stats:
    success_rate: float
    avg_confidence: float
    use_count: int
    success_count: int = 0

class SkillEvolution:
    def __init__(self, db_path: str = "skills_evolution.db"):
        self.db_path = os.path.expanduser(db_path)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        db = Database(self.db_path)
        
        # Table: skill_usage
        if not db["skill_usage"].exists():
            db["skill_usage"].create({
                "id": int,
                "skill_name": str,
                "topic": str,
                "success": int, # 0 or 1
                "confidence": float,
                "feedback": str,
                "variant": str, # for A/B testing, default to 'A'
                "timestamp": str
            }, pk="id", defaults={"timestamp": "CURRENT_TIMESTAMP"})
            db["skill_usage"].create_index(["skill_name"])
            db["skill_usage"].create_index(["topic"])
            
        # Table: skill_prompts
        if not db["skill_prompts"].exists():
            db["skill_prompts"].create({
                "id": int,
                "skill_name": str,
                "prompt_template": str,
                "version": int,
                "timestamp": str
            }, pk="id", defaults={"timestamp": "CURRENT_TIMESTAMP"})

    def record_use(
        self, 
        skill_name: str, 
        success: bool, 
        feedback: str, 
        confidence: float = 1.0, 
        topic: str = "General",
        variant: str = "A"
    ) -> None:
        """Records a single usage instance of a skill with feedback, topic, and A/B test variant."""
        db = Database(self.db_path)
        db["skill_usage"].insert({
            "skill_name": skill_name,
            "topic": topic,
            "success": 1 if success else 0,
            "confidence": confidence,
            "feedback": feedback,
            "variant": variant
        })

    def get_stats(self, skill_name: str) -> Stats:
        """Calculates success rate, average confidence, and usage counts for a skill."""
        db = Database(self.db_path)
        try:
            rows = list(db["skill_usage"].rows_where("skill_name = ?", [skill_name]))
        except Exception:
            rows = []
            
        if not rows:
            return Stats(success_rate=0.0, avg_confidence=0.0, use_count=0, success_count=0)

        use_count = len(rows)
        successes = sum(1 for row in rows if row["success"])
        success_rate = successes / use_count
        avg_confidence = sum(row["confidence"] for row in rows) / use_count

        return Stats(
            success_rate=success_rate,
            avg_confidence=avg_confidence,
            use_count=use_count,
            success_count=successes
        )

    # --- Thompson Sampling ---
    def select_skill_thompson(self, skill_names: List[str]) -> str:
        """
        Uses Thompson Sampling (Bayesian multi-armed bandit) to select the best
        skill name from a list of options based on their historical success.
        """
        if not skill_names:
            raise ValueError("No skill names provided for selection.")
            
        best_skill = None
        max_sample = -1.0
        
        for name in skill_names:
            stats = self.get_stats(name)
            successes = stats.success_count
            failures = stats.use_count - successes
            
            # Thompson draw from Beta distribution Beta(1 + successes, 1 + failures)
            sample = np.random.beta(1 + successes, 1 + failures)
            if sample > max_sample:
                max_sample = sample
                best_skill = name
                
        return best_skill or skill_names[0]

    # --- A/B Testing Framework ---
    def select_prompt_variant(self, skill_name: str, variants: Dict[str, str]) -> Tuple[str, str]:
        """
        Performs Thompson Sampling over multiple prompt variant keys (e.g. {'A': template_A, 'B': template_B})
        to choose the most effective template.
        Returns (variant_key, prompt_template).
        """
        db = Database(self.db_path)
        best_variant = None
        max_sample = -1.0
        
        for var_name, template in variants.items():
            try:
                rows = list(db["skill_usage"].rows_where("skill_name = ? AND variant = ?", [skill_name, var_name]))
            except Exception:
                rows = []
                
            successes = sum(1 for r in rows if r["success"])
            failures = len(rows) - successes
            
            # Thompson sample draw
            sample = np.random.beta(1 + successes, 1 + failures)
            if sample > max_sample:
                max_sample = sample
                best_variant = var_name
                
        chosen_variant = best_variant or list(variants.keys())[0]
        return chosen_variant, variants[chosen_variant]

    # --- Prompt Mutation and Testing ---
    def mutate_prompt(
        self, 
        skill_name: str, 
        base_template: str, 
        mutation_instruction: str = "Strictly verify mathematical equations",
        provider: Optional[Any] = None
    ) -> str:
        """
        Mutates a prompt template using the LLM (or a structured fallback)
        and increments the version counter.
        """
        db = Database(self.db_path)
        
        # Get current version
        try:
            latest = list(db["skill_prompts"].rows_where("skill_name = ?", [skill_name], order_by="version DESC", limit=1))
            current_version = latest[0]["version"] if latest else 0
        except Exception:
            current_version = 0
            
        new_version = current_version + 1
        
        mutated_template = ""
        if provider:
            prompt = (
                f"You are a prompt engineer optimizing an AI agent's instructions for the skill '{skill_name}'.\n"
                f"Original Template:\n{base_template}\n\n"
                f"Improvement Instruction:\n{mutation_instruction}\n\n"
                f"Provide the complete, updated template. Do not add any explanatory text, output only the template."
            )
            try:
                resp = provider.complete([{"role": "user", "content": prompt}])
                mutated_template = resp.get("content", "")
            except Exception:
                pass
                
        if not mutated_template:
            # Fallback string mutation
            evolved_marker = "\n### Evolved Guidelines"
            clean_template = base_template
            if evolved_marker in clean_template:
                clean_template = clean_template.split(evolved_marker)[0]
                
            mutated_template = (
                f"{clean_template}\n"
                f"### Evolved Guidelines (V{new_version}):\n"
                f"- Adhere to: {mutation_instruction}\n"
            )
            
        db["skill_prompts"].insert({
            "skill_name": skill_name,
            "prompt_template": mutated_template,
            "version": new_version
        })
        
        return mutated_template

    def evolve_prompt(self, skill_name: str, base_template: str) -> str:
        """
        Evolves the prompt template by embedding lessons learned from failures and feedback.
        Required for backward compatibility in integration tests.
        """
        db = Database(self.db_path)
        
        # Retrieve all feedback for failed runs
        try:
            rows = list(db["skill_usage"].rows_where("skill_name = ? AND success = 0", [skill_name], order_by="timestamp DESC", limit=10))
            failed_feedbacks = [r["feedback"] for r in rows if r.get("feedback")]
        except Exception:
            failed_feedbacks = []
            
        # Get current version
        try:
            latest = list(db["skill_prompts"].rows_where("skill_name = ?", [skill_name], order_by="version DESC", limit=1))
            current_version = latest[0]["version"] if latest else 0
            current_template = latest[0]["prompt_template"] if latest else base_template
        except Exception:
            current_version = 0
            current_template = base_template
            
        if not failed_feedbacks:
            return current_template

        version = current_version + 1
        clean_template = current_template
        evolved_marker = "\n### Evolved Guidelines"
        if evolved_marker in clean_template:
            clean_template = clean_template.split(evolved_marker)[0]

        evolved_block = f"{evolved_marker} (V{version}):\n"
        evolved_block += "Based on learning from previous unsuccessful attempts, ensure you strictly adhere to the following:\n"
        for fb in failed_feedbacks:
            fb_clean = fb.replace("\n", " ").strip()
            evolved_block += f"- Avoid issue: {fb_clean}\n"

        evolved_template = clean_template + evolved_block

        db["skill_prompts"].insert({
            "skill_name": skill_name,
            "prompt_template": evolved_template,
            "version": version
        })

        return evolved_template

    # --- Automatic Skill Generation ---
    def generate_skill_from_interaction(
        self, 
        topic: str, 
        interaction_log: List[Dict[str, str]],
        provider: Optional[Any] = None
    ) -> Skill:
        """
        Generates a new Skill definition from a successful interaction log.
        """
        transcript = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in interaction_log])
        
        skill_name = "".join(x for x in topic.title() if not x.isspace()) + "Skill"
        
        if provider:
            prompt = (
                f"Based on the following successful chat interaction on '{topic}', extract a detailed, "
                f"YAML-compatible skill representation. Return details under these JSON keys:\n"
                f"- description: brief skill description\n"
                f"- concepts: list of concepts covered\n"
                f"- common_mistakes: list of mistakes to avoid\n"
                f"- analogies: list of analogies helpful to explain this\n"
                f"- verification_strategies: list of ways to mathematically double-check results\n\n"
                f"Transcript:\n{transcript}\n\n"
                f"Output only the JSON block."
            )
            try:
                import json
                resp = provider.complete([{"role": "user", "content": prompt}])
                content = resp.get("content", "")
                # Parse JSON
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0]
                data = json.loads(content.strip())
                return Skill(
                    name=skill_name,
                    domain=topic,
                    description=data.get("description", f"Extracted skill for {topic}"),
                    concepts=data.get("concepts", []),
                    common_mistakes=data.get("common_mistakes", []),
                    analogies=data.get("analogies", []),
                    verification_strategies=data.get("verification_strategies", [])
                )
            except Exception:
                pass
                
        # Fallback simple extraction
        import re
        # Find some latex formulas
        formulas = re.findall(r"\$\$(.*?)\$\$", transcript)
        formulas = [f.strip() for f in formulas if len(f.strip()) < 50]
        
        return Skill(
            name=skill_name,
            domain=topic,
            description=f"Automatically generated skill for {topic} based on interaction.",
            concepts=[topic],
            common_mistakes=["Computational oversight or arithmetic error"],
            analogies=[f"Think of {topic} like a system of balancing equations."],
            verification_strategies=[f"Verify with formula: {f}" for f in formulas[:2]] if formulas else ["Verify using dimensional consistency"]
        )

    # --- Performance Dashboard ---
    def get_performance_dashboard(self) -> Dict[str, Any]:
        """
        Compiles performance metrics across all skills and topics.
        """
        db = Database(self.db_path)
        try:
            runs = list(db["skill_usage"].rows)
        except Exception:
            runs = []
            
        if not runs:
            return {
                "total_usage_count": 0,
                "overall_success_rate": 0.0,
                "skills": {},
                "topics": {}
            }
            
        total_runs = len(runs)
        overall_successes = sum(1 for r in runs if r["success"])
        overall_success_rate = overall_successes / total_runs
        
        skills_metrics = {}
        topics_metrics = {}
        
        for run in runs:
            s_name = run["skill_name"]
            topic = run["topic"] or "General"
            success = run["success"]
            conf = run["confidence"]
            
            # Skill aggregation
            if s_name not in skills_metrics:
                skills_metrics[s_name] = {"successes": 0, "runs": 0, "confidences": []}
            skills_metrics[s_name]["runs"] += 1
            if success:
                skills_metrics[s_name]["successes"] += 1
            skills_metrics[s_name]["confidences"].append(conf)
            
            # Topic aggregation
            if topic not in topics_metrics:
                topics_metrics[topic] = {"successes": 0, "runs": 0}
            topics_metrics[topic]["runs"] += 1
            if success:
                topics_metrics[topic]["successes"] += 1
                
        # Format results
        skills_dashboard = {}
        for s_name, data in skills_metrics.items():
            skills_dashboard[s_name] = {
                "runs": data["runs"],
                "success_rate": data["successes"] / data["runs"],
                "avg_confidence": sum(data["confidences"]) / data["runs"]
            }
            
        topics_dashboard = {}
        for t_name, data in topics_metrics.items():
            topics_dashboard[t_name] = {
                "runs": data["runs"],
                "success_rate": data["successes"] / data["runs"]
            }
            
        return {
            "total_usage_count": total_runs,
            "overall_success_rate": overall_success_rate,
            "skills": skills_dashboard,
            "topics": topics_dashboard
        }
