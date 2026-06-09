from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "agent-manifest.schema.json"
AGENTS_DIR = ROOT / "agents"


def load_schema() -> dict:
    import json

    with SCHEMA_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def load_manifest(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file)
    if not isinstance(data, dict):
        raise ValueError("manifest must be a YAML object")
    return data


def validate_manifest(path: Path, validator: Draft202012Validator) -> list[str]:
    errors: list[str] = []
    try:
        manifest = load_manifest(path)
    except Exception as exc:
        return [f"{path}: cannot read YAML: {exc}"]

    for error in sorted(validator.iter_errors(manifest), key=lambda item: item.path):
        field = ".".join(str(part) for part in error.absolute_path) or "<root>"
        errors.append(f"{path}: {field}: {error.message}")

    expected_name = f"{manifest.get('agent_id', '')}.yaml"
    if manifest.get("agent_id") and path.name != expected_name:
        errors.append(f"{path}: filename must be {expected_name}")

    return errors


def manifest_paths(paths: list[str]) -> list[Path]:
    if paths:
        return [Path(path) for path in paths]
    return sorted(AGENTS_DIR.glob("*.yaml"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate itinai agent manifests.")
    parser.add_argument("paths", nargs="*", help="Optional manifest paths to validate")
    parser.add_argument("--schema", type=str, default=None, help="Path to JSON schema file (optional)")
    args = parser.parse_args()

    if args.schema:
        schema_path = Path(args.schema)
        import json
        with schema_path.open("r", encoding="utf-8") as f:
            schema = json.load(f)
    else:
        schema = load_schema()
    
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    paths = manifest_paths(args.paths)

    if not paths:
        print("No agent manifests found.")
        return 0

    all_errors: list[str] = []
    for path in paths:
        all_errors.extend(validate_manifest(path, validator))

    if all_errors:
        for error in all_errors:
            print(error, file=sys.stderr)
        return 1

    print(f"Validated {len(paths)} manifest(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
