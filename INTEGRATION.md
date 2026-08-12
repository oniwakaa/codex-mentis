# Codex Mentis — Integration Notes

## After all subagents complete, run:

```bash
cd ~/projects/codex-mentis

# Verify all files exist
find codex_mentis -name "*.py" | sort

# Install in development mode
pip install -e .

# Test the CLI
codex-mentis --help
codex-mentis config init
codex-mentis chat
```

## Fix any import errors between modules

The subagents may have different assumptions about interfaces. Check:
1. codex_mentis/cli/app.py imports from agents, memory, math_engine
2. codex_mentis/agents/orchestrator.py imports from all agent files
3. codex_mentis/memory/store.py is imported by agents and CLI

## Missing pieces to add manually:
1. __init__.py files may need explicit imports
2. The REPL may need adjustment for the actual orchestrator interface
3. Provider API keys need to be loaded from config
