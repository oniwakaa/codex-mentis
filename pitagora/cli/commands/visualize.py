from pathlib import Path

import numpy as np
import sympy as sp
import typer

from pitagora.cli.rich_ui import create_spinner, print_plot

app = typer.Typer(help="Visualize mathematical expressions and functions")


@app.command("plot")
def plot_expression(
    expression: str = typer.Argument(
        ..., help="Mathematical expression to plot (e.g. 'sin(x) * exp(-0.2*x)')"
    ),
    x_range: tuple[float, float] = typer.Option(
        (0.0, 10.0), "--range", "-r", help="Min and Max bounds for independent variable"
    ),
    plot_type: str = typer.Option(
        "function", "--type", "-t", help="Plot type (function/scatter/parametric)"
    ),
    save_path: Path | None = typer.Option(
        None, "--save", "-s", help="Path to save the plot as an image (PNG/PDF)"
    ),
):
    """Renders a function plot in the terminal or saves it as a graphic file."""
    typer.echo(f"Visualizing expression '{expression}' over range {x_range}...")

    xmin, xmax = x_range
    x_vals = np.linspace(xmin, xmax, 200)

    try:
        with create_spinner("Generating numerical coordinates..."):
            if plot_type == "parametric":
                # Expecting format "f(t), g(t)"
                parts = expression.split(",")
                if len(parts) != 2:
                    typer.echo(
                        "Error: Parametric plots require x and y expressions separated by a comma (e.g. 'cos(t), sin(t)')."
                    )
                    raise typer.Exit(1)

                t_sym = sp.Symbol("t")
                expr_x = sp.sympify(parts[0].strip())
                expr_y = sp.sympify(parts[1].strip())

                f_x = sp.lambdify(t_sym, expr_x, "numpy")
                f_y = sp.lambdify(t_sym, expr_y, "numpy")

                # Evaluate
                x_coords = np.array(f_x(x_vals), dtype=float)
                y_coords = np.array(f_y(x_vals), dtype=float)

                title = f"Parametric: x={parts[0].strip()}, y={parts[1].strip()}"
                xlabel = "x(t)"
                ylabel = "y(t)"
            else:
                # Standard function y = f(x)
                x_sym = sp.Symbol("x")
                expr = sp.sympify(expression)
                f_y = sp.lambdify(x_sym, expr, "numpy")

                x_coords = x_vals
                y_coords = np.array(f_y(x_vals), dtype=float)

                title = f"y = {expression}"
                xlabel = "x"
                ylabel = "y"

    except Exception as e:
        typer.echo(f"Error evaluating expression: {e}")
        raise typer.Exit(1)

    # Render in terminal
    print_plot(
        x=x_coords.tolist(),
        y=y_coords.tolist(),
        title=title,
        xlabel=xlabel,
        ylabel=ylabel,
        plot_type=plot_type,
        x_range=x_range if plot_type != "parametric" else None,
    )

    # Save to file if requested using matplotlib
    if save_path:
        try:
            import matplotlib.pyplot as plt

            plt.figure(figsize=(8, 5))
            if plot_type == "scatter":
                plt.scatter(x_coords, y_coords, label=title, color="blue", alpha=0.7)
            else:
                plt.plot(x_coords, y_coords, label=title, color="blue", linewidth=2)

            plt.title(title)
            plt.xlabel(xlabel)
            plt.ylabel(ylabel)
            plt.grid(True, linestyle="--", alpha=0.5)
            plt.legend()
            plt.savefig(save_path, dpi=150)
            plt.close()
            typer.echo(f"Successfully saved plot image to {save_path}")
        except Exception as e:
            typer.echo(f"Failed to save image via Matplotlib: {e}")
