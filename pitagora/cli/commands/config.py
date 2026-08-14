import typer

from pitagora.cli.rich_ui import print_table
from pitagora.core.config import CONFIG_PATH, get_default_config, load_config, save_config

app = typer.Typer(help="Manage Pitagora configuration")


@app.command("show")
def show_config():
    """Display the current configuration settings."""
    config = load_config()
    data = config.model_dump()

    headers = ["Section", "Key", "Value"]
    rows = []
    for section, values in data.items():
        if isinstance(values, dict):
            for key, value in values.items():
                rows.append([section, key, str(value)])
        else:
            rows.append(["(top-level)", section, str(values)])

    print_table(headers, rows, title=f"Configuration Settings (from {CONFIG_PATH})")


@app.command("set")
def set_config(
    key_path: str = typer.Argument(..., help="Path to setting (e.g., providers.default or model)"),
    value: str = typer.Argument(..., help="New value for the setting"),
):
    """Set a configuration value."""
    config = load_config()
    parts = key_path.split(".")

    if len(parts) == 1:
        # Top-level scalar field (e.g., model)
        section = parts[0]
        if not hasattr(config, section):
            typer.echo(f"Error: Field '{section}' does not exist.")
            raise typer.Exit(1)
        current_val = getattr(config, section)
        try:
            if isinstance(current_val, bool):
                parsed_val = value.lower() in ("true", "1", "yes")
            elif isinstance(current_val, int):
                parsed_val = int(value)
            elif isinstance(current_val, list):
                parsed_val = [x.strip() for x in value.split(",")]
            else:
                parsed_val = value
            setattr(config, section, parsed_val)
            save_config(config)
            typer.echo(f"Successfully set {key_path} to {parsed_val}")
        except Exception as e:
            typer.echo(f"Error converting/setting value: {e}")
            raise typer.Exit(1)
        return

    if len(parts) != 2:
        typer.echo("Error: Key path must be 'section.key' or a top-level field name.")
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
            parsed_val = value.lower() in ("true", "1", "yes")
        elif isinstance(current_val, int):
            parsed_val = int(value)
        elif isinstance(current_val, list):
            parsed_val = [x.strip() for x in value.split(",")]
        else:
            parsed_val = value

        setattr(sub_config, key, parsed_val)
        save_config(config)
        typer.echo(f"Successfully set {key_path} to {parsed_val}")
    except Exception as e:
        typer.echo(f"Error converting/setting value: {e}")
        raise typer.Exit(1)


@app.command("init")
def init_config(
    force: bool = typer.Option(False, "--force", "-f", help="Force overwrite if file exists")
):
    """Initialize a default configuration file."""
    if CONFIG_PATH.exists() and not force:
        typer.echo(f"Config file already exists at {CONFIG_PATH}. Use --force to overwrite.")
        raise typer.Exit(1)

    config = get_default_config()
    save_config(config)
    typer.echo(f"Initialized default configuration at {CONFIG_PATH}")
