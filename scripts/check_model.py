import os
from dotenv import load_dotenv
from google import genai
from google.genai.types import EmbedContentConfig

load_dotenv()
project = os.environ["GOOGLE_CLOUD_PROJECT"]

for location in ("us-east4", "global", "us-central1"):
    client = genai.Client(vertexai=True, project=project, location=location)
    for model in ("gemini-3.8-flash", "gemini-3.5-flash", "gemini-3.5-flash-lite"):
        try:
            r = client.models.generate_content(model=model, contents="Say hi in five words")
            print(f"OK    {location:12} {model}: {r.text.strip()}")
        except Exception as e:
            print(f"FAIL  {location:12} {model}: {str(e)[:80]}")
    try:
        e = client.models.embed_content(
            model="gemini-embedding-001", contents="test",
            config=EmbedContentConfig(output_dimensionality=768))
        print(f"OK    {location:12} embedding: {len(e.embeddings[0].values)} dims")
    except Exception as ex:
        print(f"FAIL  {location:12} embedding: {str(ex)[:80]}")