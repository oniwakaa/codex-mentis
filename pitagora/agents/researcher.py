import re

import httpx

from pitagora.agents.base import AgentResponse, BaseAgent
from pitagora.agents.providers.base import BaseProvider

RESEARCH_SYSTEM_PROMPT = """<role>Research agent for Pitagora. Deep-dive into math, physics, and scientific concepts.</role>

<instructions>
- Use correct LaTeX for all formulas; keep explanations mathematically precise
- Cite sources inline (authors, papers, arXiv IDs, textbooks)
- Structure findings as a report: headers, key equations, bibliography
- Use web_search and kb_retrieve tools to gather factual, up-to-date data
</instructions>

<example>
Query: "Schwarzschild metric":
"## Schwarzschild Metric\\n\\nThe unique spherically symmetric vacuum solution to Einstein's field equations [Schwarzschild 1916]:\\n$$ds^2 = -(1-\\frac{r_s}{r})c^2 dt^2 + (1-\\frac{r_s}{r})^{-1} dr^2 + r^2 d\\Omega^2$$\\nwhere $r_s = 2GM/c^2$ is the Schwarzschild radius.\\n\\n**Sources**\\n- K. Schwarzschild, *Sitzungsber. Preuss. Akad.* (1916)\\n"
</example>
"""


class ResearchAgent(BaseAgent):
    def __init__(self, provider: BaseProvider):
        super().__init__(
            name="Researcher",
            role="Scientific Research and Synthesis Expert",
            provider=provider,
            system_prompt=RESEARCH_SYSTEM_PROMPT,
        )

        # Register tools
        self.register_tool(
            "web_search",
            {
                "name": "web_search",
                "description": "Search the web for papers, explanations, or articles on a scientific topic.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query (e.g. 'Schrodinger equation derivation history')",
                        }
                    },
                    "required": ["query"],
                },
            },
            self.tool_web_search,
        )

        self.register_tool(
            "kb_retrieve",
            {
                "name": "kb_retrieve",
                "description": "Query the local knowledge base or uploaded documents for relevant concepts.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The semantic search query for the local KB",
                        }
                    },
                    "required": ["query"],
                },
            },
            self.tool_kb_retrieve,
        )

    def tool_web_search(self, query: str) -> str:
        """
        Executes a search via DuckDuckGo HTML API and scrapes titles, URLs, and snippets.
        """
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/119.0"
            }
            url = f"https://html.duckduckgo.com/html/?q={httpx.QueryParams(query)}"
            with httpx.Client(timeout=15.0) as client:
                r = client.get(url, headers=headers)

            if r.status_code == 200:
                results = []
                try:
                    from bs4 import BeautifulSoup

                    soup = BeautifulSoup(r.text, "html.parser")
                    for item in soup.select(".result")[:5]:
                        title_a = item.select_one(".result__a")
                        snippet_a = item.select_one(".result__snippet")
                        if title_a:
                            results.append(
                                f"Title: {title_a.get_text(strip=True)}\n"
                                f"URL: {title_a['href']}\n"
                                f"Snippet: {snippet_a.get_text(strip=True) if snippet_a else ''}\n"
                            )
                except ImportError:
                    # Basic regex fallback if bs4 is missing
                    urls = re.findall(r'href="([^"]+)" class="result__url"', r.text)
                    snippets = re.findall(
                        r'<a class="result__snippet"[^>]*>(.*?)</a>', r.text, re.DOTALL
                    )
                    for i in range(min(len(urls), len(snippets), 5)):
                        clean_snippet = re.sub(r"<[^<]+?>", "", snippets[i]).strip()
                        results.append(
                            f"Title: Result {i+1}\n"
                            f"URL: {urls[i]}\n"
                            f"Snippet: {clean_snippet}\n"
                        )

                if results:
                    return "\n---\n".join(results)

            return f"DuckDuckGo search returned status {r.status_code}"
        except Exception as e:
            return f"Error executing web search: {str(e)}"

    def tool_kb_retrieve(self, query: str) -> str:
        """
        Queries the knowledge base module (if available).
        """
        try:
            # Wrap import in try-except as specified
            from pitagora.knowledge.base import KnowledgeBase

            kb = KnowledgeBase()
            results = kb.retrieve(query)
            if results:
                return "\n---\n".join(
                    [
                        f"Source: {res.get('source')}\nContent: {res.get('content')}"
                        for res in results
                    ]
                )
            return "No matching local KB entries found."
        except Exception:
            return f"Knowledge base module is not initialized. Mock search query for '{query}' returned no results."

    def research(self, topic: str, depth: str = "medium") -> AgentResponse:
        """
        Runs an agent loop that uses search/kb retrieval tools to synthesize research on a topic.
        """
        max_turns = 4 if depth == "deep" else 2
        prompt = (
            f"Please conduct research on the topic: '{topic}'.\n"
            f"Research depth: {depth}.\n"
            f"Use your web search or KB retrieval tools if you need to gather equations, papers, or facts. "
            f"Produce a detailed report outlining key equations, conceptual insights, and bibliography/citations."
        )

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt},
        ]

        for _ in range(max_turns):
            response = self.provider.complete(messages, tools=self.tools)
            content = response.get("content", "")
            tool_calls = response.get("tool_calls", [])

            if not tool_calls:
                # No more tools needed; parse confidence and return
                confidence = 1.0
                conf_match = re.search(
                    r"<confidence>\s*(0\.\d+|1\.0|1)\s*</confidence>", content, re.IGNORECASE
                )
                if conf_match:
                    try:
                        confidence = float(conf_match.group(1))
                    except ValueError:
                        pass
                return AgentResponse(
                    content=content,
                    tool_calls=[],
                    confidence=confidence,
                    metadata={"agent_name": self.name, "agent_role": self.role},
                )

            # Record assistant call
            messages.append({"role": "assistant", "content": content})

            # Execute tool calls and feed back results
            tool_results_summary = []
            for tc in tool_calls:
                name = tc["name"]
                args = tc["arguments"]
                result = self.with_tool(name, args)
                tool_results_summary.append(f"Tool '{name}' with args {args} returned:\n{result}")

            messages.append({"role": "user", "content": "\n\n".join(tool_results_summary)})

        # Exceeded max turns, get final answer
        response = self.provider.complete(messages)
        return AgentResponse(
            content=response.get("content", ""),
            tool_calls=[],
            confidence=0.8,
            metadata={"agent_name": self.name, "agent_role": self.role},
        )

    def find_papers(self, query: str) -> AgentResponse:
        """
        Specifically search for papers and list references.
        """
        prompt = (
            f"Search for academic papers, books, or preprints related to: '{query}'.\n"
            f"Use the web_search tool if needed. Return a list of at least 3 relevant sources "
            f"with author, title, year, journal/arXiv ID, and a brief description of their contribution."
        )
        return self.think(prompt)

    def synthesize(self, sources: list[str]) -> AgentResponse:
        """
        Synthesize multiple text snippets or source summaries into a unified report.
        """
        sources_str = "\n\n".join([f"Source {i+1}:\n{src}" for i, src in enumerate(sources)])
        prompt = (
            f"Synthesize the following sources into a single, cohesive, structured research report.\n"
            f"Ensure equations are clear and references are integrated logically.\n\n"
            f"{sources_str}"
        )
        return self.think(prompt)
