"""Document ingestion — extracts text from PDF, Markdown, LaTeX, and plain text."""

import os
import re
from pathlib import Path


class DocumentIngester:
    """Extracts readable text from various document formats."""

    SUPPORTED_EXTENSIONS = {
        ".pdf",
        ".md",
        ".markdown",
        ".tex",
        ".latex",
        ".txt",
        ".rst",
        ".html",
        ".htm",
    }

    def extract_text(self, path: str) -> str:
        """Extract text from a file based on its extension."""
        path = os.path.expanduser(path)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Document not found: {path}")

        ext = Path(path).suffix.lower()

        if ext == ".pdf":
            return self._extract_pdf(path)
        elif ext in (".md", ".markdown"):
            return self._extract_markdown(path)
        elif ext in (".tex", ".latex"):
            return self._extract_latex(path)
        elif ext in (".html", ".htm"):
            return self._extract_html(path)
        else:
            return self._extract_text(path)

    def _extract_pdf(self, path: str) -> str:
        """Extract text from PDF using pymupdf or marker-pdf."""
        try:
            import pymupdf

            doc = pymupdf.open(path)
            text_parts = []
            for page in doc:
                text_parts.append(page.get_text())
            doc.close()
            return "\n\n".join(text_parts)
        except ImportError:
            pass

        try:
            from marker_pdf import convert_pdf

            return convert_pdf(path)
        except ImportError:
            pass

        # Fallback: try pdftotext CLI
        try:
            import subprocess

            result = subprocess.run(
                ["pdftotext", path, "-"], capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        raise ImportError(
            "No PDF extraction library available. Install pymupdf: pip install pymupdf"
        )

    def _extract_markdown(self, path: str) -> str:
        """Extract text from Markdown, preserving structure."""
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read()
        # Remove HTML tags but keep content
        text = re.sub(r"<[^>]+>", "", text)
        # Preserve math blocks
        return text

    def _extract_latex(self, path: str) -> str:
        """Extract text from LaTeX, converting math to readable form."""
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read()

        # Remove comments
        text = re.sub(r"%.*$", "", text, flags=re.MULTILINE)
        # Extract document body
        body_match = re.search(r"\\begin\{document\}(.*?)\\end\{document\}", text, re.DOTALL)
        if body_match:
            text = body_match.group(1)
        # Remove common LaTeX commands but keep content
        text = re.sub(r"\\(?:textbf|textit|emph|underline)\{([^}]*)\}", r"\1", text)
        text = re.sub(r"\\(?:section|subsection|subsubsection)\*?\{([^}]*)\}", r"\n## \1\n", text)
        text = re.sub(r"\\(?:item)\s*", "- ", text)
        # Keep math environments readable
        text = re.sub(r"\\\((.*?)\\\)", r"$\1$", text)
        text = re.sub(r"\\\[(.*?)\\\]", r"$$\1$$", text)
        # Remove remaining commands
        text = re.sub(r"\\[a-zA-Z]+\{([^}]*)\}", r"\1", text)
        text = re.sub(r"\\[a-zA-Z]+", "", text)
        # Clean up
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _extract_html(self, path: str) -> str:
        """Extract text from HTML."""
        try:
            from bs4 import BeautifulSoup

            with open(path, encoding="utf-8", errors="replace") as f:
                soup = BeautifulSoup(f.read(), "html.parser")
            # Remove script/style
            for tag in soup(["script", "style"]):
                tag.decompose()
            return soup.get_text(separator="\n", strip=True)
        except ImportError:
            # Fallback: basic regex
            with open(path, encoding="utf-8", errors="replace") as f:
                text = f.read()
            text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text)
            return text.strip()

    def _extract_text(self, path: str) -> str:
        """Extract plain text."""
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
