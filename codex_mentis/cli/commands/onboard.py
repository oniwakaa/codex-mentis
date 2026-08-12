"""Onboarding system — first-run experience with level assessment."""
import os
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

PROFILE_PATH = Path("~/.codex-mentis/profile.yaml")


def has_profile() -> bool:
    """Check if user has completed onboarding."""
    return PROFILE_PATH.expanduser().exists()


def load_profile() -> Optional[Dict]:
    """Load user profile from disk."""
    import yaml
    path = PROFILE_PATH.expanduser()
    if not path.exists():
        return None
    with open(path) as f:
        return yaml.safe_load(f)


def save_profile(profile: Dict) -> None:
    """Save user profile to disk."""
    import yaml
    path = PROFILE_PATH.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.dump(profile, f, default_flow_style=False)


# Diagnostic questions for level assessment
MATH_QUESTIONS = [
    {
        "question": "Solve for x: 2x + 3 = 7",
        "answer": "2",
        "keywords": ["2", "x=2", "x = 2"],
        "level": "beginner",
    },
    {
        "question": "What is the derivative of x² with respect to x?",
        "answer": "2x",
        "keywords": ["2x", "2*x", "2 x"],
        "level": "intermediate",
    },
    {
        "question": "What is an eigenvalue of a matrix?",
        "answer": "scalar λ such that Av = λv",
        "keywords": ["scalar", "eigenvalue", "Av", "λv", "lambda", "vector", "transform"],
        "level": "advanced",
    },
    {
        "question": "Evaluate: ∫₀¹ x² dx",
        "answer": "1/3",
        "keywords": ["1/3", "0.333", "one third", "third"],
        "level": "intermediate",
    },
]

PHYSICS_QUESTIONS = [
    {
        "question": "State Newton's second law of motion.",
        "answer": "F = ma",
        "keywords": ["F=ma", "force", "mass", "acceleration", "F = ma"],
        "level": "beginner",
    },
    {
        "question": "What is conserved in a closed system according to Noether's theorem?",
        "answer": "energy (from time symmetry)",
        "keywords": ["energy", "conservation", "symmetry", "momentum", "Noether"],
        "level": "advanced",
    },
    {
        "question": "What is the Lagrangian in classical mechanics?",
        "answer": "L = T - V (kinetic minus potential energy)",
        "keywords": ["T - V", "kinetic", "potential", "L =", "Lagrangian", "difference"],
        "level": "advanced",
    },
    {
        "question": "What is the speed of light in vacuum (approximate value)?",
        "answer": "3 × 10⁸ m/s",
        "keywords": ["3", "10^8", "10⁸", "300", "million", "c", "speed of light"],
        "level": "beginner",
    },
]


def run_onboarding(console=None, skip: bool = False, level_override: Optional[str] = None) -> Dict:
    """Run the onboarding flow. Returns the profile dict."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt, Confirm
    from rich.text import Text
    from rich.progress import Progress, SpinnerColumn, TextColumn

    if console is None:
        console = Console()

    if skip:
        profile = {
            "name": "User",
            "interests": ["mathematics", "physics"],
            "levels": {"mathematics": level_override or "intermediate", "physics": level_override or "intermediate"},
            "onboarding_date": datetime.now().isoformat(),
            "diagnostic_scores": {},
        }
        save_profile(profile)
        return profile

    # Step 1: Welcome
    banner = """
