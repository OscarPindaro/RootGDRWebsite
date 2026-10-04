import argparse
import json
import sys
from pathlib import Path
from uuid import uuid4

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
        "seed-request",
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
        elif name == "capture-spec":
            operation.add_argument(
                "--purpose", choices=("predeploy", "weekly"), default="predeploy"
            )
        elif name == "seed-request":
            operation.add_argument("--bundle", required=True, type=Path)
            operation.add_argument("--email", required=True)
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
            print(capacity(plan.target, images, plan.helper_image_id).model_dump_json())
        elif args.operation == "current":
            current = current_deployment(plan.target)
            print(current.model_dump_json() if current else "null")
        elif args.operation == "schema":
            print(json.dumps(schema_heads(plan.target.database)))
        elif args.operation == "capture-spec":
            if args.purpose == "weekly":
                # A periodic copy is its own operation: it must not reuse the
                # deployment run ID, or its receipt would collide with the last one.
                plan.run_id = uuid4()
            print(
                recovery_spec(
                    plan, current_deployment(plan.target), args.purpose
                ).model_dump_json()
            )
        elif args.operation == "manifest":
            print(verified_manifest(plan).model_dump_json())
        elif args.operation == "rollback":
            previous = CurrentDeployment.model_validate_json(args.previous.read_bytes())
            before = json.loads(args.before.read_bytes())
            after = schema_heads(plan.target.database)
            print(json.dumps(rollback_allowed(previous, before, after)))
        elif args.operation == "seed-request":
            # Controller-only conversion: the standalone server copy never runs
            # this path, so PyYAML stays out of the pinned target environment.
            import yaml  # noqa: PLC0415

            if not args.bundle.is_file():
                raise BackupError("Seed bundle must be an existing file")
            print(
                json.dumps(
                    {
                        "owner_email": args.email,
                        "expected_commit": plan.artifact.commit,
                        "bundle": yaml.safe_load(args.bundle.read_text()),
                    }
                )
            )
        return 0
    except BackupError, ValidationError, OSError, ValueError:
        print(
            "Deployment boundary validation failed; no rollout authorized",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
