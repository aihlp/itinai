from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import requests
import yaml


ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = ROOT / "agents"
DEFAULT_ENDPOINT = "https://itinai.com/wp-json/itinai/v1/sync"
DEFAULT_TIMEOUT_SECONDS = 20


def load_manifest(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file)
    if not isinstance(data, dict):
        raise ValueError(f"{path} is not a YAML object")
    return data


def load_health_report(path: Path | None) -> dict[str, dict[str, Any]]:
    if not path or not path.exists():
        return {}
    report = json.loads(path.read_text(encoding="utf-8"))
    return {
        item["agent_id"]: item
        for item in report.get("results", [])
        if isinstance(item, dict) and item.get("agent_id")
    }


def wordpress_payload(manifest: dict[str, Any], health: dict[str, Any] | None) -> dict[str, Any]:
    payload = dict(manifest)
    payload["description"] = payload.get("description") or payload.get("name") or payload["agent_id"]

    health_check = payload.get("health_check") if isinstance(payload.get("health_check"), dict) else {}
    health_payload = {
        "url": health_check.get("url") or payload.get("a2a_config", {}).get("agent_card_url", ""),
        "status": "unknown",
    }
    if health:
        health_payload["status"] = "online" if health.get("ok") else "offline"
        health_payload["last_checked"] = health.get("checked_at", "")
    payload["health"] = health_payload
    return payload


def sync_manifest(
    session: requests.Session,
    endpoint: str,
    token: str,
    manifest: dict[str, Any],
    health: dict[str, Any] | None,
    timeout: int,
) -> tuple[bool, str]:
    payload = wordpress_payload(manifest, health)
    response = session.post(
        endpoint,
        json=payload,
        timeout=timeout,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "itinai-github-sync/1.0",
            "X-WP-Key": token,
        },
    )
    if 200 <= response.status_code < 300:
        return True, f"{response.status_code}"
    return False, f"{response.status_code}: {response.text[:300]}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync ITINAI manifests to the WordPress Agents app.")
    parser.add_argument("--endpoint", default=os.environ.get("WP_SYNC_ENDPOINT", DEFAULT_ENDPOINT))
    parser.add_argument("--key-env", default="WP_KEY", help="Environment variable containing the WordPress key")
    parser.add_argument("--health-report", default="health-results.json")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    token = os.environ.get(args.key_env, "").strip()
    if not token:
        print(f"Skipping WordPress sync: {args.key_env} is not set.")
        return 0

    health = load_health_report(Path(args.health_report) if args.health_report else None)
    paths = sorted(AGENTS_DIR.glob("*.yaml"))
    if args.limit:
        paths = paths[: args.limit]

    success = 0
    failed = 0
    with requests.Session() as session:
        for path in paths:
            manifest = load_manifest(path)
            ok, detail = sync_manifest(
                session,
                args.endpoint,
                token,
                manifest,
                health.get(manifest["agent_id"]),
                args.timeout,
            )
            if ok:
                success += 1
                print(f"SYNC OK {manifest['agent_id']} {detail}")
            else:
                failed += 1
                print(f"SYNC FAIL {manifest['agent_id']} {detail}", file=sys.stderr)

    print(f"WordPress sync complete: success={success}, failed={failed}, endpoint={args.endpoint}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
