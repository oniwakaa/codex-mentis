import pytest
import os
import yaml
from pathlib import Path
from codex_mentis.core import config as core_config
from codex_mentis.core.config import (
    get_default_config,
    load_config,
    save_config,
    CodexMentisConfig
)

@pytest.fixture(autouse=True)
def mock_config_paths(tmp_path, monkeypatch):
    # Override CONFIG_DIR and CONFIG_PATH in core_config
    mock_dir = tmp_path / ".codex-mentis"
    mock_path = mock_dir / "config.yaml"
    
    monkeypatch.setattr(core_config, "CONFIG_DIR", mock_dir)
    monkeypatch.setattr(core_config, "CONFIG_PATH", mock_path)
    return mock_dir, mock_path

def test_config_defaults():
    cfg = get_default_config()
    assert cfg.providers.default == "gemini"
    assert cfg.memory.spaced_repetition is True
    assert cfg.ui.theme == "dark"

def test_save_and_load_config():
    cfg = get_default_config()
    cfg.providers.default = "custom-provider"
    cfg.ui.theme = "light"
    
    save_config(cfg)
    
    # Reload config
    loaded = load_config()
    assert loaded.providers.default == "custom-provider"
    assert loaded.ui.theme == "light"

def test_load_corrupted_config(tmp_path):
    # Write corrupted/invalid YAML to config file path
    config_file = core_config.CONFIG_PATH
    os.makedirs(os.path.dirname(config_file), exist_ok=True)
    with open(config_file, "w") as f:
        f.write("providers: invalid_syntax: : :")
        
    # Should fall back to default config without raising an exception
    loaded = load_config()
    assert loaded.providers.default == "gemini"
