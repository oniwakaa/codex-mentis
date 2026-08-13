import json
import logging
import sqlite3
import random
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from pitagora.agents.base import BaseAgent, AgentResponse
from pitagora.agents.providers.base import BaseProvider

logger = logging.getLogger(__name__)

SELF_IMPROVER_SYSTEM_PROMPT = """<role>Self-improver for Pitagora. Optimize prompts and pedagogical strategies from empirical success metrics.</role>

<instructions>
- Analyze outcome metrics to evaluate strategies per topic and level
- Balance exploration vs. exploitation via Thompson Sampling on Beta(alpha, beta) priors
- Rewrite underperforming prompts (avg < 3.0 over ≥10 uses) into improved variants
- Codify successful explanation patterns into reusable skill definitions
</instructions>

<example>
Strategy "socratic" underperforms (avg 2.4 over 12 uses):
"Revised prompt: ask one question at a time, confirm the student's prior step before advancing, and avoid revealing the answer — guide toward it."
</example>
"""

class EvolvedPrompt(BaseModel):
    strategy_name: str = Field(description="The strategy that was evolved")
    new_prompt_template: str = Field(description="The full revised system prompt template")
    explanation_of_changes: str = Field(description="Why the prompt was updated and how it addresses the failure logs")


# Map a teaching classification label to a 1-5 response-quality score.
# Used by the chat REPL to feed the feedback loop with a real signal
# derived from the ResponseAnalyzer's classification of the learner's reply.
CLASSIFICATION_QUALITY: Dict[str, int] = {
    "correct": 5,
    "deeper": 5,
    "partial": 3,
    "question": 3,
    "skip": 2,
    "confused": 1,
    "off_topic": 1,
}


