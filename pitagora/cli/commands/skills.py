"""Skills CLI — list, inspect, import, forge, and activate reasoning skills."""
import os
from typing import Optional

import typer

from pitagora.core.constants import CONFIG_DIR
from pitagora.cli.rich_ui import print_table, print_panel

app = typer.Typer(help="Manage and inspect reasoning skills")

BUILTIN_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "skills", "builtin")
USER_SKILLS_DIR = str(CONFIG_DIR / "skills")


def _engines():
    """Return (builtin_engine, user_engine)."""
    from pitagora.skills.engine import SkillsEngine
    builtin = SkillsEngine(skills_dir=BUILTIN_DIR)
    user = SkillsEngine(skills_dir=USER_SKILLS_DIR)
    return builtin, user


def _all_skills():
    """Yield (origin, skill) for every loadable skill across builtin + user dirs."""
    builtin_eng, user_eng = _engines()
    seen = set()
    for name in builtin_eng.list_skills():
        if name in seen:
            continue
        try:
            yield "builtin", builtin_eng.load_skill(name)
        except Exception:
            continue
    for name in user_eng.list_skills():
        if name in seen:
            continue
        try:
            yield user_eng.load_skill(name).origin or "imported", user_eng.load_skill(name)
        except Exception:
            continue


@app.command("list")
def list_skills():
    """List all available skills (builtin + user)."""
    rows = []
    for origin, skill in _all_skills():
        status = "on" if skill.enabled else "off"
        rows.append([skill.name, skill.domain, origin, status, f"v{skill.version}"])
    if not rows:
        typer.echo("No skills found.")
        return
    print_table(
        ["Skill", "Domain", "Origin", "State", "Ver"],
        rows,
        title="Available Skills",
    )


@app.command("show")
def show_skill(name: str = typer.Argument(..., help="Skill name to inspect")):
    """Show details of a specific skill."""
    builtin_eng, user_eng = _engines()
    skill = None
    for eng in (builtin_eng, user_eng):
        try:
            skill = eng.load_skill(name)
            break
        except FileNotFoundError:
            continue
    if skill is None:
        typer.echo(f"Skill '{name}' not found.")
        raise typer.Exit(1)
    triggers = ", ".join(skill.trigger_patterns) or "-"
    tmpl = (skill.template or skill.prompt_template or "(none)")[:400]
    content = (
        f"[bold]Domain:[/bold] {skill.domain}\n"
        f"[bold]Origin:[/bold] {skill.origin}\n"
        f"[bold]State:[/bold] {'enabled' if skill.enabled else 'disabled'}\n"
        f"[bold]Triggers:[/bold] {triggers}\n\n"
        f"[bold]Template:[/bold]\n{tmpl}"
    )
    print_panel(content, title=f"Skill: {skill.name}", style="magenta")


@app.command("activate")
def activate_skill(name: str = typer.Argument(..., help="Skill to enable")):
    """Enable a skill for matching."""
    from pitagora.skills.evolution import SkillForge
    forge = SkillForge(USER_SKILLS_DIR)
    try:
        forge.activate(name)
    except FileNotFoundError:
        typer.echo(f"Skill '{name}' not found in user skills dir.")
        raise typer.Exit(1)
    typer.echo(f"Activated skill '{name}'.")


@app.command("deactivate")
def deactivate_skill(name: str = typer.Argument(..., help="Skill to disable")):
    """Disable a skill from matching."""
    from pitagora.skills.engine import SkillsEngine
    eng = SkillsEngine(skills_dir=USER_SKILLS_DIR)
    try:
        skill = eng.load_skill(name)
    except FileNotFoundError:
        typer.echo(f"Skill '{name}' not found in user skills dir.")
        raise typer.Exit(1)
    skill.enabled = False
    eng.save_skill(skill)
    typer.echo(f"Deactivated skill '{name}'.")


@app.command("forge")
def forge_list():
    """Show model-created skills pending review."""
    from pitagora.skills.evolution import SkillForge
    forge = SkillForge(USER_SKILLS_DIR)
    pending = forge.pending_review()
    if not pending:
        typer.echo("No skills pending review.")
        return
    rows = [[s.name, s.domain, ", ".join(s.trigger_patterns) or "-"] for s in pending]
    print_table(["Skill", "Domain", "Triggers"], rows, title="Skills Pending Review")


