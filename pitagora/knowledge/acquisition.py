"""Knowledge acquisition — the brain that discovers, crawls, extracts, and stores knowledge.

This is what makes Pitagora different: instead of hardcoded concepts,
the agent actively researches topics, finds papers, extracts knowledge,
and builds a growing, source-cited knowledge base across Math, Physics, and Philosophy.

Pipeline:
  1. Intent → What does the user want to learn?
  2. Search  → webfetch multi-engine search (free, zero-config, arXiv, SEP, Gutenberg)
  3. Fetch   → webfetch local extraction (clean markdown, no API cost)
  4. Extract → Parse equations, definitions, theorems, arguments, relationships
  5. Store   → Save to knowledge base with full citations
  6. Graph   → Update concept graph with discovered relationships
"""

import re
from datetime import datetime
from typing import Any

from pitagora.knowledge.extractor import KnowledgeExtractor
from pitagora.knowledge.webfetch_bridge import WebfetchBridge


class KnowledgeAcquisition:
    """Orchestrates knowledge discovery and storage across STEM and Philosophy."""

    def __init__(self, knowledge_base=None, concept_graph=None):
        self.webfetch = WebfetchBridge()
        self.extractor = KnowledgeExtractor()
        self.kb = knowledge_base
        self.cg = concept_graph

    def research_topic(
        self, topic: str, depth: str = "medium", max_sources: int = 5
    ) -> dict[str, Any]:
        """Research a topic end-to-end: search → fetch → extract → store.

        Args:
            topic: What to research (e.g. "Lagrangian mechanics derivation")
            depth: "shallow" (1-2 sources), "medium" (3-5), "deep" (5-10)
            max_sources: Max number of sources to crawl

        Returns:
            {topic, sources, findings, concepts_found, citations}
        """
        # Step 1: Search
        n_results = {"shallow": 3, "medium": 5, "deep": 10}.get(depth, 5)
        search_results = self.webfetch.search(topic, max_results=n_results)

        if not search_results:
            return {
                "topic": topic,
                "sources": [],
                "findings": f"No results found for '{topic}'. Try a different query.",
                "concepts_found": [],
                "citations": [],
            }

        # Step 2: Fetch content from top sources
        sources = []
        for result in search_results[:max_sources]:
            url = result.get("url", "")
            if not url:
                continue
            fetched = self.webfetch.fetch_url(url)
            if fetched.get("text"):
                sources.append(
                    {
                        "url": url,
                        "title": fetched.get("title", result.get("title", "")),
                        "text": fetched["text"],
                        "snippet": result.get("snippet", ""),
                        "search_score": result.get("score", 0.0),
                    }
                )

        if not sources:
            return {
                "topic": topic,
                "sources": search_results,
                "findings": f"Found {len(search_results)} results but could not extract content.",
                "concepts_found": [],
                "citations": [],
            }

        # Step 3: Extract knowledge from each source
        all_findings = []
        all_concepts = set()
        citations = []

        for source in sources:
            extracted = self.extractor.extract_knowledge(source["text"], topic=topic)
            source["extracted"] = extracted
            all_findings.extend(extracted.get("key_points", []))
            all_concepts.update(extracted.get("concepts", []))
            if extracted.get("equations"):
                all_findings.extend([f"Equation: {eq}" for eq in extracted["equations"]])
            citations.append(
                {
                    "title": source["title"],
                    "url": source["url"],
                    "relevance": source["search_score"],
                }
            )

        # Step 4: Store in knowledge base if available
        if self.kb:
            for source in sources:
                extracted = source.get("extracted", {})
                self.kb.add_document(
                    path=source["url"],
                    title=source["title"],
                    subject=topic,
                    chunks=[{"text": source["text"][:2000], "metadata": {"source": source["url"]}}],
                    metadata={"researched_at": datetime.now().isoformat(), "topic": topic},
                )

        # Step 5: Update concept graph if available
        if self.cg and all_concepts:
            for concept in all_concepts:
                if concept not in self.cg.graph:
                    self.cg.add_concept(
                        concept=concept,
                        prerequisites=[],
                        description=f"Discovered via research on '{topic}'",
                        domain="auto-discovered",
                    )

        return {
            "topic": topic,
            "sources": [
                {"title": s["title"], "url": s["url"], "snippet": s["snippet"]} for s in sources
            ],
            "findings": all_findings,
            "concepts_found": list(all_concepts),
            "citations": citations,
            "total_sources_crawled": len(sources),
        }

    def search_papers(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        """Search for academic papers specifically (arXiv, academic portals)."""
        arxiv_query = f"site:arxiv.org {query}"
        results = self.webfetch.search(arxiv_query, max_results=max_results)

        general_results = self.webfetch.search(
            f"{query} paper mathematics physics", max_results=max_results
        )

        seen = set()
        combined = []
        for r in results + general_results:
            url = r.get("url", "")
            if url and url not in seen:
                seen.add(url)
                combined.append(r)

        return combined[:max_results]

    def fetch_paper(self, arxiv_url: str) -> dict[str, Any]:
        """Fetch and extract content from an arxiv paper page or PDF."""
        if "arxiv.org/abs/" in arxiv_url:
            html_url = arxiv_url.replace("/abs/", "/html/")
            fetched = self.webfetch.fetch_url(html_url)
            if fetched.get("text"):
                return self._process_paper(fetched, arxiv_url)

        fetched = self.webfetch.fetch_url(arxiv_url)
        return self._process_paper(fetched, arxiv_url)

    def _process_paper(self, fetched: dict[str, Any], original_url: str) -> dict[str, Any]:
        """Process fetched paper content into structured knowledge."""
        text = fetched.get("text", "")
        if not text:
            return {"error": "Could not extract paper content", "url": original_url}

        extracted = self.extractor.extract_knowledge(text, topic="")

        return {
            "title": fetched.get("title", "Unknown Paper"),
            "url": original_url,
            "abstract": self._extract_abstract(text),
            "equations": extracted.get("equations", []),
            "key_points": extracted.get("key_points", []),
            "concepts": extracted.get("concepts", []),
            "full_text_length": len(text),
        }

    def _extract_abstract(self, text: str) -> str:
        """Try to extract the abstract from paper text."""
        abstract_match = re.search(
            r"(?:Abstract|ABSTRACT)[:\s]*(.*?)(?:\n\n|Introduction|INTRODUCTION|1\.|Keywords)",
            text,
            re.DOTALL | re.IGNORECASE,
        )
        if abstract_match:
            return abstract_match.group(1).strip()[:1000]
        return text[:500].strip()

    def search_philosophy(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        """Search Stanford Encyclopedia of Philosophy (SEP) and philosophy repositories."""
        sep_query = f"site:plato.stanford.edu {query}"
        results = self.webfetch.search(sep_query, max_results=max_results)

        general_phil = self.webfetch.search(
            f"{query} Stanford Encyclopedia of Philosophy epistemology logic metaphysics",
            max_results=max_results,
        )

        seen = set()
        combined = []
        for r in results + general_phil:
            url = r.get("url", "")
            if url and url not in seen:
                seen.add(url)
                combined.append(r)

        return combined[:max_results]

    def fetch_sep_entry(self, sep_url_or_slug: str) -> dict[str, Any]:
        """Fetch and extract structured knowledge from a Stanford Encyclopedia of Philosophy entry."""
        url = sep_url_or_slug.strip()
        if not url.startswith("http"):
            slug = url.strip("/")
            url = f"https://plato.stanford.edu/entries/{slug}/"

        fetched = self.webfetch.fetch_url(url)
        text = fetched.get("text", "")
        if not text:
            return {"error": "Could not fetch SEP entry", "url": url}

        extracted = self.extractor.extract_knowledge(text, topic="")

        preamble_match = re.search(r"^(.*?)(?:\n#+\s*1|\n1\.\s+)", text, re.DOTALL)
        preamble = preamble_match.group(1).strip()[:1500] if preamble_match else text[:1000].strip()

        return {
            "title": fetched.get("title", "SEP Entry"),
            "url": url,
            "preamble": preamble,
            "key_points": extracted.get("key_points", []),
            "concepts": extracted.get("concepts", []),
            "full_text_length": len(text),
            "source_type": "sep_philosophy",
        }

    def fetch_classic_text(self, query: str, gutenberg_id: int | None = None) -> dict[str, Any]:
        """Fetch classic open philosophy / physics foundational treatise (Gutenberg, Internet Archive)."""
        if gutenberg_id:
            url = f"https://www.gutenberg.org/files/{gutenberg_id}/{gutenberg_id}-0.txt"
            fetched = self.webfetch.fetch_url(url)
        else:
            search_res = self.webfetch.search(f"site:gutenberg.org {query} text", max_results=1)
            if search_res:
                url = search_res[0].get("url", "")
                fetched = self.webfetch.fetch_url(url) if url else {}
            else:
                fetched = {}

        text = fetched.get("text", "")
        if not text:
            return {"error": f"Could not fetch classic text for '{query}'"}

        extracted = self.extractor.extract_knowledge(text[:8000], topic=query)
        return {
            "title": fetched.get("title", query),
            "url": fetched.get("url", ""),
            "excerpt": text[:2000].strip(),
            "concepts": extracted.get("concepts", []),
            "key_points": extracted.get("key_points", []),
            "source_type": "classic_text",
        }
