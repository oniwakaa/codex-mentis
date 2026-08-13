import logging
import yaml
from pathlib import Path
from typing import List
from pydantic import BaseModel, Field

from pitagora.core.constants import CONFIG_DIR, CONFIG_PATH

log = logging.getLogger(__name__)

class ProvidersConfig(BaseModel):
    default: str = Field(default="gemini", description="For general tasks")
    reasoning: str = Field(default="openai", description="For complex proofs")
    vision: str = Field(default="anthropic", description="For diagram analysis")
    local: str = Field(default="llama", description="For privacy-sensitive tasks")
    config: dict = Field(default_factory=dict, description="Provider connection config")

class MemoryConfig(BaseModel):
    backend: str = Field(default="sqlite", description="Database backend")
    vector_model: str = Field(default="all-MiniLM-L6-v2", description="Model for embeddings")
    spaced_repetition: bool = Field(default=True, description="Enable spaced repetition scheduling")

class MathConfig(BaseModel):
    sandbox: str = Field(default="sympy", description="Math sandbox engine")
    verification_levels: List[str] = Field(default_factory=lambda: ["computational", "cross_check"], description="Math verification levels")
    plot_backend: str = Field(default="plotext", description="Plotting backend")

class MCPConfig(BaseModel):
    evermemos: bool = Field(default=True, description="Enable EverMemOS integration")
    obsidian: str = Field(default_factory=lambda: str(Path("~/obsidian-vault").expanduser()), description="Path to Obsidian vault")
    remarkable: str = Field(default="/dev/ttyUSB0", description="Path to reMarkable connection")

class UIConfig(BaseModel):
    theme: str = Field(default="dark", description="UI Theme")
    latex: bool = Field(default=True, description="Render LaTeX in terminal")
    plots: str = Field(default="terminal", description="Where to render plots: terminal or file")

class PitagoraConfig(BaseModel):
    providers: ProvidersConfig = Field(default_factory=ProvidersConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    math: MathConfig = Field(default_factory=MathConfig)
    mcp: MCPConfig = Field(default_factory=MCPConfig)
    ui: UIConfig = Field(default_factory=UIConfig)
    model: str = Field(default="", description="Default model override")
    features: dict = Field(default_factory=dict, description="Feature flags")

def get_default_config() -> PitagoraConfig:
    return PitagoraConfig()

def ensure_config_dir() -> None:
    if not CONFIG_DIR.exists():
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)

def load_config() -> PitagoraConfig:
    ensure_config_dir()
    if not CONFIG_PATH.exists():
        config = get_default_config()
        save_config(config)
        return config
    try:
        with open(CONFIG_PATH, "r") as f:
            data = yaml.safe_load(f) or {}
        return PitagoraConfig(**data)
    except Exception as e:
        # Fallback to default config on load error
        log.warning("Failed to load config from %s: %s", CONFIG_PATH, e)
        return get_default_config()

def save_config(config: PitagoraConfig) -> None:
    ensure_config_dir()
    # Serialize config using Pydantic v2's model_dump
    data = config.model_dump()
    with open(CONFIG_PATH, "w") as f:
        yaml.safe_dump(data, f, default_flow_style=False)
