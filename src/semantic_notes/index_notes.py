import hashlib
import json
import os
from pathlib import Path
from typing import Iterable

import chromadb
from cryptography.fernet import Fernet
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

from semantic_notes.note_utils import (
    build_fernet_from_env,
    decrypt_if_needed,
    encrypt_if_needed,
    getenv_bool,
    iter_local_markdown,
    MarkdownFile,
    required_env,
    should_index_rel,
)

DEFAULT_MODEL_NAME = "Qwen/Qwen3-Embedding-0.6B"


def chunks(text: str, size: int = 900, overlap: int = 150):
    # rough char chunking; close enough for v1
    i = 0
    while i < len(text):
        yield text[i : i + size]
        i += size - overlap


def s3_client():
    import boto3

    return boto3.client("s3", region_name=os.getenv("AWS_REGION"))


def iter_s3_markdown(fernet: Fernet | None) -> Iterable[MarkdownFile]:
    bucket = required_env("S3_BUCKET")
    prefix = os.getenv("S3_MARKDOWN_PREFIX", "")
    client = s3_client()
    paginator = client.get_paginator("list_objects_v2")

    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if not key.endswith(".md"):
                continue
            rel = key[len(prefix) :].lstrip("/") if prefix else key
            if not should_index_rel(rel):
                continue
            body = client.get_object(Bucket=bucket, Key=key)["Body"].read()
            plaintext = decrypt_if_needed(body, fernet)
            yield MarkdownFile(
                rel=rel,
                fingerprint=f'{obj.get("ETag", "").strip(chr(34))}:{obj.get("LastModified", "")}',
                text=plaintext.decode("utf-8", errors="ignore"),
            )


def serialize_embedding_records(records: list[dict]) -> bytes:
    return "\n".join(json.dumps(record, separators=(",", ":")) for record in records).encode("utf-8")


def embedding_output_key(payload: bytes) -> str:
    prefix = os.getenv("S3_EMBEDDINGS_PREFIX", "embeddings/").rstrip("/")
    shard_index = os.getenv("SHARD_INDEX", "0")
    digest = hashlib.sha256(payload).hexdigest()[:16]
    return f"{prefix}/shard-{shard_index}/{digest}.jsonl"


def write_embeddings_to_s3(records: list[dict], fernet: Fernet | None) -> None:
    if not records or not getenv_bool("WRITE_TO_S3"):
        return
    bucket = required_env("S3_BUCKET")
    payload = serialize_embedding_records(records)
    encrypted_payload = encrypt_if_needed(payload, fernet)
    key = embedding_output_key(payload)
    s3_client().put_object(Bucket=bucket, Key=key, Body=encrypted_payload)
    print(f"Wrote {len(records)} embedding records to s3://{bucket}/{key}")


def write_embeddings_to_local(records: list[dict], fernet: Fernet | None) -> None:
    if not records or not getenv_bool("WRITE_TO_LOCAL"):
        return
    if fernet is None:
        raise ValueError("S3_ENCRYPTION_KEY must be set when WRITE_TO_LOCAL is true")

    payload = serialize_embedding_records(records)
    encrypted_payload = encrypt_if_needed(payload, fernet)
    output_path = Path(required_env("LOCAL_EMBEDDINGS_DIR")) / embedding_output_key(payload)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(encrypted_payload)
    print(f"Wrote {len(records)} encrypted embedding records to {output_path}")


def load_state() -> dict:
    state_file = Path(os.getenv("STATE_FILE", "index_state.json"))
    if state_file.exists():
        return json.loads(state_file.read_text())
    return {}


def save_state(state: dict) -> None:
    state_file = Path(os.getenv("STATE_FILE", "index_state.json"))
    state_file.write_text(json.dumps(state, indent=2))


def main() -> None:
    source = os.getenv("MARKDOWN_SOURCE", "local").lower()
    fernet = build_fernet_from_env()
    state = load_state()
    model_name = os.getenv("MODEL_NAME", DEFAULT_MODEL_NAME)
    hugging_face_cache = os.getenv("HF_CACHE_DIR", "/models")

    model = SentenceTransformer(local_files_only=True, model_name_or_path=model_name, cache_folder=hugging_face_cache)

    write_to_chroma = getenv_bool("WRITE_TO_CHROMA", True)
    collection = None
    if write_to_chroma:
        db_dir = required_env("DB_DIR")
        collection_name = required_env("COLLECTION")
        client = chromadb.PersistentClient(path=db_dir)
        collection = client.get_or_create_collection(collection_name)

    if source == "local":
        markdown_files = iter_local_markdown()
    elif source == "s3":
        markdown_files = iter_s3_markdown(fernet)
    else:
        raise ValueError("MARKDOWN_SOURCE must be 'local' or 's3'")

    for markdown_file in tqdm(markdown_files):
        if markdown_file.rel in state and state[markdown_file.rel]["fingerprint"] == markdown_file.fingerprint:
            continue

        docs, ids, metas = [], [], []
        for j, chunk in enumerate(chunks(markdown_file.text)):
            if chunk.strip():
                ids.append(f"{markdown_file.rel}::{j}")
                docs.append(chunk)
                metas.append({"path": markdown_file.rel, "chunk": j})

        if not docs:
            state[markdown_file.rel] = {"fingerprint": markdown_file.fingerprint}
            save_state(state)
            continue

        embeddings = model.encode(docs, normalize_embeddings=True).tolist()
        if collection is not None:
            collection.upsert(ids=ids, documents=docs, embeddings=embeddings, metadatas=metas)

        records = [
            {"id": id_, "document": doc, "embedding": embedding, "metadata": meta}
            for id_, doc, embedding, meta in zip(ids, docs, embeddings, metas)
        ]
        write_embeddings_to_s3(records, fernet)
        write_embeddings_to_local(records, fernet)
        state[markdown_file.rel] = {"fingerprint": markdown_file.fingerprint}
        save_state(state)
        print(f"Indexed {len(docs)} chunks from {markdown_file.rel}")


if __name__ == "__main__":
    main()
