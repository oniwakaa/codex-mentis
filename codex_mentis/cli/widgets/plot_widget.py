import math
import numpy as np
from typing import Optional, Tuple
from textual.widget import Widget
from textual.message import Message
from rich.text import Text

class PlotBoundsChanged(Message):
    """Event fired when plotting viewport bounds change."""
    def __init__(self, x_min: float, x_max: float, y_min: float, y_max: float) -> None:
        super().__init__()
        self.x_min = x_min
        self.x_max = x_max
        self.y_min = y_min
        self.y_max = y_max

class PlotWidget(Widget):
    """
    An interactive plot widget using Textual canvas rendering.
    Supports zooming (scroll wheel / +/- keys) and panning (mouse drag / arrow keys).
    """
    
    DEFAULT_CSS = """
    PlotWidget {
        width: 100%;
        height: 100%;
        background: $background;
        border: solid $accent;
        color: $text;
    }
    PlotWidget:focus {
        border: solid $primary;
    }
    """

    BINDINGS = [
        ("up", "pan_up", "Pan Up"),
        ("down", "pan_down", "Pan Down"),
        ("left", "pan_left", "Pan Left"),
        ("right", "pan_right", "Pan Right"),
        ("plus", "zoom_in", "Zoom In"),
        ("minus", "zoom_out", "Zoom Out"),
        ("r", "reset_view", "Reset View"),
    ]

    def __init__(self, expr: str = "x**2", **kwargs):
        super().__init__(**kwargs)
        self.can_focus = True
        self.expr = expr
        
        # Viewport bounds
        self.x_min = -5.0
        self.x_max = 5.0
        self.y_min = -5.0
        self.y_max = 5.0
        
        # Interaction state
        self.dragging = False
        self.last_mouse_x = 0
        self.last_mouse_y = 0

    def set_expression(self, expr: str) -> None:
        """Updates the mathematical expression to plot."""
        self.expr = expr
        # Auto-reset zoom/pan to defaults based on expression
        self.reset_view()

    def reset_view(self) -> None:
        self.x_min = -5.0
        self.x_max = 5.0
        self.y_min = -5.0
        self.y_max = 5.0
        self.refresh()

    def action_pan_up(self) -> None:
        dy = (self.y_max - self.y_min) * 0.1
        self.y_min += dy
        self.y_max += dy
        self.refresh()

    def action_pan_down(self) -> None:
        dy = (self.y_max - self.y_min) * 0.1
        self.y_min -= dy
        self.y_max -= dy
        self.refresh()

    def action_pan_left(self) -> None:
        dx = (self.x_max - self.x_min) * 0.1
        self.x_min -= dx
        self.x_max -= dx
        self.refresh()

    def action_pan_right(self) -> None:
        dx = (self.x_max - self.x_min) * 0.1
        self.x_min += dx
        self.x_max += dx
        self.refresh()

    def action_zoom_in(self) -> None:
        self._zoom(0.8)

    def action_zoom_out(self) -> None:
        self._zoom(1.2)

    def _zoom(self, factor: float) -> None:
        x_center = (self.x_min + self.x_max) / 2.0
        y_center = (self.y_min + self.y_max) / 2.0
        
        x_half = (self.x_max - self.x_min) * factor / 2.0
        y_half = (self.y_max - self.y_min) * factor / 2.0
        
        self.x_min = x_center - x_half
        self.x_max = x_center + x_half
        self.y_min = y_center - y_half
        self.y_max = y_center + y_half
        self.refresh()

    def on_mouse_down(self, event) -> None:
        self.dragging = True
        self.last_mouse_x = event.x
        self.last_mouse_y = event.y
        self.capture_mouse()

    def on_mouse_up(self, event) -> None:
        self.dragging = False
        self.release_mouse()

    def on_mouse_move(self, event) -> None:
        if self.dragging:
            width = self.size.width or 1
            height = self.size.height or 1
            
            dx_cells = event.x - self.last_mouse_x
            dy_cells = event.y - self.last_mouse_y
            
            # Map grid cells delta to math coordinate space delta
            dx_coords = dx_cells * (self.x_max - self.x_min) / width
            dy_coords = dy_cells * (self.y_max - self.y_min) / height
            
            self.x_min -= dx_coords
            self.x_max -= dx_coords
            self.y_min += dy_coords
            self.y_max += dy_coords
            
            self.last_mouse_x = event.x
            self.last_mouse_y = event.y
            self.refresh()

    def on_mouse_scroll(self, event) -> None:
        if event.direction == "up" or event.delta_y < 0:
            self._zoom(0.9)
        else:
            self._zoom(1.1)

    def render(self) -> Text:
        width = self.size.width
        height = self.size.height
        
        if width < 5 or height < 5:
            return Text("Plot pane too small", style="yellow")

        # Reserve some rows/cols for axes labels
        plot_w = width - 8
        plot_h = height - 2
        
        if plot_w <= 0 or plot_h <= 0:
            return Text("Plot pane too small", style="yellow")
            
        # Create character canvas
        canvas = [[" " for _ in range(plot_w)] for _ in range(plot_h)]
        
        # 1. Draw axes
        # Find column corresponding to x=0
        if self.x_min <= 0 <= self.x_max:
            zero_col = int((0 - self.x_min) / (self.x_max - self.x_min) * (plot_w - 1))
            for r in range(plot_h):
                canvas[r][zero_col] = "│"
                
        # Find row corresponding to y=0 (y increases upwards, so row 0 is y_max)
        if self.y_min <= 0 <= self.y_max:
            zero_row = int((self.y_max - 0) / (self.y_max - self.y_min) * (plot_h - 1))
            for c in range(plot_w):
                if canvas[zero_row][c] == "│":
                    canvas[zero_row][c] = "┼"
                else:
                    canvas[zero_row][c] = "─"

        # 2. Evaluate and plot expression
        x_vals = np.linspace(self.x_min, self.x_max, plot_w * 2) # double resolution for sub-pixel interpolation
        
        # Safe math dictionary for evaluation
        safe_dict = {
            "x": x_vals,
            "sin": np.sin,
            "cos": np.cos,
            "tan": np.tan,
            "exp": np.exp,
            "log": np.log,
            "sqrt": np.sqrt,
            "pi": np.pi,
            "e": np.e,
            "np": np
        }
        
        # Clean expression of common latex/sympy symbols
        expr_clean = (
            self.expr
            .replace("^", "**")
            .replace("sin", "np.sin")
            .replace("cos", "np.cos")
            .replace("tan", "np.tan")
            .replace("exp", "np.exp")
            .replace("log", "np.log")
            .replace("sqrt", "np.sqrt")
        )
        
        try:
            # Vectorized evaluation
            y_vals = eval(expr_clean, {"__builtins__": {}}, safe_dict)
            
            # Map evaluated coordinates to character matrix
            for i, x_val in enumerate(x_vals):
                y_val = y_vals[i]
                if np.isnan(y_val) or np.isinf(y_val):
                    continue
                    
                # Map x to column
                c_idx = int((x_val - self.x_min) / (self.x_max - self.x_min) * (plot_w - 1))
                # Map y to row
                r_idx = int((self.y_max - y_val) / (self.y_max - self.y_min) * (plot_h - 1))
                
                if 0 <= c_idx < plot_w and 0 <= r_idx < plot_h:
                    canvas[r_idx][c_idx] = "●"
        except Exception as e:
            # Render evaluation error on canvas
            error_msg = f"Plot Error: {str(e)[:40]}"
            start_col = max(0, (plot_w - len(error_msg)) // 2)
            for j, char in enumerate(error_msg):
                if start_col + j < plot_w:
                    canvas[plot_h // 2][start_col + j] = char

        # 3. Construct rich text rendering output with labels
        result = Text()
        
        # Upper Y label
        y_max_str = f"{self.y_max:7.2f} ┤"
        y_min_str = f"{self.y_min:7.2f} ┤"
        y_zero_str = "   0.00 ┼"
        
        for r in range(plot_h):
            # Left axis marker
            if r == 0:
                result.append(y_max_str, style="cyan")
            elif r == plot_h - 1:
                result.append(y_min_str, style="cyan")
            elif self.y_min <= 0 <= self.y_max and r == int((self.y_max - 0) / (self.y_max - self.y_min) * (plot_h - 1)):
                result.append(y_zero_str, style="cyan")
            else:
                result.append("        │", style="cyan")
                
            # Plot row content
            row_str = "".join(canvas[r])
            # Highlight mathematical plot characters
            row_text = Text(row_str)
            row_text.highlight_words(["●"], "bold green")
            result.append(row_text)
            result.append("\n")
            
        # Bottom X axis labels
        result.append("        └" + "─" * (plot_w) + "\n", style="cyan")
        
        # Center-spaced X bounds
        x_min_str = f"{self.x_min:.2f}"
        x_max_str = f"{self.x_max:.2f}"
        title_str = f" Plot: {self.expr} "
        
        spacer_width = plot_w - len(x_min_str) - len(x_max_str)
        if spacer_width > len(title_str) + 4:
            left_space = (spacer_width - len(title_str)) // 2
            right_space = spacer_width - len(title_str) - left_space
            x_labels = f"        {x_min_str}{' ' * left_space}{title_str}{' ' * right_space}{x_max_str}"
        else:
            x_labels = f"        {x_min_str}{' ' * spacer_width}{x_max_str}"
            
        result.append(x_labels, style="bold cyan")
        return result
