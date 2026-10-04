import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from .backup import BackupError
from .rollout import (
    capacity,
    current_deployment,
    plan_deployment,
    recovery_spec,
    schema_heads,
    transfer_images,
    verified_manifest,
    ImageTransfer,
)
from .rollout_schemas import (
    CurrentDeployment,
    DeploymentPlan,
    DeploymentSpec,
    rollback_allowed,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    operations = parser.add_subparsers(dest="operation", required=True)
    planning = operations.add_parser("plan")
    planning.add_argument("--spec", type=Path)
    planning.add_argument("--artifact", required=True, type=Path)
    for name in (
        "images",
        "space",
        "current",
        "schema",
        "capture-spec",
        "manifest",
        "rollback",
    ):
        operation = operations.add_parser(name)
        operation.add_argument("--plan", required=True, type=Path)
        if name == "images":
            operation.add_argument("--directory", required=True, type=Path)
        elif name == "space":
            operation.add_argument("--images", required=True, type=Path)
        elif name == "rollback":
            operation.add_argument("--previous", required=True, type=Path)
            operation.add_argument("--before", required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.operation == "plan":
            spec = DeploymentSpec.model_validate_json(
                args.spec.read_bytes() if args.spec else sys.stdin.buffer.read()
            )
            print(plan_deployment(spec, args.artifact).model_dump_json())
            return 0
        plan = DeploymentPlan.model_validate_json(args.plan.read_bytes())
        if args.operation == "images":
            images = transfer_images(plan, args.directory)
            print(json.dumps([image.model_dump(mode="json") for image in images]))
        elif args.operation == "space":
            images = [
                ImageTransfer.model_validate(item)
                for item in json.loads(args.images.read_bytes())
            ]
            print(capacity(plan.target, images).model_dump_json())
        elif args.operation == "current":
            current = current_deployment(plan.target)
            print(current.model_dump_json() if current else "null")
        elif args.operation == "schema":
            print(json.dumps(schema_heads(plan.target.database)))
        elif args.operation == "capture-spec":
            print(
                recovery_spec(plan, current_deployment(plan.target)).model_dump_json()
            )
        elif args.operation == "manifest":
            print(verified_manifest(plan).model_dump_json())
        elif args.operation == "rollback":
            previous = CurrentDeployment.model_validate_json(args.previous.read_bytes())
            before = json.loads(args.before.read_bytes())
            after = schema_heads(plan.target.database)
            print(json.dumps(rollback_allowed(previous, before, after)))
        return 0
    except BackupError, ValidationError, OSError, ValueError:
        print(
            "Deployment boundary validation failed; no rollout authorized",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
