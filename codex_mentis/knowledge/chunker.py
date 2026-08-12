"""Smart chunking for math/science content — preserves equations and context."""
import re
from typing import List, Dict, Any, Optional


class SmartChunker:
    """Chunks text intelligently, preserving mathematical expressions and context."""

    def __init__(
        self,
        max_chunk_size: int = 1000,
        min_chunk_size: int = 100,
        overlap: int = 50,
        preserve_equations: bool = True,
    ):
        self.max_chunk_size = max_chunk_size
        self.min_chunk_size = min_chunk_size
        self.overlap = overlap
        self.preserve_equations = preserve_equations

    def chunk_text(self, text: str, source: str = "") -> List[Dict[str, Any]]:
        """Chunk text into semantically meaningful pieces."""
        # First, split into sections by headers
        sections = self._split_sections(text)

        chunks = []
        for section_title, section_text in sections:
            if len(section_text) <= self.max_chunk_size:
                chunks.append({
                    "text": section_text,
                    "metadata": {
                        "source": source,
                        "section": section_title,
                        "char_count": len(section_text),
                    }
                })
            else:
                # Split large sections into paragraphs
                sub_chunks = self._chunk_section(section_text, section_title, source)
                chunks.extend(sub_chunks)

        return chunks

    def _split_sections(self, text: str) -> List[tuple]:
        """Split text into sections by headers."""
        # Match markdown headers, LaTeX sections, or double newlines
        header_pattern = re.compile(
            r"^(#{1,6}\s+.+|\\(?:sub)*section\*?\{[^}]+\})\s*$",
            re.MULTILINE
        )

        sections = []
        last_pos = 0
        last_title = "Introduction"

        for match in header_pattern.finditer(text):
            if match.start() > last_pos:
                section_text = text[last_pos:match.start()].strip()
                if section_text:
                    sections.append((last_title, section_text))
            last_title = match.group(0).strip().lstrip("#").strip()
            last_title = re.sub(r"\\(?:sub)*section\*?\{([^}]+)\}", r"\1", last_title)
            last_pos = match.end()

        # Add remaining text
        remaining = text[last_pos:].strip()
        if remaining:
            sections.append((last_title, remaining))

        if not sections:
            sections = [("全文", text)]

        return sections

    def _chunk_section(self, text: str, section: str, source: str) -> List[Dict[str, Any]]:
        """Chunk a large section preserving equations and paragraph boundaries."""
        # Split by double newlines (paragraphs)
        paragraphs = re.split(r"\n\s*\n", text)

        chunks = []
        current_chunk = ""
        current_equation = None

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # Check if paragraph contains a math block
            has_equation = bool(re.search(r"\$\$.*?\$\$|\\begin\{(?:equation|align|eqnarray)", para, re.DOTALL))

            # If adding this paragraph exceeds max, start new chunk
            if current_chunk and len(current_chunk) + len(para) > self.max_chunk_size:
                if len(current_chunk) >= self.min_chunk_size:
                    chunks.append({
                        "text": current_chunk.strip(),
                        "metadata": {
                            "source": source,
                            "section": section,
                            "char_count": len(current_chunk),
                            "has_equation": current_equation is not None,
                        }
                    })
                    # Overlap: keep last sentence for context
                    overlap_text = self._get_overlap_text(current_chunk)
                    current_chunk = overlap_text + "\n\n" + para
                    current_equation = None
                else:
                    current_chunk += "\n\n" + para
            else:
                if current_chunk:
                    current_chunk += "\n\n" + para
                else:
                    current_chunk = para

            if has_equation:
                current_equation = True

        # Final chunk
        if current_chunk.strip():
            chunks.append({
                "text": current_chunk.strip(),
                "metadata": {
                    "source": source,
                    "section": section,
                    "char_count": len(current_chunk),
                    "has_equation": current_equation is not None,
                }
            })

        return chunks

    def _get_overlap_text(self, text: str) -> str:
        """Get the last few sentences for overlap context."""
        if self.overlap <= 0:
            return ""
        sentences = re.split(r"(?<=[.!?])\s+", text)
        overlap_text = ""
        for sentence in reversed(sentences):
            if len(overlap_text) + len(sentence) > self.overlap:
                break
            overlap_text = sentence + " " + overlap_text
        return overlap_text.strip()

    def chunk_equation_block(self, text: str) -> List[Dict[str, Any]]:
        """Special chunking that keeps equations with their explanations."""
        # Split at equation boundaries but keep equation + explanation together
        pattern = re.compile(
            r"(\$\$.*?\$\$|\\begin\{(?:equation|align|eqnarray)\*?\}.*?\\end\{(?:equation|align|eqnarray)\*?\})",
            re.DOTALL
        )

        parts = pattern.split(text)
        chunks = []
        i = 0
        while i < len(parts):
            chunk_text = parts[i].strip()
            # If next part is an equation, attach it to current
            if i + 1 < len(parts) and re.match(r"^\$\$|\\begin\{", parts[i + 1].strip()):
                chunk_text += "\n\n" + parts[i + 1].strip()
                i += 2
            else:
                i += 1

            if chunk_text and len(chunk_text) >= self.min_chunk_size:
                chunks.append({
                    "text": chunk_text,
                    "metadata": {"has_equation": True, "char_count": len(chunk_text)}
                })
            elif chunk_text:
                # Merge small chunks
                if chunks:
                    chunks[-1]["text"] += "\n\n" + chunk_text
                    chunks[-1]["metadata"]["char_count"] += len(chunk_text) + 2
                else:
                    chunks.append({
                        "text": chunk_text,
                        "metadata": {"has_equation": False, "char_count": len(chunk_text)}
                    })

        return chunks
