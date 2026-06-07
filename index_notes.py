import json
import os
import chromadb
from pathlib import Path
from sentence_transformers import SentenceTransformer
from tqdm import tqdm
import time

from itertools import chain


from dotenv import load_dotenv
load_dotenv()

DB_DIR = os.getenv("DB_DIR")
COLLECTION = os.getenv("COLLECTION")
LOGSEQ_DIR = Path(os.getenv("LOGSEQ_DIR"))
STATE_FILE = Path("index_state.json")

if STATE_FILE.exists():
    state = json.loads(STATE_FILE.read_text())
else:
    state = {}

model = SentenceTransformer("Qwen/Qwen3-Embedding-0.6B")

client = chromadb.PersistentClient(path=DB_DIR)
collection = client.get_or_create_collection(COLLECTION)

def chunks(text, size=900, overlap=150):
    # rough char chunking; close enough for v1
    i = 0
    while i < len(text):
        yield text[i:i + size]
        i += size - overlap

paths = [x for x in chain(
    (LOGSEQ_DIR / "journals").rglob("2025_*.md"),
    # (LOGSEQ_DIR / "pages").rglob("*.md"),
)]

for path in tqdm(paths):
    rel = str(path.relative_to(LOGSEQ_DIR))
    mtime = path.stat().st_mtime

    if rel in state and state[rel]["mtime"] == mtime:
        continue
    # TODO move the update until after we actually added the thing.
    state[rel] = {"mtime": mtime}

    time.sleep(30)

    # re-index file here
    docs, ids, metas = [], [], []

    text = path.read_text(errors="ignore")
    for j, chunk in enumerate(chunks(text)):
        if chunk.strip():
            ids.append(f"{rel}::{j}")  # TODO the ids arent great at pointing to which chunk in the file contains the thing. but guess you can approximate using the chunk length, and overlap, 900 and 150 ?
            docs.append(chunk)
            metas.append({"path": str(rel), "chunk": j})
    #
    embeddings = model.encode(docs, normalize_embeddings=True).tolist()
    
    collection.upsert(
        ids=ids,
        documents=docs,
        embeddings=embeddings,
        metadatas=metas,
    )
    ...
    print(f"Indexed {len(docs)} chunks from {rel}")

    STATE_FILE.write_text(json.dumps(state, indent=2))


