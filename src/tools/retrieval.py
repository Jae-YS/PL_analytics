import os
import psycopg
from typing import Optional
from src.embeddings import embed_text

def connect():
    try:
        from dotenv import load_dotenv
        load_dotenv(".env")
    except ImportError:
        pass
    url = os.getenv("DATABASE_URL", "postgresql://pl:pl@localhost:5433/pl")
    return psycopg.connect(url, connect_timeout=3)  


def search_documents(query: str, top_k: int = 3, doc_type: Optional[str] = None) -> dict:
    """Search internal scouting reports, pre-match briefings and memos.
    Use for qualitative questions about players, opponent tendencies and
    club policy. Never use it for match results or league standings.
    Example: search_documents("Brighton build-up style", top_k=3)."""
    vec = "[" + ",".join(map(str, embed_text(query, "RETRIEVAL_QUERY"))) + "]"
    
    sql = (f"SELECT source_file, title, doc_date, content, "
           f"1 - (embedding <=> %s::vector) AS score "
           f"FROM doc_chunks "
           f"{'WHERE doc_type = %s ' if doc_type else ''}"
           f"ORDER BY score DESC LIMIT %s")
    with connect() as conn:
        with conn.cursor() as cur: 
            row = cur.execute(sql, (vec, doc_type, top_k) if doc_type else (vec, top_k)).fetchall()
        if not row:
            return {"query": query, "results": []}
        
        return {"query": query,
                "results": [{
                    "source_file": source_file,
                    "title": title,
                    "date": doc_date.isoformat(),
                    "content": content,
                    "score": round(score, 3),
                } for source_file, title, doc_date, content, score in row]}
        