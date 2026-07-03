
import argparse
from pathlib import Path

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
            

def do():
    parser = define_parser()

    args = parser.parse_args()
    if args.command == "local":
        for path in Path(args.source_dir).glob("**/*.md"):
            print("processing {path}")

if __name__ == "__main__":    
    do()





