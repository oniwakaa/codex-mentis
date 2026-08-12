import os
import yaml
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

@dataclass
class Skill:
    name: str
    domain: str
    description: str
    concepts: List[str] = field(default_factory=list)
    common_mistakes: List[str] = field(default_factory=list)
    analogies: List[str] = field(default_factory=list)
    socratic_questions: List[str] = field(default_factory=list)
    verification_strategies: List[str] = field(default_factory=list)
    prompt_template: Optional[str] = None

class SkillsEngine:
    def __init__(self, skills_dir: Optional[str] = None):
        if skills_dir is None:
            # Default directory is codex_mentis/skills/builtin
            skills_dir = os.path.join(os.path.dirname(__file__), "builtin")
        self.skills_dir = skills_dir
        self.skills_cache: Dict[str, Skill] = {}

    def load_skill(self, name: str) -> Skill:
        """Loads a skill from YAML file by name."""
        if name in self.skills_cache:
            return self.skills_cache[name]

        # Try YAML in skills_dir
        yaml_path = os.path.join(self.skills_dir, f"{name}.yaml")
        if not os.path.exists(yaml_path):
            raise FileNotFoundError(f"Skill '{name}' not found at path: {yaml_path}")

        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        skill = Skill(
            name=data.get('name', name),
            domain=data.get('domain', 'General'),
            description=data.get('description', ''),
            concepts=data.get('concepts', []),
            common_mistakes=data.get('common_mistakes', []),
            analogies=data.get('analogies', []),
            socratic_questions=data.get('socratic_questions', []),
            verification_strategies=data.get('verification_strategies', []),
            prompt_template=data.get('prompt_template', None)
        )
        self.skills_cache[name] = skill
        return skill

    def list_skills(self, domain: Optional[str] = None) -> List[str]:
        """Lists available skills, optionally filtered by domain."""
        if not os.path.exists(self.skills_dir):
            return []
        
        skill_names = []
        for file in os.listdir(self.skills_dir):
            if file.endswith('.yaml'):
                name = os.path.splitext(file)[0]
                try:
                    skill = self.load_skill(name)
                    if domain is None or skill.domain.lower() == domain.lower():
                        skill_names.append(name)
                except Exception:
                    # If load fails, ignore or list it anyway
                    if domain is None:
                        skill_names.append(name)
        return skill_names

    def get_prompt(self, skill: Skill, context: Dict[str, Any]) -> str:
        """Renders the skill as a prompt utilizing the domain knowledge."""
        template = skill.prompt_template
        if not template:
            # Default prompt template containing all structured information
            template = """You are an expert AI assistant operating in the domain of **{domain}**.
You are utilizing the specialized skill: **{name}**.
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
        
        # Formatting lists into strings
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
            user_context=user_context_str
        )

    def execute_skill(self, name: str, context: Dict[str, Any]) -> str:
        """Executes a skill by rendering the prompt and routing it to the Agent Orchestrator if available."""
        skill = self.load_skill(name)
        rendered_prompt = self.get_prompt(skill, context)

        # Attempt to import orchestrator/providers to query LLM
        try:
            # We attempt to import from the project's agents package
            from codex_mentis.agents.orchestrator import AgentOrchestrator
            # Let's say orchestrator is available
            orchestrator = AgentOrchestrator()
            # If orchestrator has a process / route method:
            # response = orchestrator.route(rendered_prompt)
            # return response
        except ImportError:
            pass

        # If not available or fails, return the rendered prompt so the caller can send it
        return rendered_prompt
