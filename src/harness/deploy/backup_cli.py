"""Small argv-only adapter for Ansible. Deployment orchestration stays in roles."""

import argparse
import sys
from pathlib import Path

from pydantic import ValidationError

from .backup import BackupError, capture, verify_bundle, write_private
from .backup_restore import restore_encrypted
from .backup_schemas import BackupReceipt, CaptureSpec, RestoreSpec, StorageSpec
from .backup_storage import initialize_storage, seal


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="operation", required=True)
    capture_parser = commands.add_parser("capture")
    capture_parser.add_argument("--spec", required=True, type=Path)
    capture_parser.add_argument("--directory", required=True, type=Path)
    verify_parser = commands.add_parser("verify")
    verify_parser.add_argument("--directory", required=True, type=Path)
    init_parser = commands.add_parser("init-storage")
    init_parser.add_argument("--storage", required=True, type=Path)
    seal_parser = commands.add_parser("seal")
    seal_parser.add_argument("--directory", required=True, type=Path)
    seal_parser.add_argument("--storage", required=True, type=Path)
    seal_parser.add_argument("--receipt", required=True, type=Path)
    restore_parser = commands.add_parser("restore")
    restore_parser.add_argument("--storage", required=True, type=Path)
    restore_parser.add_argument("--receipt", required=True, type=Path)
    restore_parser.add_argument("--spec", required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.operation == "capture":
            capture(
                CaptureSpec.model_validate_json(args.spec.read_bytes()), args.directory
            )
        elif args.operation == "verify":
            verify_bundle(args.directory)
        elif args.operation == "init-storage":
            initialize_storage(
                StorageSpec.model_validate_json(args.storage.read_bytes())
            )
        elif args.operation == "seal":
            receipt = seal(
                StorageSpec.model_validate_json(args.storage.read_bytes()),
                args.directory,
            )
            write_private(args.receipt, receipt.model_dump_json(indent=2).encode())
        elif args.operation == "restore":
            result = restore_encrypted(
                StorageSpec.model_validate_json(args.storage.read_bytes()),
                BackupReceipt.model_validate_json(args.receipt.read_bytes()),
                RestoreSpec.model_validate_json(args.spec.read_bytes()),
            )
            print(result.model_dump_json())
        print("Recovery operation verified")
        return 0
    except BackupError, ValidationError, OSError, ValueError:
        # Do not print validation input, SQL, credentials or subprocess stderr.
        print(
            "Recovery operation failed; migration gate remains closed", file=sys.stderr
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
