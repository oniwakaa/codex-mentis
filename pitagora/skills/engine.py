import os
import re
from difflib import SequenceMatcher
from typing import Any

import httpx
import yaml
from pydantic import BaseModel, Field


class Skill(BaseModel):
    name: str
    domain: str = "General"
    description: str = ""
    concepts: list[str] = Field(default_factory=list)
    common_mistakes: list[str] = Field(default_factory=list)
    analogies: list[str] = Field(default_factory=list)
    socratic_questions: list[str] = Field(default_factory=list)
    verification_strategies: list[str] = Field(default_factory=list)
    exercises: list[str] = Field(default_factory=list)
    prompt_template: str | None = None
    # WS3: dynamic skills extension (backward-compatible — all optional)
    trigger_patterns: list[str] = Field(default_factory=list)
    template: str | None = None
    tools_used: list[str] = Field(default_factory=list)
    origin: str = Field(default="builtin")  # builtin | model_created | imported
    enabled: bool = Field(default=True)
    version: int = Field(default=1)


class SkillsEngine:
    def __init__(self, skills_dir: str | None = None):
        if skills_dir is None:
            # Default directory is pitagora/skills/builtin
            skills_dir = os.path.join(os.path.dirname(__file__), "builtin")
        self.skills_dir = os.path.abspath(skills_dir)
        os.makedirs(self.skills_dir, exist_ok=True)
        self.skills_cache: dict[str, Skill] = {}

    def load_skill(self, name: str) -> Skill:
        """Loads a skill from YAML file by name."""
        if name in self.skills_cache:
            return self.skills_cache[name]

        yaml_path = os.path.join(self.skills_dir, f"{name}.yaml")
        if not os.path.exists(yaml_path):
            raise FileNotFoundError(f"Skill '{name}' not found at path: {yaml_path}")

        with open(yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        skill = Skill(
            name=data.get("name", name),
            domain=data.get("domain", "General"),
            description=data.get("description", ""),
            concepts=data.get("concepts", []),
            common_mistakes=data.get("common_mistakes", []),
            analogies=data.get("analogies", []),
            socratic_questions=data.get("socratic_questions", []),
            verification_strategies=data.get("verification_strategies", []),
            exercises=data.get("exercises", []),
            prompt_template=data.get("prompt_template", None),
            trigger_patterns=data.get("trigger_patterns", []),
            template=data.get("template", None),
            tools_used=data.get("tools_used", []),
            origin=data.get("origin", "builtin"),
            enabled=data.get("enabled", True),
            version=data.get("version", 1),
        )
        self.skills_cache[name] = skill
        return skill

    def save_skill(self, skill: Skill) -> None:
        """Saves a skill definition to YAML file in the skills directory."""
        yaml_path = os.path.join(self.skills_dir, f"{skill.name.lower()}.yaml")
        # Pydantic v2 dump
        data = skill.model_dump()
        with open(yaml_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)
        self.skills_cache[skill.name] = skill

    def list_skills(self, domain: str | None = None) -> list[str]:
        """Lists available skills, optionally filtered by domain."""
        if not os.path.exists(self.skills_dir):
            return []

        skill_names = []
        for file in os.listdir(self.skills_dir):
            if file.endswith(".yaml"):
                name = os.path.splitext(file)[0]
                try:
                    skill = self.load_skill(name)
                    if domain is None or skill.domain.lower() == domain.lower():
                        skill_names.append(name)
                except Exception:
                    # Fallback if load fails
                    if domain is None:
                        skill_names.append(name)
        return skill_names

    def get_prompt(self, skill: Skill, context: dict[str, Any]) -> str:
        """Renders the skill as a prompt utilizing the domain knowledge."""
        template = skill.prompt_template
        if not template:
            # Default prompt template containing all structured information
            template = """You are an expert AI assistant operating in the domain of **{domain}**.
You are utilizing the specialized skill: **{name}** (v{version}).
Description: {description}

### Mastered Concepts:
{concepts_list}

### Common Mistakes to Avoid:
{mistakes_list}

### Helpful Analogies to Use:
{analogies_list}

### Socratic Guidance Questions:
{socratic_list}

### Mathematical Verification Strategies:
{verification_list}

### Context:
{user_context}

Please solve the problem or respond to the query in the context of the above guidelines. Ensure your response is mathematically rigorous and leverages the verification strategies.
"""

        concepts_list = "\n".join(f"- {c}" for c in skill.concepts)
        mistakes_list = "\n".join(f"- {m}" for m in skill.common_mistakes)
        analogies_list = "\n".join(f"- {a}" for a in skill.analogies)
        socratic_list = "\n".join(f"- {q}" for q in skill.socratic_questions)
        verification_list = "\n".join(f"- {v}" for v in skill.verification_strategies)

        user_context_str = "\n".join(f"{k}: {v}" for k, v in context.items())

        return template.format(
            domain=skill.domain,
            name=skill.name,
            description=skill.description,
            concepts_list=concepts_list,
            mistakes_list=mistakes_list,
            analogies_list=analogies_list,
            socratic_list=socratic_list,
            verification_list=verification_list,
            user_context=user_context_str,
            version=skill.version,
        )

    def execute_skill(self, name: str, context: dict[str, Any]) -> str:
        """Executes a skill by rendering the prompt."""
        skill = self.load_skill(name)
        return self.get_prompt(skill, context)

    # --- Skill Matching ---
    def match_skills(self, topic: str, problem_text: str | None = None) -> list[Skill]:
        """
        Matches and ranks skills relevant to a topic and/or problem text.
        Trigger patterns (regex) take priority; falls back to keyword/fuzzy scoring.
        """
        all_skills = [self.load_skill(name) for name in self.list_skills()]
        # ponytail: O(n*m) regex scan is fine for a small builtin skill set;
        # index trigger patterns if the catalog grows past ~100 skills.
        scored_skills = []

        search_query = (topic + " " + (problem_text or "")).lower()

        for skill in all_skills:
            if not skill.enabled:
                continue
            score = 0.0

            # Trigger-pattern regex match (highest signal)
            for pattern in skill.trigger_patterns:
                try:
                    if re.search(pattern, search_query, re.IGNORECASE):
                        score += 0.6
                        break
                except re.error:
                    # Treat malformed patterns as literal substrings
                    if pattern.lower() in search_query:
                        score += 0.6
                        break

            # Exact domain match
            if skill.domain.lower() == topic.lower():
                score += 0.5

            # Substring checks
            if skill.name.lower() in search_query:
                score += 0.4

            # Concept matches
            for concept in skill.concepts:
                if concept.lower() in search_query:
                    score += 0.2

            # Fuzzy match description/name
            name_sim = SequenceMatcher(None, skill.name.lower(), topic.lower()).ratio()
            desc_sim = 0.0
            if skill.description:
                desc_sim = (
                    max(
                        SequenceMatcher(None, word.lower(), topic.lower()).ratio()
                        for word in skill.description.split()
                    )
                    * 0.3
                )

            score += max(name_sim, desc_sim)

            if score > 0.1:
                scored_skills.append((skill, score))

        scored_skills.sort(key=lambda x: x[1], reverse=True)
        return [skill for skill, _ in scored_skills]

    def render_template(self, skill: Skill, context: dict[str, Any]) -> str | None:
        """Render a skill's `template` with {{variable}} placeholders from context.

        Returns None when the skill has no template (callers fall back to get_prompt).
        """
        if not skill.template:
            return None
        rendered = skill.template
        for key, value in context.items():
            rendered = rendered.replace("{{" + key + "}}", str(value))
        return rendered

    # --- Skill Composition ---
    def create_composite_skill(self, composite_name: str, skill_names: list[str]) -> Skill:
        """
        Chains multiple skills together to create a single composite Skill.
        """
        skills = [self.load_skill(name) for name in skill_names]
        if not skills:
            raise ValueError("No valid skills provided for composition.")

        merged_concepts = []
        merged_mistakes = []
        merged_analogies = []
        merged_socratic = []
        merged_verification = []

        for sk in skills:
            merged_concepts.extend(c for c in sk.concepts if c not in merged_concepts)
            merged_mistakes.extend(m for m in sk.common_mistakes if m not in merged_mistakes)
            merged_analogies.extend(a for a in sk.analogies if a not in merged_analogies)
            merged_socratic.extend(q for q in sk.socratic_questions if q not in merged_socratic)
            merged_verification.extend(
                v for v in sk.verification_strategies if v not in merged_verification
            )

        domains = list(set(sk.domain for sk in skills))
        composite_domain = domains[0] if len(domains) == 1 else "Composite / Multidisciplinary"

        composite_desc = f"Composite skill composed of: {', '.join(skill_names)}."

        return Skill(
            name=composite_name,
            domain=composite_domain,
            description=composite_desc,
            concepts=merged_concepts,
            common_mistakes=merged_mistakes,
            analogies=merged_analogies,
            socratic_questions=merged_socratic,
            verification_strategies=merged_verification,
            version=1,
        )

    # --- Community Skill Installation ---
    def install_skill_from_url(self, url: str) -> str:
        """
        Installs a skill definition from a remote URL.
        Returns the name of the installed skill.
        """
        resp = httpx.get(url, follow_redirects=True)
        if resp.status_code != 200:
            raise httpx.HTTPStatusError(
                f"Failed to fetch skill from URL: {url}", request=resp.request, response=resp
            )

        data = yaml.safe_load(resp.text)
        if not isinstance(data, dict) or "name" not in data:
            raise ValueError("Invalid skill definition format.")

        skill = Skill(
            name=data["name"],
            domain=data.get("domain", "General"),
            description=data.get("description", ""),
            concepts=data.get("concepts", []),
            common_mistakes=data.get("common_mistakes", []),
            analogies=data.get("analogies", []),
            socratic_questions=data.get("socratic_questions", []),
            verification_strategies=data.get("verification_strategies", []),
            exercises=data.get("exercises", []),
            prompt_template=data.get("prompt_template"),
            trigger_patterns=data.get("trigger_patterns", []),
            template=data.get("template", None),
            tools_used=data.get("tools_used", []),
            origin=data.get("origin", "imported"),
            enabled=data.get("enabled", True),
            version=data.get("version", 1),
        )

        self.save_skill(skill)
        return skill.name
