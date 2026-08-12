# Pitagora — Integration Notes

## After all subagents complete, run:

```bash
cd ~/projects/pitagora

# Verify all files exist
find pitagora -name "*.py" | sort

# Install in development mode
pip install -e .

# Test the CLI
pitagora --help
pitagora config init
pitagora chat
```

## Fix any import errors between modules

The subagents may have different assumptions about interfaces. Check:
1. pitagora/cli/app.py imports from agents, memory, math_engine
2. pitagora/agents/orchestrator.py imports from all agent files
3. pitagora/memory/store.py is imported by agents and CLI

## Missing pieces to add manually:
1. __init__.py files may need explicit imports
2. The REPL may need adjustment for the actual orchestrator interface
3. Provider API keys need to be loaded from config
