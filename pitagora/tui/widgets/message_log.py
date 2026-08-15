"""MessageLogWidget: scrollable conversation log."""

from textual.reactive import reactive
from textual.widgets import Static


class MessageLogWidget(Static):
    messages: reactive[list] = reactive(list)

    def render(self) -> str:
        if not self.messages:
            return "No messages yet. Type input below."
        lines = []
        for msg in self.messages[-50:]:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            lines.append(f"[{role.upper()}]: {content}\n")
        return "\n".join(lines)
