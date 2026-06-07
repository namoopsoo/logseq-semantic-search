import chromadb

from sentence_transformers import SentenceTransformer

model = SentenceTransformer("Qwen/Qwen3-Embedding-0.6B")
client = chromadb.PersistentClient(path="./chroma_logseq")
collection = client.get_collection("logseq_notes")

query = input("Search: ")
embedding = model.encode([query], normalize_embeddings=True).tolist()[0]

results = collection.query(
    query_embeddings=[embedding],
    n_results=8,
)

for doc, meta, dist in zip(
    results["documents"][0],
    results["metadatas"][0],
    results["distances"][0],
):
    print("\n---")
    print(meta["path"], "distance=", round(dist, 4))
    print(doc[:1000])