def quality_from_classification(label: str) -> int:
    """Convert a teaching classification label to a 1-5 quality score."""
    return CLASSIFICATION_QUALITY.get(str(label).lower(), 3)

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

        # 5. Strategy metrics (WS1) — per-interaction pedagogical outcomes
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS strategy_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT,
                level TEXT,
                strategy_used TEXT,
                response_quality INTEGER,
                time_to_understanding REAL,
                hints_needed INTEGER,
                success INTEGER,
                feedback TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_metrics_topic_level "
            "ON strategy_metrics(topic, level)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_metrics_strategy "
            "ON strategy_metrics(strategy_used)"
        )

        # 6. Prompt variants (WS1) — evolved prompts with lineage
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS prompt_variants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_name TEXT,
                prompt_text TEXT,
                parent_id INTEGER,
                performance_delta REAL,
                avg_quality REAL,
                uses INTEGER DEFAULT 0,
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

    # ─────────────────────────────────────────────────────────────────────
    # WS1: Self-improving feedback loop — metrics, evaluation, selection
    # ─────────────────────────────────────────────────────────────────────

    def record_interaction(
        self,
        topic: str,
        level: str,
        strategy_used: str,
        response_quality: int,
        time_to_understanding: Optional[float] = None,
        hints_needed: Optional[int] = None,
        success: Optional[bool] = None,
        feedback: str = "",
    ) -> int:
        """Record a single teaching interaction with pedagogical metrics.

        `response_quality` is a 1-5 heuristic (or explicit student feedback).
        `success` defaults to response_quality >= 4 when not supplied.
        Returns the row id.
        """
        if success is None:
            success = response_quality >= 4
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO strategy_metrics
                   (topic, level, strategy_used, response_quality,
                    time_to_understanding, hints_needed, success, feedback)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (topic, level, strategy_used, response_quality,
                 time_to_understanding, hints_needed, 1 if success else 0, feedback),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def strategy_report(
        self,
        topic: Optional[str] = None,
        level: Optional[str] = None,
        last_n: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Aggregate metrics per strategy (optionally filtered by topic/level).

        Computes avg_quality, avg_hints_needed, success_rate, and use count.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            where = []
            params: List[Any] = []
            if topic:
                where.append("topic = ?")
                params.append(topic)
            if level:
                where.append("level = ?")
                params.append(level)
            where_sql = ("WHERE " + " AND ".join(where)) if where else ""
            limit_sql = f"LIMIT {int(last_n)}" if last_n else ""
            # ponytail: subquery rowid filter keeps the "last N" semantics simple
            # without window functions; fine for the small interaction volume
            # of a teaching CLI. Upgrade to a window function if N grows large.
            cur.execute(
                f"""SELECT strategy_used,
                           COUNT(*) AS uses,
                           AVG(response_quality) AS avg_quality,
                           AVG(hints_needed) AS avg_hints,
                           SUM(success) * 1.0 / COUNT(*) AS success_rate
                    FROM (
                        SELECT * FROM strategy_metrics {where_sql}
                        ORDER BY timestamp DESC {limit_sql}
                    )
                    GROUP BY strategy_used
                    ORDER BY avg_quality DESC""",
                params,
            )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
        finally:
            conn.close()

    def select_strategy_for(self, topic: str, level: str) -> str:
        """Pick a strategy for a topic+level.

        With ≥5 past interactions, exploit the best-performing strategy.
        Otherwise explore via weighted random favouring untested strategies.
        """
        report = {r["strategy_used"]: r for r in self.strategy_report(topic=topic, level=level)}
        total_uses = sum(r["uses"] for r in report.values())

        strategies = ["socratic", "feynman", "analogy", "side_by_side", "formal_proof"]
        if total_uses >= 5 and report:
            # Exploit: highest avg_quality (ties broken by success_rate)
            best = max(
                report.items(),
                key=lambda kv: (kv[1]["avg_quality"], kv[1]["success_rate"]),
            )
            return best[0]

        # Explore: weighted random favouring untested strategies
        weights = []
        for s in strategies:
            uses = report.get(s, {}).get("uses", 0)
            # untested -> high weight; more uses -> lower weight
            weights.append(1.0 / (uses + 1))
        return random.choices(strategies, weights=weights, k=1)[0]

    async def suggest_prompt_revision(
        self, strategy_name: str, metrics: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """When a strategy underperforms (avg < 3.0 over ≥10 uses), use the LLM
        to rewrite the prompt and store the variant with lineage + delta."""
        if metrics is None:
            metrics = {}
            for r in self.strategy_report():
                if r["strategy_used"] == strategy_name:
                    metrics = r
                    break
        avg_quality = metrics.get("avg_quality", 0.0) or 0.0
        uses = metrics.get("uses", 0) or 0

        # Guard: only revise when genuinely underperforming with enough data
        if uses < 10 or avg_quality >= 3.0:
            return {
                "strategy_name": strategy_name,
                "revised": False,
                "reason": f"no revision needed (uses={uses}, avg_quality={avg_quality:.2f})",
            }

        # Fetch the current best prompt text as the parent
        parent = json.loads(await self.tool_get_best_prompt(strategy_name))
        parent_text = parent.get("prompt_text", "")

        prompt = (
            f"<role>Prompt engineer.</role>\n\n"
            f"<context>The '{strategy_name}' teaching strategy is underperforming.\n"
            f"avg_quality={avg_quality:.2f} over {uses} uses.\n"
            f"Current prompt:\n```\n{parent_text}\n```</context>\n\n"
            f"<instructions>Rewrite the prompt to fix the weaknesses. Keep it under "
            f"500 tokens, use XML tags, and include one example. Output only the new prompt.</instructions>"
        )
        try:
            evolved = await self.athink_structured(prompt, EvolvedPrompt)
        except Exception as e:
            logger.error(f"Error in suggest_prompt_revision: {e}")
            return {"strategy_name": strategy_name, "revised": False, "error": str(e)}

        # Compute performance delta vs parent and persist the variant
        parent_id = None
        if parent.get("prompt_id", "").endswith("_default"):
            parent_id = None
        else:
            conn = sqlite3.connect(self.db_path)
            try:
                row = conn.cursor().execute(
                    "SELECT id FROM prompt_variants WHERE strategy_name=? ORDER BY id DESC LIMIT 1",
                    (strategy_name,),
                ).fetchone()
                parent_id = row[0] if row else None
            finally:
                conn.close()

        delta = avg_quality - 3.0  # baseline target
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO prompt_variants
                   (strategy_name, prompt_text, parent_id, performance_delta, avg_quality, uses)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (strategy_name, evolved.new_prompt_template, parent_id, delta, avg_quality, uses),
            )
            conn.commit()
            variant_id = cur.lastrowid
        finally:
            conn.close()

        return {
            "strategy_name": strategy_name,
            "revised": True,
            "variant_id": variant_id,
            "parent_id": parent_id,
            "performance_delta": delta,
            "new_prompt": evolved.new_prompt_template,
            "explanation": evolved.explanation_of_changes,
        }

    def digest(self) -> Dict[str, Any]:
        """Weekly-style digest: top/bottom strategies, trending topics, focus areas."""
        report = self.strategy_report()
        if not report:
            return {"top": [], "bottom": [], "trending": [], "focus": []}
        sorted_by_quality = sorted(report, key=lambda r: r["avg_quality"], reverse=True)
        top = sorted_by_quality[:3]
        bottom = sorted_by_quality[-3:][::-1]

        # Trending topics = most-used topics in recent interactions
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            cur.execute(
                """SELECT topic, COUNT(*) AS uses
                   FROM strategy_metrics
                   GROUP BY topic
                   ORDER BY uses DESC
                   LIMIT 5"""
            )
            trending = [{"topic": r[0], "uses": r[1]} for r in cur.fetchall()]
        finally:
            conn.close()

        # Focus = bottom strategies' topics
        focus = [r["strategy_used"] for r in bottom]
        return {"top": top, "bottom": bottom, "trending": trending, "focus": focus}

    async def rate_explanation(
        self, topic: str, level: str, strategy: str, explanation: str
    ) -> int:
        """Content-derived self-assessment of a produced explanation.

        The orchestrator one-shot tutor path has no learner reply to classify,
        so this asks the model to rate the explanation it just produced on a
        1-5 pedagogical-quality scale. Returns 3 (neutral) on any failure.
        This is a heuristic, not a student signal — the chat REPL teaching path
        remains the source of real learner-derived quality.
        """
        if not explanation or not explanation.strip():
            return 3
        prompt = (
            f"<role>Pedagogical quality assessor.</role>\n"
            f"<context>A tutor explained '{topic}' to a {level} student using a "
            f"{strategy} style.</context>\n"
            f"<explanation>\n{explanation[:1500]}\n</explanation>\n"
            f"<instructions>Rate the explanation's pedagogical quality on a "
            f"1-5 scale (1=confusing/wrong, 3=adequate, 5=clear, accurate, "
            f"well-paced). Reply with ONLY a single integer 1-5.</instructions>"
        )
        try:
            resp = await self.athink(prompt)
            text = (resp.content or "").strip()
            # Take the first integer found in the response.
            for tok in text.split():
                if tok.isdigit():
                    q = int(tok)
                    if 1 <= q <= 5:
                        return q
            # Fallback: scan for a digit anywhere.
            for ch in text:
                if ch.isdigit() and 1 <= int(ch) <= 5:
                    return int(ch)
        except Exception as e:
            logger.debug("rate_explanation failed: %s", e)
        return 3
