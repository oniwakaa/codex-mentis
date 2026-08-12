import typer
import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, List
from pitagora.core.config import CONFIG_DIR
from pitagora.cli.rich_ui import print_table, print_panel

app = typer.Typer(help="Manage and query the Pitagora knowledge base")

DB_PATH = CONFIG_DIR / "memory.db"

def get_db_connection():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS kb_documents (
            path TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            subject TEXT NOT NULL,
            added_at TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS kb_chunks (
            doc_path TEXT,
            chunk_index INTEGER,
            text TEXT NOT NULL,
            embedding TEXT,
            PRIMARY KEY (doc_path, chunk_index),
            FOREIGN KEY (doc_path) REFERENCES kb_documents(path) ON DELETE CASCADE
        )
    """)
    conn.commit()
    return conn

def extract_text(file_path: Path) -> str:
    """Extract plain text from files depending on their extension."""
    ext = file_path.suffix.lower()
    if ext in (".md", ".tex", ".txt", ".yaml", ".yml"):
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    elif ext == ".pdf":
        try:
            import pypdf
            reader = pypdf.PdfReader(file_path)
            text = ""
            for page in reader.pages:
                text += page.extract_text() or ""
            return text
        except Exception:
            return f"[PDF processing error: install pypdf to read PDF files directly. Raw file size: {file_path.stat().st_size} bytes]"
    return ""

def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 150) -> List[str]:
    """Simple text chunker with overlap."""
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += (chunk_size - overlap)
    return chunks

@app.command("add")
def add_document(
    file_path: Path = typer.Argument(..., help="Path to document file to ingest"),
    subject: str = typer.Option("general", "--subject", "-s", help="Subject classification (e.g. physics, math)"),
    title: Optional[str] = typer.Option(None, "--title", "-t", help="Custom title for the document")
):
    """Ingest a reference document (PDF, Markdown, LaTeX, TXT) into the local knowledge base."""
    if not file_path.exists():
        typer.echo(f"Error: File '{file_path}' does not exist.")
        raise typer.Exit(1)
        
    doc_title = title or file_path.name
    text = extract_text(file_path)
    if not text:
        typer.echo(f"Error: Unable to extract text from {file_path}. Format may be unsupported.")
        raise typer.Exit(1)
        
    chunks = chunk_text(text)
    if not chunks:
        typer.echo(f"Error: Ingested file has empty content.")
        raise typer.Exit(1)
        
    # Generate embeddings if sentence-transformers is installed
    embeddings = []
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("all-MiniLM-L6-v2")
        embeddings = [model.encode(c).tolist() for c in chunks]
    except Exception:
        pass
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Add document
        cursor.execute(
            "INSERT OR REPLACE INTO kb_documents (path, title, subject, added_at) VALUES (?, ?, ?, ?)",
            (str(file_path.resolve()), doc_title, subject, datetime.now().isoformat())
        )
        
        # Remove old chunks if overwriting
        cursor.execute("DELETE FROM kb_chunks WHERE doc_path = ?", (str(file_path.resolve()),))
        
        # Add new chunks
        for idx, chunk in enumerate(chunks):
            emb_str = json.dumps(embeddings[idx]) if idx < len(embeddings) else None
            cursor.execute(
                "INSERT INTO kb_chunks (doc_path, chunk_index, text, embedding) VALUES (?, ?, ?, ?)",
                (str(file_path.resolve()), idx, chunk, emb_str)
            )
            
        conn.commit()
        typer.echo(f"Successfully ingested '{doc_title}' ({len(chunks)} chunks, subject: {subject})")
    except Exception as e:
        conn.rollback()
        typer.echo(f"Failed to ingest document: {e}")
    finally:
        conn.close()

@app.command("list")
def list_documents():
    """List all ingested documents in the knowledge base."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT path, title, subject, added_at FROM kb_documents")
    rows = cursor.fetchall()
    
    # Get chunk counts
    counts = {}
    cursor.execute("SELECT doc_path, COUNT(*) as cnt FROM kb_chunks GROUP BY doc_path")
    for r in cursor.fetchall():
        counts[r["doc_path"]] = r["cnt"]
        
    conn.close()
    
    if not rows:
        typer.echo("Knowledge base is empty. Use 'kb add' to index documents.")
        return
        
    headers = ["Title", "Subject", "Chunks", "Added At", "Path"]
    display_rows = []
    for r in rows:
        path = r["path"]
        chunk_cnt = counts.get(path, 0)
        display_rows.append([r["title"], r["subject"], chunk_cnt, r["added_at"], path])
        
    print_table(headers, display_rows, title="Knowledge Base Documents")

@app.command("search")
def search_kb(
    query: str = typer.Argument(..., help="Search query"),
    limit: int = typer.Option(3, "--limit", "-l", help="Max results to display")
):
    """Semantic/text search across the knowledge base."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT c.doc_path, c.chunk_index, c.text, c.embedding, d.title, d.subject 
        FROM kb_chunks c 
        JOIN kb_documents d ON c.doc_path = d.path
    """)
    rows = cursor.fetchall()
    
    if not rows:
        typer.echo("No documents in the knowledge base to search.")
        conn.close()
        return
        
    semantic_success = False
    try:
        from sentence_transformers import SentenceTransformer
        import numpy as np
        
        model = SentenceTransformer("all-MiniLM-L6-v2")
        query_emb = model.encode(query)
        
        scores = []
        for r in rows:
            emb_str = r["embedding"]
            if emb_str:
                emb = np.array(json.loads(emb_str))
                sim = np.dot(query_emb, emb) / (np.linalg.norm(query_emb) * np.linalg.norm(emb))
                scores.append((sim, r))
            else:
                scores.append((0.0, r))
                
        scores.sort(key=lambda x: x[0], reverse=True)
        results = [s[1] for s in scores if s[0] > 0.25][:limit]
        semantic_success = len(results) > 0
    except Exception:
        pass
        
    if not semantic_success:
        # Fallback text keyword search
        cursor.execute("""
            SELECT c.doc_path, c.chunk_index, c.text, d.title, d.subject 
            FROM kb_chunks c 
            JOIN kb_documents d ON c.doc_path = d.path 
            WHERE c.text LIKE ? LIMIT ?
        """, (f"%{query}%", limit))
        results = cursor.fetchall()
        
    conn.close()
    
    if not results:
        typer.echo("No matching knowledge base content found.")
        return
        
    typer.echo(f"Knowledge Base Results for: '{query}'")
    for r in results:
        title = f"Document: {r['title']} (Chunk {r['chunk_index']}, Subject: {r['subject']})"
        print_panel(r["text"], title, style="green")

@app.command("remove")
def remove_document(path: str = typer.Argument(..., help="Path of the document to remove")):
    """Remove a document and its chunks from the knowledge base."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Enable foreign keys for cascade delete
    cursor.execute("PRAGMA foreign_keys = ON")
    
    cursor.execute("SELECT path FROM kb_documents WHERE path = ?", (path,))
    exists = cursor.fetchone()
    
    if not exists:
        typer.echo(f"Error: Document with path '{path}' not found in knowledge base.")
        conn.close()
        raise typer.Exit(1)
        
    cursor.execute("DELETE FROM kb_documents WHERE path = ?", (path,))
    conn.commit()
    conn.close()
    typer.echo(f"Successfully removed '{path}' from knowledge base.")
