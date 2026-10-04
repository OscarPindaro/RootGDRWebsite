import argparse
import json
import sys
from pathlib import Path
from uuid import uuid4

from pydantic import ValidationError

from .backup import BackupError
from .vikunja import (
    board_images,
    board_recovery_spec,
    bootstrap_board,
    finalize_board,
    initialize_board,
    plan_board,
    preflight_board,
    verify_board,
)
from .vikunja_schemas import VikunjaPlan, VikunjaSpec


def main() -> int:
    parser = argparse.ArgumentParser()
    operations = parser.add_subparsers(dest="operation", required=True)
    planning = operations.add_parser("plan")
    planning.add_argument("--compose", required=True, type=Path)
    images = operations.add_parser("images")
    images.add_argument("--directory", required=True, type=Path)
    for name in (
        "preflight",
        "initialize",
        "bootstrap",
        "verify",
        "finalize",
        "capture-spec",
    ):
        operation = operations.add_parser(name)
        operation.add_argument("--plan", required=True, type=Path)
        if name in {"initialize", "bootstrap", "verify", "finalize"}:
            operation.add_argument("--spec", type=Path)
        if name == "initialize":
            operation.add_argument("--compose", required=True, type=Path)
            operation.add_argument("--secret", required=True, type=Path)
        if name == "bootstrap":
            operation.add_argument("--provider", required=True)
        if name == "capture-spec":
            operation.add_argument(
                "--purpose", choices=("weekly", "predeploy"), default="weekly"
            )
    args = parser.parse_args()
    try:
        if args.operation == "images":
            print(
                json.dumps(
                    [
                        image.model_dump(mode="json")
                        for image in board_images(args.directory)
                    ]
                )
            )
            return 0
        if args.operation == "plan":
            spec = VikunjaSpec.model_validate_json(sys.stdin.buffer.read())
            print(plan_board(spec, args.compose).model_dump_json())
            return 0
        plan = VikunjaPlan.model_validate_json(args.plan.read_bytes())
        if args.operation == "preflight":
            print(preflight_board(plan).model_dump_json())
        elif args.operation == "capture-spec":
            plan.run_id = uuid4()
            print(board_recovery_spec(plan, args.purpose).model_dump_json())
        else:
            spec = VikunjaSpec.model_validate_json(
                args.spec.read_bytes() if args.spec else sys.stdin.buffer.read()
            )
            if args.operation == "initialize":
                print(
                    initialize_board(
                        plan, spec, args.compose, args.secret
                    ).model_dump_json()
                )
            elif args.operation == "bootstrap":
                bootstrap_board(plan, spec, args.provider)
            elif args.operation == "verify":
                verify_board(plan, spec)
            elif args.operation == "finalize":
                print(finalize_board(plan, spec).model_dump_json())
        return 0
    except BackupError, ValidationError, OSError, ValueError:
        print(
            "Board boundary failed; no deployment verified and no credentials disclosed",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
