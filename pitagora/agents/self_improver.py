import json
import logging
import sqlite3
import random
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from pitagora.agents.base import BaseAgent, AgentResponse
from pitagora.agents.providers.base import BaseProvider

logger = logging.getLogger(__name__)

SELF_IMPROVER_SYSTEM_PROMPT = """You are the Self-Improver Agent for Pitagora. Your role is to optimize system prompts and pedagogical strategies based on empirical success metrics.

You analyze user outcomes, evaluate A/B testing data, execute Thompson Sampling to balance exploration and exploitation of explanation strategies, and write evolved guidelines.
You also specialize in identifying successful explanation patterns and code-generating them into reusable skill definitions.
"""

class EvolvedPrompt(BaseModel):
    strategy_name: str = Field(description="The strategy that was evolved")
    new_prompt_template: str = Field(description="The full revised system prompt template")
    explanation_of_changes: str = Field(description="Why the prompt was updated and how it addresses the failure logs")

class GeneratedSkill(BaseModel):
    skill_name: str = Field(description="A clean identifier for the new skill (kebab-case)")
    description: str = Field(description="Purpose and target area of the skill")
    instructions: List[str] = Field(description="Step-by-step procedural guidelines for this skill")
    example_input: str = Field(description="An example input scenario")
    example_output: str = Field(description="An example successful response showing the pattern in action")

