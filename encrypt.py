import os
from tqdm import tqdm
from pathlib import Path
from index_notes import (
    build_fernet_from_env, encrypt_if_needed, iter_local_markdown, required_env, getenv_bool,
)


def do():
    fernet = build_fernet_from_env()

    markdown_files = iter_local_markdown(fernet)

    # logseq_dir = Path(required_env("LOGSEQ_DIR"))
    # local_target_dir = os.getenv("LOCAL_TARGET_DIR")

    output_dir = Path(required_env("LOCAL_EMBEDDINGS_DIR"))

    if getenv_bool("WRITE_TO_LOCAL"):
        ...
        print("writing encrypted to local")
    elif getenv_bool("WRITE_TO_S3"):
        raise NotImplemented()

    for markdown_file in tqdm(markdown_files):
        relative_path = markdown_file.rel
        journal = markdown_file.text

        output_path = output_dir / relative_path
        
        enc = encrypt_if_needed(journal, fernet).decode()

        output_path.write_text(enc)

        print(f"encrypting {relative_path} --> {output_path}")


if __name__ == "__main__":    
    do()





