import os
from tqdm import tqdm
from pathlib import Path

from semantic_notes.note_utils import build_fernet_from_env, encrypt_if_needed, iter_local_markdown, getenv_bool


def do():
    fernet = build_fernet_from_env()

    markdown_files = iter_local_markdown(fernet)

    output_dir = Path(os.getenv("LOCAL_ENCRYPTED_NOTES_DIR"))

    if getenv_bool("WRITE_TO_LOCAL"):
        ...
        print("writing encrypted to local")
    elif getenv_bool("WRITE_TO_S3"):
        raise NotImplemented()

    for markdown_file in tqdm(markdown_files):
        relative_path = markdown_file.rel
        journal = markdown_file.text

        output_path = output_dir / relative_path
        output_path.parent.mkdir(parents=True, exist_ok=True)

        enc = encrypt_if_needed(journal, fernet).decode()

        output_path.write_text(enc)

        print(f"encrypting {relative_path} --> {output_path}")


if __name__ == "__main__":    
    do()