class SelfImproverAgent(BaseAgent):
    def __init__(self, provider: BaseProvider, db_path: str = ""):
        if not db_path:
            from pitagora.core.constants import DB_DIR
            db_path = str(DB_DIR / "self_improver.db")
        super().__init__(
            name="SelfImprover",
            role="Prompts & Strategy Evolution Optimizer",
            provider=provider,
            system_prompt=SELF_IMPROVER_SYSTEM_PROMPT
        )
        self.db_path = db_path
        self._init_db()

        # Register track_outcome
        self.register_tool(
            "track_outcome",
            {
                "name": "track_outcome",
                "description": "Record the outcome (success/failure) of an explanation strategy for reinforcement learning.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "prompt_id": {
                            "type": "string",
                            "description": "Identifier for the specific prompt version used."
                        },
                        "strategy_name": {
                            "type": "string",
                            "description": "The type of strategy used (e.g., Socratic, Feynman, Analogies)."
                        },
                        "success": {
                            "type": "boolean",
                            "description": "Whether the explanation successfully led to user understanding or correct answer."
                        },
                        "feedback": {
                            "type": "string",
                            "description": "Qualitative user feedback or error logs."
                        }
                    },
                    "required": ["prompt_id", "strategy_name", "success"]
                }
            },
            self.tool_track_outcome
        )

        # Register get_best_prompt
        self.register_tool(
            "get_best_prompt",
            {
                "name": "get_best_prompt",
                "description": "Retrieve the best performing prompt template for a specific strategy.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "strategy_name": {
                            "type": "string",
                            "description": "Name of the target strategy."
                        }
                    },
                    "required": ["strategy_name"]
                }
            },
            self.tool_get_best_prompt
        )

        # Register evolve_strategy
        self.register_tool(
            "evolve_strategy",
            {
                "name": "evolve_strategy",
                "description": "Evolve an explanation strategy system prompt based on its failure logs.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "strategy_name": {
                            "type": "string",
                            "description": "Name of the strategy to evolve."
                        },
                        "current_prompt": {
                            "type": "string",
                            "description": "The current system prompt template of the strategy."
                        }
                    },
                    "required": ["strategy_name", "current_prompt"]
                }
            },
            self.tool_evolve_strategy
        )

        # Register generate_skill
        self.register_tool(
            "generate_skill",
            {
                "name": "generate_skill",
                "description": "Generate a new reusable pedagogical skill definition from successful patterns.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pattern_name": {
                            "type": "string",
                            "description": "A clear name for the pattern (e.g., visual-calculus, socratic-physics)."
                        },
                        "successful_patterns_summary": {
                            "type": "string",
                            "description": "A summary of successful inputs/outputs that exhibit this pattern."
                        }
                    },
                    "required": ["pattern_name", "successful_patterns_summary"]
                }
            },
            self.tool_generate_skill
        )

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 1. Strategy Performance (Thompson Sampling parameters alpha, beta)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS strategy_performance (
                strategy_name TEXT PRIMARY KEY,
                alpha REAL DEFAULT 1.0,
                beta REAL DEFAULT 1.0
            )
        """)
        
        # 2. Prompts Performance
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS prompt_performance (
                prompt_id TEXT PRIMARY KEY,
                prompt_text TEXT,
                strategy_name TEXT,
                successes INTEGER DEFAULT 0,
                failures INTEGER DEFAULT 0
            )
        """)
        
        # 3. Outcomes log
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS outcomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prompt_id TEXT,
                strategy_name TEXT,
                success BOOLEAN,
                feedback TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 4. Evolved Skills
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS evolved_skills (
                skill_name TEXT PRIMARY KEY,
                description TEXT,
                instructions TEXT,
                example_input TEXT,
                example_output TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Seed default strategies if not exists
        default_strategies = ["socratic", "feynman", "analogy", "side_by_side", "formal_proof"]
        for strategy in default_strategies:
            cursor.execute(
                "INSERT OR IGNORE INTO strategy_performance (strategy_name, alpha, beta) VALUES (?, 1.0, 1.0)",
                (strategy,)
            )
            
        conn.commit()
        conn.close()

    def select_strategy(self, strategies: List[str]) -> str:
        """
        Uses Thompson Sampling to select the best explanation strategy.
        Samples from Beta(alpha, beta) for each strategy and chooses the max.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        selected_strategy = None
        max_sample = -1.0
        
        for strategy in strategies:
            cursor.execute(
                "SELECT alpha, beta FROM strategy_performance WHERE strategy_name = ?",
                (strategy,)
            )
            row = cursor.fetchone()
            if row:
                alpha, beta = row[0], row[1]
            else:
                alpha, beta = 1.0, 1.0
                # Insert dynamic strategy if missing
                cursor.execute(
                    "INSERT OR IGNORE INTO strategy_performance (strategy_name, alpha, beta) VALUES (?, 1.0, 1.0)",
                    (strategy,)
                )
                conn.commit()
                
            # Thompson sample
            sample = random.betavariate(alpha, beta)
            if sample > max_sample:
                max_sample = sample
                selected_strategy = strategy
                
        conn.close()
        
        # Fallback to random if something goes wrong
        return selected_strategy or random.choice(strategies)

    async def tool_track_outcome(self, prompt_id: str, strategy_name: str, success: bool, feedback: str = "") -> str:
        """
        Tracks a user interaction outcome, updating both strategy Beta parameters and prompt metrics.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            # 1. Log outcome
            cursor.execute(
                "INSERT INTO outcomes (prompt_id, strategy_name, success, feedback) VALUES (?, ?, ?, ?)",
                (prompt_id, strategy_name, 1 if success else 0, feedback)
            )
            
            # 2. Update strategy performance (Thompson Sampling parameters)
            cursor.execute(
                "SELECT alpha, beta FROM strategy_performance WHERE strategy_name = ?",
                (strategy_name,)
            )
            row = cursor.fetchone()
            if not row:
                cursor.execute(
                    "INSERT INTO strategy_performance (strategy_name, alpha, beta) VALUES (?, 1.0, 1.0)",
                    (strategy_name,)
                )
                alpha, beta = 1.0, 1.0
            else:
                alpha, beta = row[0], row[1]
                
            if success:
                # Add reward
                alpha += 1.0
            else:
                # Add penalty
                beta += 1.0
                
            cursor.execute(
                "UPDATE strategy_performance SET alpha = ?, beta = ? WHERE strategy_name = ?",
                (alpha, beta, strategy_name)
            )
            
            # 3. Update prompt statistics
            cursor.execute(
                "SELECT successes, failures FROM prompt_performance WHERE prompt_id = ?",
                (prompt_id,)
            )
            p_row = cursor.fetchone()
            if p_row:
                p_successes, p_failures = p_row[0], p_row[1]
                if success:
                    p_successes += 1
                else:
                    p_failures += 1
                cursor.execute(
                    "UPDATE prompt_performance SET successes = ?, failures = ? WHERE prompt_id = ?",
                    (p_successes, p_failures, prompt_id)
                )
            else:
                # Create a placeholder entry for prompt text, to be populated later or kept empty
                cursor.execute(
                    "INSERT INTO prompt_performance (prompt_id, prompt_text, strategy_name, successes, failures) VALUES (?, ?, ?, ?, ?)",
                    (prompt_id, "Unknown prompt template", strategy_name, 1 if success else 0, 0 if success else 1)
                )
                
            conn.commit()
            return json.dumps({
                "status": "success",
                "updated_strategy": strategy_name,
                "new_alpha": alpha,
                "new_beta": beta
            })
        except Exception as e:
            logger.error(f"Error tracking outcome: {e}")
            return json.dumps({"status": "error", "message": str(e)})
        finally:
            conn.close()

    async def tool_get_best_prompt(self, strategy_name: str) -> str:
        """
        Retrieves the prompt_id and text of the best performing prompt for a strategy.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT prompt_id, prompt_text, (successes * 1.0 / (successes + failures + 1)) as score
                FROM prompt_performance
                WHERE strategy_name = ?
                ORDER BY score DESC, (successes + failures) DESC
                LIMIT 1
            """, (strategy_name,))
            row = cursor.fetchone()
            if row:
                return json.dumps({
                    "prompt_id": row[0],
                    "prompt_text": row[1],
                    "estimated_score": row[2]
                })
            else:
                return json.dumps({
                    "prompt_id": f"{strategy_name}_default",
                    "prompt_text": "Use default agent system prompt.",
                    "estimated_score": 0.5
                })
        finally:
            conn.close()

    async def tool_evolve_strategy(self, strategy_name: str, current_prompt: str) -> str:
        """
        Examines recent feedback logs for the strategy, particularly failures, 
        and instructs the model to evolve the system prompt to avoid these issues.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Retrieve recent failure logs
        cursor.execute("""
            SELECT feedback FROM outcomes
            WHERE strategy_name = ? AND success = 0
            ORDER BY timestamp DESC
            LIMIT 5
        """, (strategy_name,))
        failures = [row[0] for row in cursor.fetchall() if row[0]]
        conn.close()
        
        prompt = (
            f"Evolve the system prompt for explanation strategy: '{strategy_name}'.\n\n"
            f"Current Prompt Template:\n"
            f"```\n{current_prompt}\n```\n\n"
        )
        if failures:
            prompt += "Here are the qualitative failure logs from recent attempts:\n"
            for idx, fail in enumerate(failures):
                prompt += f"- Log {idx+1}: {fail}\n"
            prompt += "\nIncorporate defensive constraints and refined guidelines to prevent these failures."
        else:
            prompt += "No failures recorded yet. Please optimize the prompt for maximum pedagogical clarity, engagement, and logical depth."
            
        try:
            evolved = await self.athink_structured(prompt, EvolvedPrompt)
            
            # Save the new evolved prompt template in database
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                new_prompt_id = f"{strategy_name}_v{random.randint(1000, 9999)}"
                cursor.execute(
                    "INSERT INTO prompt_performance (prompt_id, prompt_text, strategy_name) VALUES (?, ?, ?)",
                    (new_prompt_id, evolved.new_prompt_template, strategy_name)
                )
                conn.commit()
            finally:
                conn.close()

            return evolved.model_dump_json(indent=2)
        except Exception as e:
            logger.error(f"Error in tool_evolve_strategy: {e}")
            return json.dumps({"error": str(e), "message": "Failed to evolve strategy prompt."})

    async def tool_generate_skill(self, pattern_name: str, successful_patterns_summary: str) -> str:
        """
        Codifies successful explanation workflows into a reusable markdown skill definition.
        """
        prompt = (
            f"Generate a new pedagogical skill definition named '{pattern_name}' based on these successful patterns:\n"
            f"```\n{successful_patterns_summary}\n```\n\n"
            f"Provide a structured skill definition that can be imported to optimize tutor agents."
        )
        try:
            skill = await self.athink_structured(prompt, GeneratedSkill)
            
            # Store in database
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO evolved_skills (skill_name, description, instructions, example_input, example_output)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    skill.skill_name,
                    skill.description,
                    json.dumps(skill.instructions),
                    skill.example_input,
                    skill.example_output
                ))
                conn.commit()
            finally:
                conn.close()

            return skill.model_dump_json(indent=2)
        except Exception as e:
            logger.error(f"Error in tool_generate_skill: {e}")
            return json.dumps({"error": str(e), "message": "Failed to generate skill."})