@app.command("review")
def review_skill(name: str = typer.Argument(..., help="Skill to review")):
    """Review a model-created skill, then activate or reject it."""
    from pitagora.skills.evolution import SkillForge
    forge = SkillForge(USER_SKILLS_DIR)
    pending = {s.name: s for s in forge.pending_review()}
    if name not in pending:
        typer.echo(f"Skill '{name}' is not pending review.")
        raise typer.Exit(1)
    skill = pending[name]
    typer.echo(f"Name: {skill.name}\nDomain: {skill.domain}\nTriggers: {skill.trigger_patterns}\n")
    typer.echo(f"Template:\n{skill.template}\n")
    decision = typer.prompt("Activate or reject?", default="activate")
    if decision.lower().startswith("a"):
        forge.activate(name)
        typer.echo(f"Activated '{name}'.")
    else:
        forge.reject(name)
        typer.echo(f"Rejected and removed '{name}'.")


@app.command("import")
def import_skills(
    source: str = typer.Option(..., "--from", help="Source: 'claude-code' or a directory path"),
):
    """Import skills from Claude Code (.md) or a directory of .yaml/.md files."""
    from pitagora.skills.engine import SkillsEngine
    eng = SkillsEngine(skills_dir=USER_SKILLS_DIR)
    src_dir = source
    if source == "claude-code":
        src_dir = os.path.expanduser("~/.claude/skills")
        if not os.path.isdir(src_dir):
            typer.echo(f"Claude Code skills dir not found: {src_dir}")
            raise typer.Exit(1)
    if not os.path.isdir(src_dir):
        typer.echo(f"Directory not found: {src_dir}")
        raise typer.Exit(1)

    imported = 0
    for fname in sorted(os.listdir(src_dir)):
        if fname.endswith(".yaml") or fname.endswith(".yml"):
            _import_yaml(eng, os.path.join(src_dir, fname))
            imported += 1
        elif fname.endswith(".md"):
            _import_markdown(eng, os.path.join(src_dir, fname))
            imported += 1
    typer.echo(f"Imported {imported} skill(s) into {USER_SKILLS_DIR}.")


def _import_yaml(eng, path: str) -> None:
    import yaml
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict) or "name" not in data:
        return
    from pitagora.skills.engine import Skill
    skill = Skill(
        name=data["name"],
        domain=data.get("domain", "General"),
        description=data.get("description", ""),
        concepts=data.get("concepts", []),
        common_mistakes=data.get("common_mistakes", []),
        analogies=data.get("analogies", []),
        socratic_questions=data.get("socratic_questions", []),
        verification_strategies=data.get("verification_strategies", []),
        prompt_template=data.get("prompt_template"),
        trigger_patterns=data.get("trigger_patterns", []),
        template=data.get("template", None),
        tools_used=data.get("tools_used", []),
        origin="imported",
        enabled=data.get("enabled", True),
        version=data.get("version", 1),
    )
    eng.save_skill(skill)


def _import_markdown(eng, path: str) -> None:
    """Convert a Claude Code markdown skill to a Pitagora skill YAML.

    ponytail: heuristic extraction — pulls trigger patterns from a
    'When to use' section and the body becomes the template. Good enough
    for a first import; refine manually via `pitagora skills show`.
    """
    import re
    with open(path) as f:
        text = f.read()
    name = os.path.splitext(os.path.basename(path))[0]
    # Trigger patterns from "When to use" / "Use when" sections
    triggers = []
    m = re.search(r"(?im)^#+\s*(when to use|use when).*?(?=^#|\Z)", text)
    if m:
        for line in m.group(0).splitlines()[1:]:
            line = line.strip("- *").strip()
            if line:
                triggers.append(line)
    if not triggers:
        triggers = [name]
    from pitagora.skills.engine import Skill
    skill = Skill(
        name=name.replace(" ", "_").lower(),
        domain="Imported",
        description=text.splitlines()[0].lstrip("# ").strip()[:200],
        concepts=[],
        template=text,
        trigger_patterns=triggers,
        origin="imported",
        enabled=True,
        version=1,
    )
    eng.save_skill(skill)


@app.command("evolve")
def evolve_skill(name: Optional[str] = typer.Argument(None, help="Skill to evolve")):
    """Display evolution history / performance metrics for a skill."""
    from pitagora.skills.evolution import SkillEvolution
    evo = SkillEvolution()
    if name:
        stats = evo.get_stats(name)
        print_panel(
            f"Success rate: {stats.success_rate:.1%}\n"
            f"Uses: {stats.use_count}\n"
            f"Avg confidence: {stats.avg_confidence:.2f}",
            title=f"Evolution: {name}",
            style="cyan",
        )
    else:
        dash = evo.get_performance_dashboard()
        typer.echo(f"Total uses: {dash['total_usage_count']}  Overall success: {dash['overall_success_rate']:.1%}")
