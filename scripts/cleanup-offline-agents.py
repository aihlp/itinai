from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = ROOT / "agents"
DEFAULT_FAILURE_THRESHOLD = 100


def load_health_state(path: Path | None) -> dict:
    if not path or not path.exists():
        return {"agents": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def load_manifest(agent_file: Path) -> dict:
    with agent_file.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file)
    if not isinstance(data, dict):
        raise ValueError(f"{agent_file} is not a YAML object")
    return data


def find_agents_to_remove(health_state: dict, threshold: int) -> list[dict]:
    """Найти агентов, превысивших порог последовательных неудач."""
    agents_to_remove = []
    
    for agent_id, state in health_state.get("agents", {}).items():
        consecutive_failures = state.get("consecutive_failures", 0)
        
        if consecutive_failures >= threshold:
            # Найти файл манифеста для этого агента
            manifest_path = None
            for yaml_file in AGENTS_DIR.glob("*.yaml"):
                try:
                    manifest = load_manifest(yaml_file)
                    if manifest.get("agent_id") == agent_id:
                        manifest_path = yaml_file
                        break
                except Exception:
                    continue
            
            if manifest_path:
                agents_to_remove.append({
                    "agent_id": agent_id,
                    "manifest_path": manifest_path,
                    "consecutive_failures": consecutive_failures,
                    "last_checked_at": state.get("last_checked_at", "unknown"),
                    "last_error": state.get("last_error", "unknown"),
                })
    
    return agents_to_remove


def generate_removal_list(agents_to_remove: list[dict]) -> str:
    """Сгенерировать список файлов для удаления в формате для xargs."""
    return "\n".join(str(agent["manifest_path"]) for agent in agents_to_remove)


def main() -> int:
    parser = argparse.ArgumentParser(description="Find offline agents to remove from registry.")
    parser.add_argument(
        "--health-state",
        default="health-state.json",
        help="Path to health state JSON file",
    )
    parser.add_argument(
        "--failure-threshold",
        type=int,
        default=DEFAULT_FAILURE_THRESHOLD,
        help="Number of consecutive failures before marking for removal (default: 100)",
    )
    parser.add_argument(
        "--output-file",
        default="agents-to-remove.txt",
        help="Output file with list of manifests to remove",
    )
    args = parser.parse_args()

    health_state = load_health_state(Path(args.health_state))
    agents_to_remove = find_agents_to_remove(health_state, args.failure_threshold)

    if agents_to_remove:
        output_path = Path(args.output_file)
        output_path.write_text(generate_removal_list(agents_to_remove), encoding="utf-8")
        
        print(f"Found {len(agents_to_remove)} agent(s) to remove:")
        for agent in agents_to_remove:
            print(f"  - {agent['agent_id']} ({agent['manifest_path']})")
            print(f"    Consecutive failures: {agent['consecutive_failures']}")
            print(f"    Last checked: {agent['last_checked_at']}")
            print(f"    Last error: {agent['last_error']}")
        print(f"\nRemoval list written to: {output_path}")
        return 0
    else:
        print("No agents found for removal.")
        # Создать пустой файл, чтобы следующие шаги могли его использовать
        output_path = Path(args.output_file)
        output_path.write_text("", encoding="utf-8")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
