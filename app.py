import html
import re
import random
from pathlib import Path

import chromadb
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
from fastapi.responses import FileResponse
from sentence_transformers import SentenceTransformer

DB_DIR = "./chroma_logseq"
COLLECTION = "logseq_notes"
MODEL_NAME = "Qwen/Qwen3-Embedding-0.6B"  # or your working local model

app = FastAPI(title="Logseq Semantic Search")

print("Loading embedding model...")
model = SentenceTransformer(MODEL_NAME)
print("Model loaded.")

client = chromadb.PersistentClient(path=DB_DIR)
collection = client.get_collection(COLLECTION)


def highlight_terms(text: str, query: str) -> str:
    escaped = html.escape(text)

    terms = [
        re.escape(t)
        for t in re.findall(r"\w+", query)
        if len(t) >= 3
    ]

    if not terms:
        return escaped

    pattern = re.compile(r"(" + "|".join(terms) + r")", re.IGNORECASE)

    return pattern.sub(r'<mark>\1</mark>', escaped)


def search(query: str, n_results: int = 10):
    embedding = model.encode([query], normalize_embeddings=True).tolist()[0]

    results = collection.query(
        query_embeddings=[embedding],
        n_results=n_results,
        include=["documents", "metadatas", "distances"],
    )

    rows = []
    for doc, meta, distance in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        rows.append({
            "text": doc,
            "path": meta.get("path", "unknown"),
            "chunk": meta.get("chunk", ""),
            "distance": distance,
        })

    return rows


@app.get("/", response_class=HTMLResponse)
def home(
    q: str = Query(default=""),
    n: int = Query(default=10, ge=1, le=50),
):
    rows = search(q, n) if q.strip() else []

    result_cards = "\n".join(
        f"""
        <article class="result-card">
          <div class="result-meta">
            <span class="path">{html.escape(row["path"])}</span>
            <span class="pill">chunk {html.escape(str(row["chunk"]))}</span>
            <span class="pill">distance {row["distance"]:.4f}</span>
          </div>
          <pre>{highlight_terms(row["text"], q)}</pre>
        </article>
        """
        for row in rows
    )

    return f"""
    <!doctype html>
    <html>
    <head>
      <title>Logseq Semantic Search</title>
      <style>
        :root {{
          --bg: #0f1117;
          --panel: #171a23;
          --panel-2: #202431;
          --text: #f2f4f8;
          --muted: #9aa4b2;
          --accent: #ff9f43;
          --border: #2b3040;
        }}

        * {{
          box-sizing: border-box;
        }}

        body {{
          margin: 0;
          background:
            radial-gradient(circle at top left, #1c2233 0, transparent 36rem),
            var(--bg);
          color: var(--text);
          font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          line-height: 1.5;
        }}

        main {{
          max-width: 980px;
          margin: 0 auto;
          padding: 48px 24px;
        }}

        h1 {{
          margin: 0 0 8px;
          font-size: 32px;
          letter-spacing: -0.04em;
        }}

        .subtitle {{
          color: var(--muted);
          margin-bottom: 28px;
        }}

        form {{
          display: flex;
          gap: 12px;
          margin-bottom: 28px;
        }}

        input[type="text"] {{
          flex: 1;
          background: var(--panel);
          color: var(--text);
          border: 1px solid var(--border);
          border-radius: 14px;
          padding: 14px 16px;
          font-size: 16px;
          outline: none;
        }}

        input[type="text"]:focus {{
          border-color: var(--accent);
          box-shadow: 0 0 0 3px rgba(255, 159, 67, 0.18);
        }}

        button {{
          border: 0;
          border-radius: 14px;
          padding: 0 20px;
          background: var(--accent);
          color: #1a1004;
          font-weight: 700;
          cursor: pointer;
        }}

        .summary {{
          color: var(--muted);
          margin-bottom: 16px;
        }}

        .result-card {{
          background: linear-gradient(180deg, var(--panel), var(--panel-2));
          border: 1px solid var(--border);
          border-radius: 18px;
          padding: 18px;
          margin-bottom: 16px;
          box-shadow: 0 12px 30px rgba(0, 0, 0, 0.24);
        }}

        .result-meta {{
          display: flex;
          flex-wrap: wrap;
          align-items: center;
          gap: 8px;
          margin-bottom: 12px;
          color: var(--muted);
          font-size: 13px;
        }}

        .path {{
          color: #d7dce5;
          font-weight: 650;
        }}

        .pill {{
          background: rgba(255, 255, 255, 0.06);
          border: 1px solid var(--border);
          border-radius: 999px;
          padding: 2px 8px;
        }}

        pre {{
          white-space: pre-wrap;
          word-wrap: break-word;
          margin: 0;
          font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
          font-size: 14px;
          color: #f4f6fb;
        }}

        mark {{
          background: rgba(255, 159, 67, 0.22);
          color: #ffb86c;
          padding: 0.05em 0.2em;
          border-radius: 5px;
          font-weight: 800;
        }}

        .empty {{
          color: var(--muted);
          background: var(--panel);
          border: 1px dashed var(--border);
          border-radius: 18px;
          padding: 24px;
        }}
      </style>
    </head>
    <body>
      <main>
        <h1>Logseq Semantic Search</h1>
        <div class="subtitle">Local notes, local embeddings, browser-shaped lantern.</div>

        <form method="get" action="/">
          <input
            type="text"
            name="q"
            value="{html.escape(q)}"
            placeholder="Search your notes..."
            autofocus
          />
          <input type="hidden" name="n" value="{n}" />
          <button type="submit">Search</button>
        </form>

        {
          f'<div class="summary">{len(rows)} results for <strong>{html.escape(q)}</strong></div>'
          if q.strip()
          else '<div class="empty">Type a search query to begin.</div>'
        }

        {result_cards}
      </main>
    </body>
    </html>
    """


@app.get("/random", response_class=HTMLResponse)
def get_random(
):
    #
    results = collection.get(
        include=["metadatas", "documents"]
    ) 
    i, id_ = random.choice(
        [(i, x) for (i,x) in enumerate(results["ids"])]
    )
    (page, chunk) = id_.split("::")
    i, (page, chunk), results["metadatas"][i]

    doc = results["documents"][i].replace("\n", "<br/>")

    return f"""
    <html>
    <body>
    <p>
    {i, (page, chunk), results["metadatas"][i]}<br/><br/>

    <pre>
- query: "query"
  hits:
    - "{id_}"
    </pre>
    </p><br/>
    <p>
    {doc}
    </p>
    </body>
    </html>
    """

favicon_path = 'favicon.ico'
favicon_path = 'favicon-61f4ee969f89f9936688a6c49b63173679a18780_2_1000x1000.jpeg'
@app.get('/favicon.ico', include_in_schema=False)
async def favicon():
    """
    # Source - https://stackoverflow.com/a/69065939
    # Posted by thisIlike, modified by community. See post 'Timeline' for change history
    # Retrieved 2026-06-07, License - CC BY-SA 4.0
    """
    return FileResponse(favicon_path)
