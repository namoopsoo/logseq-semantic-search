import os
import argparse
from pathlib import Path
from index_notes import build_fernet_from_env, encrypt_if_needed, decrypt_if_needed


dec = decrypt_if_needed(enc, fernet)

assert journal == dec.decode() 

def define_parser():
    # Main parser
    parser = argparse.ArgumentParser(description="Main CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    run_parser = subparsers.add_parser("local", help="local encrypt")
    run_parser.add_argument("--source-dir", action="store_true")
    run_parser.add_argument("--target-dir", action="store_true")
    run_parser.add_argument("--encryption-key", action="store_true")
    
    
    run_parser = subparsers.add_parser("s3", help="s3 encrypt")
    run_parser.add_argument("--source-dir", action="store_true")
    run_parser.add_argument("--target-dir", action="store_true")
    run_parser.add_argument("--bucket", action="store_true")
    run_parser.add_argument("--encryption-key", action="store_true")
    return parser
            
def prepare_encryption_key(args):
    """Prefer command line encryption key, but fall back to environmental variable key.
    """
    if args.encryption_key:
        os.environ["S3_ENCRYPTION_KEY"] = args.encryption_key

    fernet = build_fernet_from_env()
    return fernet


def do():
    parser = define_parser()

    args = parser.parse_args()

    fernet = prepare_encryption_key(args)
    source_dir = Path(args.source_dir)
    target_dir = Path(args.target_dir)

    if args.command == "local":
        for path in source_dir.glob("**/*.md"):

            journal = path.read_text().encode("utf-8")

            relative_path = path.relative_to(source_dir)
            target_path = target_dir / relative_path
            
            enc = encrypt_if_needed(journal, fernet).decode()

            target_path.write_text(enc)

            print(f"encrypting {path} --> {target_path}")


if __name__ == "__main__":    
    do()





