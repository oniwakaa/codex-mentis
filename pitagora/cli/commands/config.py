import typer
from pitagora.core.config import load_config, save_config, get_default_config, CONFIG_PATH
from pitagora.cli.rich_ui import print_panel, print_table

app = typer.Typer(help="Manage Pitagora configuration")

@app.command("show")
def show_config():
    """Display the current configuration settings."""
    config = load_config()
    data = config.model_dump()
    
    headers = ["Section", "Key", "Value"]
    rows = []
    for section, values in data.items():
        for key, value in values.items():
            rows.append([section, key, str(value)])
            
    print_table(headers, rows, title=f"Configuration Settings (from {CONFIG_PATH})")

@app.command("set")
def set_config(key_path: str = typer.Argument(..., help="Path to setting (e.g., providers.default)"), value: str = typer.Argument(..., help="New value for the setting")):
    """Set a configuration value."""
    config = load_config()
    parts = key_path.split(".")
    
    if len(parts) != 2:
        typer.echo("Error: Key path must be in 'section.key' format (e.g., providers.default).")
        raise typer.Exit(1)
        
    section, key = parts
    
    if not hasattr(config, section):
        typer.echo(f"Error: Section '{section}' does not exist.")
        raise typer.Exit(1)
        
    sub_config = getattr(config, section)
    if not hasattr(sub_config, key):
        typer.echo(f"Error: Key '{key}' does not exist in section '{section}'.")
        raise typer.Exit(1)
        
    # Cast value depending on field type
    current_val = getattr(sub_config, key)
    try:
        if isinstance(current_val, bool):
            # Parse boolean
            parsed_val = value.lower() in ("true", "1", "yes")
        elif isinstance(current_val, int):
            parsed_val = int(value)
        elif isinstance(current_val, list):
            # assume list of strings split by comma
            parsed_val = [x.strip() for x in value.split(",")]
        else:
            parsed_val = value
            
        setattr(sub_config, key, parsed_val)
        save_config(config)
        typer.echo(f"Successfully set {key_path} to {parsed_val}")
    except Exception as e:
        typer.echo(f"Error converting/setting value: {e}")

@app.command("init")
def init_config(force: bool = typer.Option(False, "--force", "-f", help="Force overwrite if file exists")):
    """Initialize a default configuration file."""
    if CONFIG_PATH.exists() and not force:
        typer.echo(f"Config file already exists at {CONFIG_PATH}. Use --force to overwrite.")
        raise typer.Exit(1)
        
    config = get_default_config()
    save_config(config)
    typer.echo(f"Initialized default configuration at {CONFIG_PATH}")
