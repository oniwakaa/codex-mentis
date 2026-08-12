"""Obsidian vault integration for knowledge management."""
import os
import re
from pathlib import Path
from typing import List, Dict, Any, Optional


class ObsidianBridge:
    """Read/write to Obsidian vault for knowledge management."""

    def __init__(self, vault_path: str = "~/obsidian-vault"):
        self.vault_path = Path(os.path.expanduser(vault_path))

    def is_available(self) -> bool:
        return self.vault_path.exists() and self.vault_path.is_dir()

    def list_notes(self, folder: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """List notes in the vault."""
        if not self.is_available():
            return []

        search_dir = self.vault_path / folder if folder else self.vault_path
        notes = []
        for md_file in search_dir.rglob("*.md"):
            if len(notes) >= limit:
                break
            stat = md_file.stat()
            notes.append({
                "path": str(md_file.relative_to(self.vault_path)),
                "name": md_file.stem,
                "size": stat.st_size,
                "modified": stat.st_mtime,
            })
        return sorted(notes, key=lambda n: n["modified"], reverse=True)

    def read_note(self, path: str) -> Optional[str]:
        """Read a note from the vault."""
        full_path = self.vault_path / path
        if not full_path.exists():
            return None
        return full_path.read_text(encoding="utf-8")

    def write_note(self, path: str, content: str, frontmatter: Optional[Dict[str, Any]] = None) -> bool:
        """Write a note to the vault."""
        full_path = self.vault_path / path
        full_path.parent.mkdir(parents=True, exist_ok=True)

        # Add frontmatter if provided
        if frontmatter:
            import yaml
            fm_str = yaml.dump(frontmatter, default_flow_style=False)
            content = f"---\n{fm_str}---\n\n{content}"

        full_path.write_text(content, encoding="utf-8")
        return True

    def search_notes(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search note content."""
        if not self.is_available():
            return []

        results = []
        for md_file in self.vault_path.rglob("*.md"):
            try:
                text = md_file.read_text(encoding="utf-8", errors="replace")
                if query.lower() in text.lower():
                    # Find context around match
                    idx = text.lower().index(query.lower())
                    start = max(0, idx - 100)
                    end = min(len(text), idx + len(query) + 100)
                    snippet = text[start:end].strip()

                    results.append({
                        "path": str(md_file.relative_to(self.vault_path)),
                        "name": md_file.stem,
                        "snippet": snippet,
                    })
                    if len(results) >= limit:
                        break
            except Exception:
                continue

        return results

    def create_study_note(self, topic: str, content: str, tags: Optional[List[str]] = None) -> bool:
        """Create a study note with proper frontmatter."""
        path = f"Codex Mentis/{topic.replace(' ', '_')}.md"
        frontmatter = {
            "created": "now",
            "tags": (tags or []) + ["codex-mentis", "study"],
            "topic": topic,
            "source": "codex-mentis",
        }
        return self.write_note(path, content, frontmatter)
