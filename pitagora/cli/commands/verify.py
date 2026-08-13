import typer
import sympy as sp
from pitagora.cli.rich_ui import print_panel, print_math, create_spinner

app = typer.Typer(help="Verify a mathematical claim symbolically using SymPy")

@app.command()
def verify(
    claim: str = typer.Argument(..., help="Mathematical claim to verify (e.g. 'sin(x)**2 + cos(x)**2 = 1')")
):
    """Verify a mathematical equation or equality symbolically."""
    typer.echo(f"Reviewer Agent analyzing claim: '{claim}'...")
    
    with create_spinner("Parsing symbols and running algebraic simplification...") as status:
        if "=" not in claim:
            # Maybe just evaluate or simplify expression
            try:
                expr = sp.sympify(claim)
                simplified = sp.simplify(expr)
                status.update("Simplifying expression...")
                print_panel(
                    f"Parsed Expression: {expr}\nSimplified: {simplified}", 
                    "Expression Analysis", 
                    style="cyan"
                )
                return
            except Exception as e:
                typer.echo(f"Error parsing expression: {e}")
                raise typer.Exit(1)
                
        parts = claim.split("=")
        if len(parts) != 2:
            typer.echo("Error: Claim must have exactly one '=' sign for equations.")
            raise typer.Exit(1)
            
        lhs_str, rhs_str = parts

        try:
            lhs = sp.sympify(lhs_str)
            rhs = sp.sympify(rhs_str)
            
            diff = sp.simplify(lhs - rhs)
            
            is_valid = (diff == 0)
        except Exception as e:
            typer.echo(f"Error parsing claim symbols: {e}")
            raise typer.Exit(1)
            
    if is_valid:
        content = (
            f"[bold green]Claim is TRUE.[/bold green]\n\n"
            f"[bold]LHS:[/bold] {lhs}\n"
            f"[bold]RHS:[/bold] {rhs}\n"
            f"[bold]Difference (LHS - RHS):[/bold] {diff}\n\n"
            f"Confidence score: [bold green]1.00[/bold green] (Verified via SymPy Sandbox)"
        )
        print_panel(content, "Verification Result: VALID", style="green")
        print_math(claim)
    else:
        content = (
            f"[bold red]Claim is UNVERIFIED or FALSE.[/bold red]\n\n"
            f"[bold]LHS:[/bold] {lhs}\n"
            f"[bold]RHS:[/bold] {rhs}\n"
            f"[bold]Difference (LHS - RHS) simplified to:[/bold] {diff} (expected 0)\n\n"
            f"Confidence score: [bold red]0.00[/bold red] (Failed symbolic check)"
        )
        print_panel(content, "Verification Result: INVALID", style="red")
        print_math(claim)
