"""MessageLogWidget: modernized scrollable conversation log with Rich markdown and LaTeX cards."""

from typing import Any

from rich.console import Group, RenderableType
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static

from pitagora.latex_render import format_math_in_markdown, render_equation_box


class MessageLogWidget(Static):
    """Scrollable conversation stream with role badges, markdown cards, and math rendering."""

    messages: reactive[list] = reactive(list)
    search_term: reactive[str] = reactive("")
    scroll_locked: reactive[bool] = reactive(False)

    def on_mount(self) -> None:
        self.scroll_end(animate=False)

    def watch_messages(self, old_val: list, new_val: list) -> None:
        """Auto-scroll to the bottom when new message chunks arrive unless user scrolled up."""
        if not self.scroll_locked:
            self.scroll_end(animate=False)

    def scroll_up_lines(self, n: int = 3) -> None:
        self.scroll_locked = True
        try:
            self.scroll_relative(y=-n, animate=False)
        except Exception:
            self.scroll_up(animate=False)

    def scroll_down_lines(self, n: int = 3) -> None:
        try:
            self.scroll_relative(y=n, animate=False)
        except Exception:
            self.scroll_down(animate=False)

    def page_up(self) -> None:
        self.scroll_locked = True
        self.scroll_page_up(animate=False)

    def page_down(self) -> None:
        self.scroll_page_down(animate=False)

    def scroll_to_top(self) -> None:
        self.scroll_locked = True
        self.scroll_home(animate=False)

    def scroll_to_bottom(self) -> None:
        self.scroll_locked = False
        self.scroll_end(animate=False)

    def unlock_scroll(self) -> None:
        self.scroll_locked = False
        self.scroll_end(animate=False)



    def search_buffer(self, term: str) -> None:
        self.search_term = term.strip()

    def _render_message_card(self, msg: dict[str, Any], idx: int) -> RenderableType:
        role = str(msg.get("role", "unknown")).lower()
        raw_content = str(msg.get("content", ""))
        metadata = msg.get("metadata", {})

        # Filter if search term is active
        if self.search_term and self.search_term.lower() not in raw_content.lower():
            return Text("")

        if role == "user":
            header = Text.assemble(
                ("👤 ", "bold #89b4fa"),
                ("YOU", "bold #89b4fa"),
                ("  ", "dim"),
                ("• question", "dim #6c7086"),
            )
            content_renderable = Text(raw_content, style="#cdd6f4")
            return Panel(
                content_renderable,
                title=header,
                title_align="left",
                border_style="#89b4fa",
                padding=(0, 1),
            )

        elif role in ("assistant", "agent"):
            header = Text.assemble(
                ("🧠 ", "bold #a6e3a1"),
                ("PITAGORA", "bold #a6e3a1"),
                ("  ", "dim"),
                ("• response", "dim #6c7086"),
            )
            # Process LaTeX inside markdown
            formatted_text = format_math_in_markdown(raw_content)
            try:
                content_renderable: RenderableType = Markdown(formatted_text, code_theme="nord")
            except Exception:
                content_renderable = Text(raw_content, style="#cdd6f4")

            return Panel(
                content_renderable,
                title=header,
                title_align="left",
                border_style="#a6e3a1",
                padding=(0, 1),
            )

        elif role == "system":
            is_verification = metadata.get("verification", False) or "verif" in raw_content.lower()
            is_busy = metadata.get("busy", False) or "thinking" in raw_content.lower()

            if is_verification:
                header = Text.assemble(
                    ("⚙️ ", "bold #cba6f7"),
                    ("SYMPY VERIFICATION", "bold #cba6f7"),
                )
                formatted_math = format_math_in_markdown(raw_content)
                return Panel(
                    Text(formatted_math, style="#cba6f7"),
                    title=header,
                    title_align="left",
                    border_style="#cba6f7",
                    padding=(0, 1),
                )
            elif is_busy:
                return Text.assemble(
                    ("  ⏳ ", "bold #f9e2af"),
                    (raw_content, "italic #f9e2af"),
                )
            else:
                header = Text.assemble(
                    ("ℹ️ ", "bold #fab387"),
                    ("SYSTEM", "bold #fab387"),
                )
                return Panel(
                    Text(raw_content, style="#fab387"),
                    title=header,
                    title_align="left",
                    border_style="#fab387",
                    padding=(0, 1),
                )

        elif role in ("error", "err"):
            header = Text.assemble(
                ("❌ ", "bold #f38ba8"),
                ("ERROR", "bold #f38ba8"),
            )
            return Panel(
                Text(raw_content, style="#f38ba8"),
                title=header,
                title_align="left",
                border_style="#f38ba8",
                padding=(0, 1),
            )

        elif role == "plot":
            plot_data = metadata.get("plot_data", {})
            title = plot_data.get("title", raw_content or "Interactive Visual Plot")
            from pitagora.latex_render import latex_to_unicode
            rendered_title = latex_to_unicode(title)

            header = Text.assemble(
                ("📊 ", "bold #7aa2f7"),
                (f"PLOT: {rendered_title}", "bold #7aa2f7"),
                ("  ", "dim"),
                ("• visual model", "dim #6c7086"),
            )

            # Build HD braille plot representation
            plot_renderable: RenderableType
            try:
                import plotext as plt

                plt.clf()
                plt.theme("dark")
                plt.grid(True, True)
                plt.plotsize(72, 16)
                plt.title(rendered_title)
                plt.xlabel(latex_to_unicode(plot_data.get("x_label", "x")))
                plt.ylabel(latex_to_unicode(plot_data.get("y_label", "y")))

                series = plot_data.get("series", [])
                colors = ["cyan", "magenta", "blue", "green", "yellow", "red"]
                plot_type = str(plot_data.get("plot_type", "line")).lower()

                for idx, s in enumerate(series):
                    x = s.get("x", [])
                    y = s.get("y", [])
                    raw_name = s.get("name", f"Series {idx+1}")
                    name = latex_to_unicode(raw_name)
                    color = colors[idx % len(colors)]
                    if plot_type == "scatter":
                        plt.scatter(x, y, label=name, color=color, marker="braille")
                    elif plot_type == "bar":
                        plt.bar(x, y, label=name, color=color)
                    else:
                        plt.plot(x, y, label=name, color=color, marker="braille")

                plot_ansi = plt.build()
                plot_renderable = Text.from_ansi(plot_ansi)
            except Exception as e:
                plot_renderable = Text(f"[Visual plot rendering error: {e}]", style="#f38ba8")

            math_formula = plot_data.get("math_formula", "")
            panel_content: list[RenderableType] = []
            if math_formula:
                formula_rendered = latex_to_unicode(math_formula)
                panel_content.append(Text(f"📐 Formula: {formula_rendered}\n", style="italic #bb9af7"))
            panel_content.append(plot_renderable)

            return Panel(
                Group(*panel_content),
                title=header,
                title_align="left",
                border_style="#7aa2f7",
                padding=(0, 1),
            )

        elif role == "reasoning":
            header = Text.assemble(
                ("💭 ", "dim #f9e2af"),
                ("THINKING TRACE", "dim #f9e2af"),
            )
            return Panel(
                Text(raw_content, style="dim #bac2de"),
                title=header,
                title_align="left",
                border_style="#585b70",
                padding=(0, 1),
            )

        else:
            return Text(f"[{role.upper()}]: {raw_content}\n", style="#cdd6f4")

    def render(self) -> RenderableType:
        if not self.messages:
            empty_table = Table.grid(expand=True)
            empty_table.add_column(justify="center")
            empty_table.add_row(
                Text.assemble(
                    ("\n\n✨ ", "bold #89b4fa"),
                    ("Welcome to Pitagora TUI", "bold #cdd6f4"),
                    ("\n\nType a math or physics question below, or use ", "dim #a6adc8"),
                    ("/", "bold #89b4fa"),
                    (" for slash commands.\n\n", "dim #a6adc8"),
                )
            )
            return empty_table

        cards: list[RenderableType] = []
        for idx, msg in enumerate(self.messages[-50:]):
            card = self._render_message_card(msg, idx)
            cards.append(card)

        return Group(*cards)

