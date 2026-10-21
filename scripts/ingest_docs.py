import os
import psycopg
import sys
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  
sys.path.insert(0, str(ROOT))               
DOCS = ROOT / "data" / "docs"

from src.embeddings import embed_text

def connect():
    try:
        from dotenv import load_dotenv
        load_dotenv(".env")
    except ImportError:
        pass
    url = os.getenv("DATABASE_URL", "postgresql://pl:pl@localhost:5433/pl")
    return psycopg.connect(url, connect_timeout=3)  


def parse_doc(path) -> dict:
    """Return source_file, title, doc_type (from filename), doc_date, content."""
    text = path.read_text(encoding="utf-8")
    doc_type = path.name.split("_")[1]        

    title = re.search(r"^###\s*(.+)$", text, re.M).group(1).strip()

    date_match = re.search(r"\*\*Date:\*\*\s*(\d{1,2}\s+\w+\s+\d{4})", text)
    if not date_match:
        raise ValueError(f"No '**Date:**' line found in {path.name}")
    doc_date = datetime.strptime(date_match.group(1), "%d %B %Y").date()

    return {
        "source_file": path.name,
        "doc_type": doc_type,
        "title": title,
        "doc_date": doc_date,    
        "content": text,
    }

def make_chunks(doc) -> list[str]:
    """v1: the whole document is one chunk (docs are ~200 words)."""
    return [doc["content"]]

def ensure_table(conn): 
    conn.execute(
        "CREATE EXTENSION IF NOT EXISTS vector; "
        "CREATE TABLE IF NOT EXISTS doc_chunks ("
        "source_file TEXT NOT NULL, "
        "chunk_index INT NOT NULL, "
        "doc_type TEXT NOT NULL, "
        "doc_date DATE NOT NULL, "
        "title TEXT NOT NULL, "
        "content TEXT NOT NULL, "
        "embedding VECTOR(768) NOT NULL, "
        "PRIMARY KEY (source_file, chunk_index))"
    )
    
def ingest():
    docs = [parse_doc(p) for p in sorted(DOCS.glob("[0-9][0-9]_*.md"))]
    with connect() as conn:
        ensure_table(conn)
        for doc in docs:
            for i, text in enumerate(make_chunks(doc)):
                vec = embed_text(text, "RETRIEVAL_DOCUMENT")
                conn.execute(
                    "INSERT INTO doc_chunks (source_file, chunk_index, doc_type, "
                    "doc_date, title, content, embedding) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s::vector) "
                    "ON CONFLICT (source_file, chunk_index) DO UPDATE SET "
                    "content=EXCLUDED.content, embedding=EXCLUDED.embedding",
                    (doc["source_file"], i, doc["doc_type"], doc["doc_date"],
                     doc["title"], text, "[" + ",".join(map(str, vec)) + "]"),
                )
    print(f"Ingested {len(docs)} documents")

if __name__ == "__main__":
    ingest()