import os
from dotenv import load_dotenv
from google import genai
from google.genai.types import EmbedContentConfig

load_dotenv()

MODEL = "gemini-embedding-001"
DIM = 768
_client = None


def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(
            vertexai=True,
            project=os.environ["GOOGLE_CLOUD_PROJECT"],
            location=os.getenv("EMBED_LOCATION", "us-east4"),
        )
    return _client


def embed_text(text: str, task: str) -> list[float]:
    resp = _get_client().models.embed_content(
        model=MODEL,
        contents=text,
        config=EmbedContentConfig(task_type=task, output_dimensionality=DIM),
    )
    return resp.embeddings[0].values