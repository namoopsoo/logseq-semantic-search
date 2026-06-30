# logseq-semantic-search

This repo defines a docker container, which embeds markdown notes, like logseq markdown notes for example, and then serves search against them. 

Embedding can be done in one shot if you have a fast host machine, or it can be done in shards over a kubernetes cluster, otherwise, reading and writing against blob storage like S3. Final embeddings get stored on a vector db like chromadb and served by the same docker container, with fast api.

# Installing
TBD

# Running
Locally, run the fast api app with,

```
uvicorn app:app --reload --host 127.0.0.1 --port 8000
```
