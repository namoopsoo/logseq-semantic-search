import hashlib
import json
import os
import resource
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
    s3_client,
)

DEFAULT_MODEL_NAME = "Qwen/Qwen3-Embedding-0.6B"


def current_rss_mb() -> float | None:
    try:
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) / 1024
    except OSError:
        return None
    return None


def max_rss_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def log_progress(message: str) -> None:
    current = current_rss_mb()
    if current is None:
        memory = f"max_rss={max_rss_mb():.1f}MiB"
    else:
        memory = f"rss={current:.1f}MiB max_rss={max_rss_mb():.1f}MiB"
    shard = os.getenv("SHARD_INDEX", "0")
    print(f"[shard {shard}] {message} ({memory})", flush=True)


def chunks(text: str, size: int = 900, overlap: int = 150):
    # rough char chunking; close enough for v1
    i = 0
    while i < len(text):
        yield text[i : i + size]
        i += size - overlap


def iter_s3_markdown(fernet: Fernet | None) -> Iterable[MarkdownFile]:
    bucket = required_env("S3_BUCKET")
    prefix = os.getenv("S3_MARKDOWN_PREFIX", "")
    client = s3_client()
    paginator = client.get_paginator("list_objects_v2")
    page_count = 0
    object_count = 0
    markdown_count = 0
    shard_count = 0

    log_progress(f"listing s3://{bucket}/{prefix}")

    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        page_count += 1
        page_objects = page.get("Contents", [])
        object_count += len(page_objects)
        log_progress(f"listed page {page_count} with {len(page_objects)} objects")
        for obj in page_objects:
            key = obj["Key"]
            if not key.endswith(".md"):
                continue
            markdown_count += 1
            rel = key[len(prefix) :].lstrip("/") if prefix else key
            if not should_index_rel(rel):
                continue
            shard_count += 1
            log_progress(f"fetching {rel}")
            body = client.get_object(Bucket=bucket, Key=key)["Body"].read()
            plaintext = decrypt_if_needed(body, fernet)
            log_progress(f"yielding {rel} ({len(plaintext)} bytes)")
            yield MarkdownFile(
                rel=rel,
                fingerprint=f'{obj.get("ETag", "").strip(chr(34))}:{obj.get("LastModified", "")}',
                text=plaintext.decode("utf-8", errors="ignore"),
            )
    log_progress(
        f"finished S3 listing: pages={page_count} objects={object_count} markdown={markdown_count} shard_matches={shard_count}"
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
    shard_count = os.getenv("SHARD_COUNT", "1")
    shard_index = os.getenv("SHARD_INDEX", "0")
    log_progress(
        f"starting indexer source={source} shard_index={shard_index} shard_count={shard_count} "
        f"date_window={os.getenv('SHARD_DATE_START', '')}..{os.getenv('SHARD_DATE_END', '')}"
    )
    fernet = build_fernet_from_env()
    state = {}  # load_state()
    model_name = os.getenv("MODEL_NAME", DEFAULT_MODEL_NAME)
    hugging_face_cache = os.getenv("HF_CACHE_DIR", "/models")

    log_progress(f"loading model {model_name} from cache {hugging_face_cache}")
    model = SentenceTransformer(local_files_only=True, model_name_or_path=model_name, cache_folder=hugging_face_cache)
    log_progress(f"loaded model {model_name}")

    write_to_chroma = getenv_bool("WRITE_TO_CHROMA", True)
    collection = None
    if write_to_chroma:
        db_dir = required_env("DB_DIR")
        collection_name = required_env("COLLECTION")
        client = chromadb.PersistentClient(path=db_dir)
        collection = client.get_or_create_collection(collection_name)

    if source == "local":
        markdown_files = iter_local_markdown(fernet)
    elif source == "s3":
        markdown_files = iter_s3_markdown(fernet)
    else:
        raise ValueError("MARKDOWN_SOURCE must be 'local' or 's3'")

    processed_files = 0
    processed_chunks = 0
    for markdown_file in tqdm(markdown_files, mininterval=10):
        if markdown_file.rel in state and state[markdown_file.rel]["fingerprint"] == markdown_file.fingerprint:
            continue

        log_progress(f"processing {markdown_file.rel}")

        docs, ids, metas = [], [], []
        for j, chunk in enumerate(chunks(markdown_file.text)):
            if chunk.strip():
                ids.append(f"{markdown_file.rel}::{j}")
                docs.append(chunk)
                metas.append({"path": markdown_file.rel, "chunk": j})

        if not docs:
            state[markdown_file.rel] = {"fingerprint": markdown_file.fingerprint}
            save_state(state)
            log_progress(f"skipped {markdown_file.rel}: no non-empty chunks")
            continue

        log_progress(f"encoding {len(docs)} chunks from {markdown_file.rel}")
        embeddings = model.encode(docs, normalize_embeddings=True).tolist()
        log_progress(f"encoded {len(docs)} chunks from {markdown_file.rel}")
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
        processed_files += 1
        processed_chunks += len(docs)
        log_progress(f"indexed {len(docs)} chunks from {markdown_file.rel}")

    log_progress(f"finished indexer: processed_files={processed_files} processed_chunks={processed_chunks}")


if __name__ == "__main__":
    main()
