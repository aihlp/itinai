from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
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

    dynamic_data = payload.get("dynamic_data") if isinstance(payload.get("dynamic_data"), dict) else {}
    payload["commerce"] = {
        "catalogue_feed_url": dynamic_data.get("catalogue_feed_url", ""),
        "negotiation_protocol": dynamic_data.get("negotiation_protocol", ""),
        "negotiation_endpoint": dynamic_data.get("negotiation_endpoint", ""),
    }

    health_check = payload.get("health_check") if isinstance(payload.get("health_check"), dict) else {}
    health_payload = {
        "url": health_check.get("url") or payload.get("a2a_config", {}).get("agent_card_url", ""),
    }
    if health:
        health_payload["status"] = "online" if health.get("ok") else "offline"
        health_payload["last_checked"] = health.get("checked_at", "")
    payload["health"] = health_payload
    return payload


def basic_auth_header(username: str, password: str) -> str:
    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


def post_manifest(
    session: requests.Session,
    endpoint: str,
    username: str,
    app_password: str,
    sync_key: str,
    manifest: dict[str, Any],
    health: dict[str, Any] | None,
    timeout: int,
) -> tuple[bool, str]:
    payload = wordpress_payload(manifest, health)
    try:
        response = session.post(
            endpoint,
            json=payload,
            timeout=timeout,
            headers={
                "Accept": "application/json",
            "Authorization": basic_auth_header(username, app_password),
            "Content-Type": "application/json",
            "User-Agent": "itinai-github-sync/1.0",
            "X-ITINAI-Sync-Key": sync_key,
            "X-WP-Key": sync_key,
        },
    )
    except requests.RequestException as exc:
        return False, f"request failed: {exc}"

    if 200 <= response.status_code < 300:
        return True, f"{response.status_code}"
    return False, f"{response.status_code}: {response.text[:300]}"


def should_retry(detail: str) -> bool:
    retryable_prefixes = ("408:", "425:", "429:", "500:", "502:", "503:", "504:")
    return (
        detail.startswith("request failed:")
        or detail.startswith(retryable_prefixes)
        or (detail.startswith("404:") and '"rest_no_route"' in detail)
    )


def sync_manifest(
    session: requests.Session,
    endpoint: str,
    username: str,
    app_password: str,
    sync_key: str,
    manifest: dict[str, Any],
    health: dict[str, Any] | None,
    timeout: int,
    retry_swapped_auth: bool,
    retries: int,
    retry_delay: float,
) -> tuple[bool, str]:
    attempts = max(1, retries + 1)
    details: list[str] = []
    for attempt in range(1, attempts + 1):
        ok, detail = post_manifest(session, endpoint, username, app_password, sync_key, manifest, health, timeout)
        details.append(f"attempt {attempt}: {detail}")
        if ok or not should_retry(detail) or attempt == attempts:
            break
        time.sleep(retry_delay * attempt)

    if ok or not retry_swapped_auth or not detail.startswith("401:"):
        return ok, detail if len(details) == 1 else "; ".join(details)

    swapped_ok, swapped_detail = post_manifest(
        session,
        endpoint,
        app_password,
        username,
        sync_key,
        manifest,
        health,
        timeout,
    )
    if swapped_ok:
        return True, f"{swapped_detail} (swapped WP_KEY/WP_APP auth)"
    return False, f"{detail}; swapped auth also failed: {swapped_detail}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync ITINAI manifests to the WordPress Agents app.")
    parser.add_argument("paths", nargs="*", help="Manifest paths to sync. Defaults to all agents/*.yaml")
    parser.add_argument("--endpoint", default=os.environ.get("WP_SYNC_ENDPOINT", DEFAULT_ENDPOINT))
    parser.add_argument("--user-env", default="WP_USER", help="Environment variable containing the WordPress user")
    parser.add_argument("--password-env", default="WP_KEY", help="Environment variable containing the application password or sync key")
    parser.add_argument("--health-report", default="health-results.json")
    parser.add_argument("--paths-file", help="Newline-delimited manifest paths to sync")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--retries", type=int, default=3, help="Retries per manifest for transient network/server errors")
    parser.add_argument("--retry-delay", type=float, default=2.0, help="Base retry delay in seconds")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument(
        "--no-swapped-auth-retry",
        action="store_true",
        help="Do not retry Application Password auth with WP_KEY and WP_APP swapped",
    )
    args = parser.parse_args()
    endpoint = args.endpoint or DEFAULT_ENDPOINT

    username = os.environ.get(args.user_env, "").strip()
    app_password = os.environ.get(args.password_env, "").strip()
    sync_key = os.environ.get("WP_KEY", "").strip()
    if not username or not app_password:
        print(f"Skipping WordPress sync: {args.user_env} or {args.password_env} is not set.")
        return 0

    health = load_health_report(Path(args.health_report) if args.health_report else None)
    raw_paths = list(args.paths)
    if args.paths_file:
        paths_file = Path(args.paths_file)
        if paths_file.exists():
            raw_paths.extend(line.strip() for line in paths_file.read_text(encoding="utf-8").splitlines())

    paths = [Path(path) for path in raw_paths if path.strip()] if raw_paths else sorted(AGENTS_DIR.glob("*.yaml"))
    paths = sorted(path for path in paths if path.suffix in {".yaml", ".yml"} and path.exists())
    if args.limit:
        paths = paths[: args.limit]

    if not paths:
        print("No WordPress manifests to sync.")
        return 0

    success = 0
    failed = 0
    with requests.Session() as session:
        for path in paths:
            manifest = load_manifest(path)
            ok, detail = sync_manifest(
                session,
                endpoint,
                username,
                app_password,
                sync_key,
                manifest,
                health.get(manifest["agent_id"]),
                args.timeout,
                not args.no_swapped_auth_retry,
                args.retries,
                args.retry_delay,
            )
            if ok:
                success += 1
                print(f"SYNC OK {manifest['agent_id']} {detail}")
            else:
                failed += 1
                print(f"SYNC FAIL {manifest['agent_id']} {detail}", file=sys.stderr)

    print(f"WordPress sync complete: success={success}, failed={failed}, endpoint={endpoint}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
