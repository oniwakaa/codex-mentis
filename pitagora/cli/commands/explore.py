import typer
import httpx
import logging
import xml.etree.ElementTree as ET
from typing import List, Dict
from pitagora.cli.rich_ui import print_table
from pitagora.chat import launch_chat as launch_repl

app = typer.Typer(help="Explore open-ended questions using researcher agents")

def search_arxiv(query: str, max_results: int = 3) -> List[Dict[str, str]]:
    """Live search on the arXiv public API to find academic reference papers."""
    url = f"https://export.arxiv.org/api/query?search_query=all:{query}&max_results={max_results}"
    try:
        response = httpx.get(url, timeout=10.0)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            ns = {'atom': 'http://www.w3.org/2005/Atom'}
            papers = []
            for entry in root.findall('atom:entry', ns):
                title = entry.find('atom:title', ns)
                summary = entry.find('atom:summary', ns)
                pdf_url = entry.find('atom:id', ns)
                
                title_text = title.text.strip().replace('\n', ' ') if title is not None else "No Title"
                summary_text = summary.text.strip().replace('\n', ' ') if summary is not None else ""
                url_text = pdf_url.text.strip() if pdf_url is not None else ""
                
                if len(summary_text) > 300:
                    summary_text = summary_text[:297] + "..."
                    
                papers.append({
                    "title": title_text,
                    "summary": summary_text,
                    "url": url_text
                })
            return papers
    except Exception as e:
        logging.getLogger(__name__).warning("arxiv search failed: %s", e)
        pass
    return []

@app.command()
def explore(
    question: str = typer.Argument(..., help="What question or topic to explore?"),
    depth: str = typer.Option("standard", "--depth", "-d", help="Research depth (surface/standard/deep)"),
    papers: bool = typer.Option(False, "--papers", "-p", help="Search ArXiv academic repository for context")
):
    """Start an interactive research exploration session."""
    typer.echo(f"Initializing Exploration Mode for: '{question}' (Depth: {depth})...")
    
    paper_context = ""
    if papers:
        typer.echo("Searching ArXiv database for relevant publications...")
        results = search_arxiv(question, max_results=3)
        if results:
            typer.echo(f"Found {len(results)} relevant publications.")
            headers = ["Title", "URL"]
            rows = [[p["title"][:50] + "...", p["url"]] for p in results]
            print_table(headers, rows, title="ArXiv Search Results")
            
            paper_context = "Relevant arXiv papers found:\n"
            for p in results:
                paper_context += f"- Title: {p['title']}\n  URL: {p['url']}\n  Abstract: {p['summary']}\n\n"
        else:
            typer.echo("No papers found on ArXiv matching this topic.")
            
    launch_repl(
        mode="EXPLORE",
        topic=question,
        system_prompt=paper_context,
    )
