from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml


ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = ROOT / "agents"
DEFAULT_TIMEOUT_SECONDS = 10


def load_manifest(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file)
    if not isinstance(data, dict):
        raise ValueError(f"{path} is not a YAML object")
    return data


def health_url(manifest: dict) -> str:
    health_check = manifest.get("health_check") or {}
    if health_check.get("url"):
        return health_check["url"]
    return manifest["a2a_config"]["agent_card_url"]


def check_agent(path: Path, timeout: int) -> dict:
    manifest = load_manifest(path)
    agent_id = manifest["agent_id"]
    url = health_url(manifest)
    started_at = datetime.now(timezone.utc).isoformat()

    try:
        response = requests.get(url, timeout=timeout, headers={"Accept": "application/json"})
        ok = response.status_code == 200
        return {
            "agent_id": agent_id,
            "manifest": str(path.relative_to(ROOT)),
            "url": url,
            "ok": ok,
            "status_code": response.status_code,
            "checked_at": started_at,
            "error": None if ok else f"Expected HTTP 200, got {response.status_code}",
        }
    except requests.RequestException as exc:
        return {
            "agent_id": agent_id,
            "manifest": str(path.relative_to(ROOT)),
            "url": url,
            "ok": False,
            "status_code": None,
            "checked_at": started_at,
            "error": str(exc),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check registered itinai agents.")
    parser.add_argument("--output", default="health-results.json", help="JSON output path")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    args = parser.parse_args()

    paths = sorted(AGENTS_DIR.glob("*.yaml"))
    results = [check_agent(path, args.timeout) for path in paths]
    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "total": len(results),
        "healthy": sum(1 for item in results if item["ok"]),
        "unhealthy": sum(1 for item in results if not item["ok"]),
        "results": results,
    }

    output_path = Path(args.output)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    for item in results:
        status = "OK" if item["ok"] else "FAIL"
        detail = item["status_code"] if item["status_code"] is not None else item["error"]
        print(f"{status} {item['agent_id']} {item['url']} {detail}")

    return 0 if report["unhealthy"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