╔═══════════════════════════════════════════════════════╗
║                                                       ║
║      🧠  C O D E X   M E N T I S  🧠                ║
║                                                       ║
║      Book of the Mind                                 ║
║      AI-Powered Math & Physics Learning               ║
║                                                       ║
╚═══════════════════════════════════════════════════════╝"""
    console.print(banner, style="bold cyan")
    console.print()

    console.print(Panel(
        "Welcome to Codex Mentis! Let's set up your learning profile.\n"
        "This takes about 2 minutes and helps me personalize your experience.",
        title="👋 Welcome",
        border_style="blue",
    ))

    # Step 2: Name and interests
    name = Prompt.ask("What's your name?", default="Scholar")
    console.print()

    console.print("[bold]What subjects interest you?[/bold]")
    console.print("  [cyan]1[/cyan] = Mathematics")
    console.print("  [cyan]2[/cyan] = Physics")
    console.print("  [cyan]3[/cyan] = Both")
    choice = Prompt.ask("Your choice", choices=["1", "2", "3"], default="3")

    interests = []
    if choice in ("1", "3"):
        interests.append("mathematics")
    if choice in ("2", "3"):
        interests.append("physics")

    # Step 3: Level assessment
    levels = {}
    scores = {}

    for subject in interests:
        console.print(f"\n[bold cyan]📊 Quick assessment: {subject.title()}[/bold cyan]")
        console.print("[dim]Answer these questions to help me gauge your level. Don't worry — there's no wrong answer![/dim]\n")

        questions = MATH_QUESTIONS if subject == "mathematics" else PHYSICS_QUESTIONS
        correct = 0
        total = len(questions)

        for i, q in enumerate(questions, 1):
            console.print(f"[bold]Q{i}:[/bold] {q['question']}")
            answer = Prompt.ask("  Your answer", default="")
            
            # Simple keyword matching
            answer_lower = answer.lower()
            matched = any(kw.lower() in answer_lower for kw in q["keywords"])
            
            if matched:
                correct += 1
                console.print("  [green]✓ Good![/green]\n")
            elif answer.strip() == "":
                console.print(f"  [dim]The answer is: {q['answer']}[/dim]\n")
            else:
                console.print(f"  [yellow]Not quite — the answer is: {q['answer']}[/yellow]\n")

        # Determine level from score
        pct = correct / total if total > 0 else 0
        if pct >= 0.75:
            level = "advanced"
        elif pct >= 0.4:
            level = "intermediate"
        else:
            level = "beginner"

        levels[subject] = level
        scores[subject] = {"correct": correct, "total": total, "percentage": pct}
        
        color = "green" if level == "advanced" else "yellow" if level == "intermediate" else "blue"
        console.print(f"  Your {subject} level: [bold {color}]{level.title()}[/bold {color}] ({correct}/{total})")

    # Step 4: Save profile
    profile = {
        "name": name,
        "interests": interests,
        "levels": levels,
        "onboarding_date": datetime.now().isoformat(),
        "diagnostic_scores": scores,
    }
    save_profile(profile)

    # Step 5: Show results
    console.print(Panel(
        f"[bold green]Profile created![/bold green]\n\n"
        f"Name: {name}\n"
        f"Interests: {', '.join(interests)}\n" +
        "\n".join(f"  {subj}: {lvl.title()}" for subj, lvl in levels.items()),
        title="🎓 Your Profile",
        border_style="green",
    ))

    # Step 6: Recommended learning path
    console.print("\n[bold]📚 Recommended Learning Paths:[/bold]")
    if "mathematics" in interests:
        level = levels.get("mathematics", "beginner")
        if level == "beginner":
            console.print("  [cyan]Mathematics:[/cyan] Algebra → Calculus → Linear Algebra")
        elif level == "intermediate":
            console.print("  [cyan]Mathematics:[/cyan] Multivariable Calculus → Differential Equations → Real Analysis")
        else:
            console.print("  [cyan]Mathematics:[/cyan] Topology → Complex Analysis → Abstract Algebra")
    
    if "physics" in interests:
        level = levels.get("physics", "beginner")
        if level == "beginner":
            console.print("  [cyan]Physics:[/cyan] Kinematics → Newton's Laws → Energy & Momentum")
        elif level == "intermediate":
            console.print("  [cyan]Physics:[/cyan] Lagrangian Mechanics → Electromagnetism → Waves")
        else:
            console.print("  [cyan]Physics:[/cyan] Quantum Mechanics → Statistical Mechanics → QFT")

    # Step 7: Available commands
    console.print(Panel(
        "[bold]Get started:[/bold]\n\n"
        "  codex-mentis study \"Lagrangian mechanics\"    Start a Socratic lesson\n"
        "  codex-mentis explain \"eigenvalues\" --level beginner\n"
        "  codex-mentis research \"topological insulators\"  Web research\n"
        "  codex-mentis ingest ./papers/               Analyze your documents\n"
        "  codex-mentis derive \"Euler-Lagrange\"        Derive with verification\n"
        "  codex-mentis review start                   Daily spaced repetition\n"
        "  codex-mentis doctor                         Check system health\n"
        "  codex-mentis profile                        View your profile\n",
        title="🚀 Quick Start",
        border_style="cyan",
    ))

    return profile
