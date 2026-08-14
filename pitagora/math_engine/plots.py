import matplotlib.pyplot as mplt
import numpy as np
import plotext as plt
import sympy as sp


class MathPlotter:
    def __init__(self):
        self._last_fig: mplt.Figure | None = None

    def _create_matplotlib_fig(self) -> tuple[mplt.Figure, mplt.Axes]:
        fig, ax = mplt.subplots(figsize=(8, 6))
        self._last_fig = fig
        return fig, ax

    def save_plot(self, filename: str) -> None:
        """Saves the last generated matplotlib figure to a file."""
        if self._last_fig is not None:
            self._last_fig.savefig(filename, dpi=300, bbox_inches="tight")
            mplt.close(self._last_fig)
        else:
            raise ValueError("No plot has been generated yet to save.")

    def plot_function(
        self, expr: str, x_range: tuple[float, float], title: str = "Function Plot"
    ) -> None:
        """Plots a single-variable function in the terminal and prepares matplotlib figure."""
        x_sym = sp.Symbol("x")
        parsed_expr = sp.sympify(expr)
        f_lambdified = sp.lambdify(x_sym, parsed_expr, modules=["numpy", "sympy"])

        x_vals = np.linspace(x_range[0], x_range[1], 100)
        y_vals = []
        for x in x_vals:
            try:
                y_vals.append(float(f_lambdified(x)))
            except Exception:
                y_vals.append(float("nan"))

        # Terminal plotext plot
        plt.clf()
        # Filter out NaN for plotext to avoid plotting issues
        x_plt = [x for x, y in zip(x_vals, y_vals, strict=False) if not np.isnan(y)]
        y_plt = [y for y in y_vals if not np.isnan(y)]

        plt.plot(x_plt, y_plt)
        plt.title(title)
        plt.xlabel("x")
        plt.ylabel("y")
        plt.show()

        # Matplotlib plot
        fig, ax = self._create_matplotlib_fig()
        ax.plot(x_vals, y_vals, label=f"y = {expr}")
        ax.axhline(0, color="black", linewidth=0.5, ls="--")
        ax.axvline(0, color="black", linewidth=0.5, ls="--")
        ax.grid(True, which="both", linestyle=":", alpha=0.5)
        ax.set_title(title)
        ax.set_xlabel("x")
        ax.set_ylabel("y")
        ax.legend()

    def plot_parametric(
        self, x_expr: str, y_expr: str, t_range: tuple[float, float], title: str = "Parametric Plot"
    ) -> None:
        """Plots a parametric curve (x(t), y(t)) in terminal and prepares matplotlib figure."""
        t_sym = sp.Symbol("t")
        x_parsed = sp.sympify(x_expr)
        y_parsed = sp.sympify(y_expr)

        x_lamb = sp.lambdify(t_sym, x_parsed, modules=["numpy", "sympy"])
        y_lamb = sp.lambdify(t_sym, y_parsed, modules=["numpy", "sympy"])

        t_vals = np.linspace(t_range[0], t_range[1], 200)
        x_vals = []
        y_vals = []

        for t in t_vals:
            try:
                x_vals.append(float(x_lamb(t)))
                y_vals.append(float(y_lamb(t)))
            except Exception:
                x_vals.append(float("nan"))
                y_vals.append(float("nan"))

        # Filter NaNs
        clean_x = []
        clean_y = []
        for x, y in zip(x_vals, y_vals, strict=False):
            if not np.isnan(x) and not np.isnan(y):
                clean_x.append(x)
                clean_y.append(y)

        # Terminal Plot
        plt.clf()
        plt.plot(clean_x, clean_y)
        plt.title(title)
        plt.xlabel("x(t)")
        plt.ylabel("y(t)")
        plt.show()

        # Matplotlib Plot
        fig, ax = self._create_matplotlib_fig()
        ax.plot(x_vals, y_vals, label=f"r(t) = ({x_expr}, {y_expr})")
        ax.axhline(0, color="black", linewidth=0.5, ls="--")
        ax.axvline(0, color="black", linewidth=0.5, ls="--")
        ax.grid(True, which="both", linestyle=":", alpha=0.5)
        ax.set_title(title)
        ax.set_xlabel("x")
        ax.set_ylabel("y")
        ax.legend()

    def plot_vector_field(
        self,
        Fx_expr: str,
        Fy_expr: str,
        x_range: tuple[float, float],
        y_range: tuple[float, float],
        title: str = "Vector Field",
    ) -> None:
        """Plots a 2D vector field in the terminal and prepares matplotlib figure."""
        x_sym, y_sym = sp.symbols("x y")
        Fx_parsed = sp.sympify(Fx_expr)
        Fy_parsed = sp.sympify(Fy_expr)

        Fx_lamb = sp.lambdify((x_sym, y_sym), Fx_parsed, modules=["numpy", "sympy"])
        Fy_lamb = sp.lambdify((x_sym, y_sym), Fy_parsed, modules=["numpy", "sympy"])

        # Grid for evaluation
        # Terminal representation is simpler
        x_grid_plt = np.linspace(x_range[0], x_range[1], 15)
        y_grid_plt = np.linspace(y_range[0], y_range[1], 15)

        plt.clf()
        plt.title(title)

        # In terminal, we represent the vector field using a scatter plot of grid points
        # and short lines indicating flow directions
        for x in x_grid_plt:
            for y in y_grid_plt:
                try:
                    dx = float(Fx_lamb(x, y))
                    dy = float(Fy_lamb(x, y))

                    mag = np.hypot(dx, dy)
                    if mag > 1e-5:
                        # Normalize vector to a short length for terminal display
                        dx_norm = 0.5 * (x_range[1] - x_range[0]) / 15 * (dx / mag)
                        dy_norm = 0.5 * (y_range[1] - y_range[0]) / 15 * (dy / mag)
                        plt.plot([x, x + dx_norm], [y, y + dy_norm])
                except Exception:
                    continue
        plt.xlabel("x")
        plt.ylabel("y")
        plt.show()

        # Matplotlib Plot
        fig, ax = self._create_matplotlib_fig()
        X, Y = np.meshgrid(
            np.linspace(x_range[0], x_range[1], 20), np.linspace(y_range[0], y_range[1], 20)
        )

        # Vector field evaluation
        U = np.zeros_like(X)
        V = np.zeros_like(Y)
        for i in range(X.shape[0]):
            for j in range(X.shape[1]):
                try:
                    U[i, j] = float(Fx_lamb(X[i, j], Y[i, j]))
                    V[i, j] = float(Fy_lamb(X[i, j], Y[i, j]))
                except Exception:
                    U[i, j] = 0.0
                    V[i, j] = 0.0

        ax.quiver(X, Y, U, V, color="blue", pivot="mid")
        ax.grid(True, linestyle=":", alpha=0.5)
        ax.set_title(title)
        ax.set_xlabel("x")
        ax.set_ylabel("y")

    def plot_surface(
        self,
        expr: str,
        x_range: tuple[float, float],
        y_range: tuple[float, float],
        title: str = "Surface Plot",
    ) -> None:
        """Plots a 3D surface z = f(x, y) projected as 2D heatmap in terminal, and 3D surface in Matplotlib."""
        x_sym, y_sym = sp.symbols("x y")
        parsed = sp.sympify(expr)
        f_lambdified = sp.lambdify((x_sym, y_sym), parsed, modules=["numpy", "sympy"])

        # 2D Heatmap / contour in plotext
        x_vals = np.linspace(x_range[0], x_range[1], 30)
        y_vals = np.linspace(y_range[0], y_range[1], 30)

        # Generate matrix of values
        Z_grid = []
        for y in y_vals:
            row = []
            for x in x_vals:
                try:
                    row.append(float(f_lambdified(x, y)))
                except Exception:
                    row.append(0.0)
            Z_grid.append(row)

        plt.clf()
        # Plotext has a heatmap function in newer versions.
        # If it fails, we fall back to a 3D scatter projection
        try:
            plt.matrix_plot(Z_grid)
        except Exception:
            # Fallback to scatter plot representing height as a projection
            proj_x = []
            proj_y = []
            for _i, y in enumerate(y_vals):
                for _j, x in enumerate(x_vals):
                    proj_x.append(x)
                    proj_y.append(y)
            plt.scatter(proj_x, proj_y)

        plt.title(f"{title} (Terminal Heatmap/Grid)")
        plt.xlabel("x")
        plt.ylabel("y")
        plt.show()

        # Matplotlib 3D Surface Plot
        fig = mplt.figure(figsize=(10, 8))
        self._last_fig = fig
        ax = fig.add_subplot(111, projection="3d")

        X_mat, Y_mat = np.meshgrid(x_vals, y_vals)
        Z_mat = np.zeros_like(X_mat)
        for i in range(X_mat.shape[0]):
            for j in range(X_mat.shape[1]):
                try:
                    Z_mat[i, j] = float(f_lambdified(X_mat[i, j], Y_mat[i, j]))
                except Exception:
                    Z_mat[i, j] = np.nan

        surf = ax.plot_surface(X_mat, Y_mat, Z_mat, cmap="viridis", edgecolor="none", alpha=0.8)
        fig.colorbar(surf, ax=ax, shrink=0.5, aspect=5)
        ax.set_title(title)
        ax.set_xlabel("x")
        ax.set_ylabel("y")
        ax.set_zlabel("z")

    def plot_scatter(
        self, x_data: list[float], y_data: list[float], title: str = "Scatter Plot"
    ) -> None:
        """Plots scatter data in terminal and prepares matplotlib figure."""
        plt.clf()
        plt.scatter(x_data, y_data)
        plt.title(title)
        plt.xlabel("x")
        plt.ylabel("y")
        plt.show()

        # Matplotlib Plot
        fig, ax = self._create_matplotlib_fig()
        ax.scatter(x_data, y_data, color="red", alpha=0.7, label="Data points")
        ax.grid(True, linestyle=":", alpha=0.5)
        ax.set_title(title)
        ax.set_xlabel("x")
        ax.set_ylabel("y")
        ax.legend()
