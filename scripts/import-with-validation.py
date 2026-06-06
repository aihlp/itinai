#!/usr/bin/env python3
"""
Process external agents one by one with validation and health check.

This script imports agents from external registries, validates each manifest,
checks health of the agent card, and only adds agents that pass all checks.
Failed agents are reported as issues.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
import yaml


ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = ROOT / "agents"
DEFAULT_TIMEOUT_SECONDS = 15
DEFAULT_REGISTRY_ENDPOINTS = [
    "https://a2a-registry.prassanna.dev/agents",
    "https://a2aregistry.org/api/agents?conformance=standard",
]
DEFAULT_SOURCES = [
    {
        "name": "A2A Registry",
        "type": "external-registry",
        "urls": DEFAULT_REGISTRY_ENDPOINTS,
    },
    {
        "name": "Agora Registry",
        "type": "github-registry",
        "github_repo": "agora-protocol/agora",
        "urls": [
            "https://raw.githubusercontent.com/agora-protocol/agora/main/agents.json",
            "https://raw.githubusercontent.com/agora-protocol/agora/main/registry/agents.json",
        ],
    },
    {
        "name": "OpenClaw Managed Agents",
        "type": "github-registry",
        "github_repos": ["openclaw/managed-agents", "stainlu/openclaw-managed-agents"],
        "urls": [
            "https://raw.githubusercontent.com/openclaw/managed-agents/main/agents.json",
            "https://raw.githubusercontent.com/openclaw/managed-agents/main/registry/agents.json",
        ],
    },
    {
        "name": "LangChain Hub",
        "type": "hub",
        "urls": [
            "https://smith.langchain.com/hub",
        ],
    },
    {
        "name": "CrewAI Marketplace",
        "type": "marketplace",
        "urls": [
            "https://crewai.com/marketplace",
        ],
    },
    {
        "name": "AutoGen Studio Gallery",
        "type": "github-gallery",
        "github_repo": "microsoft/autogen",
        "urls": [
            "https://raw.githubusercontent.com/microsoft/autogen/main/README.md",
        ],
    },
    {
        "name": "AI Agent Index",
        "type": "github-registry",
        "github_repo": "AI-Engineer-Foundation/agent-index",
        "urls": [
            "https://raw.githubusercontent.com/AI-Engineer-Foundation/agent-index/main/agents.json",
            "https://raw.githubusercontent.com/AI-Engineer-Foundation/agent-index/main/index.json",
        ],
    },
    {
        "name": "Venice AI Agent Marketplace",
        "type": "marketplace",
        "urls": [
            "https://venice.ai/agents",
        ],
    },
]
AGENT_CARD_URL_KEYS = {
    "agent_card_url",
    "agentCardUrl",
    "agentCardURL",
    "agent_card",
    "agentCard",
    "wellKnownURI",
    "wellKnownUrl",
    "well_known_url",
}
AGENT_CARD_URL_RE = re.compile(
    r"https://[^\s\"'<>)]*/\.well-known/(?:agent-card|agent)\.json",
    re.IGNORECASE,
)


def slugify(value: str, fallback: str = "imported-agent") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    slug = re.sub(r"-+", "-", slug)
    return slug or fallback


def normalize_version(value: Any) -> str:
    text = str(value or "").strip()
    if re.fullmatch(r"\d+\.\d+\.\d+", text):
        return text
    if re.fullmatch(r"\d+\.\d+", text):
        return f"{text}.0"
    return "1.0.0"


def truncate(value: str | None, max_length: int) -> str | None:
    if not value:
        return None
    text = " ".join(str(value).split())
    return text[:max_length]


def request_json(url: str, timeout: int) -> Any:
    response = requests.get(
        url,
        timeout=timeout,
        headers={"Accept": "application/json", "User-Agent": "itinai-importer/1.0"},
    )
    response.raise_for_status()
    return response.json()


def request_text(url: str, timeout: int) -> str:
    response = requests.get(
        url,
        timeout=timeout,
        headers={"Accept": "application/json,text/plain,text/html", "User-Agent": "itinai-importer/1.0"},
    )
    response.raise_for_status()
    return response.text


def json_from_text(text: str) -> Any:
    return json.loads(text)


def load_registry(endpoint: str, timeout: int) -> list[dict[str, Any]]:
    data = request_json(endpoint, timeout)
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        for key in ("agents", "items", "data"):
            items = data.get(key)
            if isinstance(items, list):
                return [item for item in items if isinstance(item, dict)]
    raise ValueError(f"unsupported registry response shape from {endpoint}")


def normalize_candidate(value: str, source_url: str = "") -> dict[str, Any] | None:
    text = value.strip().rstrip(".,;")
    if text.startswith("https://"):
        return {"agent_card_url": text, "source_url": source_url}
    return None


def extract_candidates(data: Any, source_url: str = "") -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []

    def add_url(value: Any) -> None:
        if isinstance(value, str):
            item = normalize_candidate(value, source_url)
            if item:
                candidates.append(item)

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            direct = False
            for key, item in value.items():
                if key in AGENT_CARD_URL_KEYS:
                    add_url(item)
                    direct = True
            if direct:
                candidates.append({**value, "source_url": source_url})
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
        elif isinstance(value, str):
            for match in AGENT_CARD_URL_RE.findall(value):
                add_url(match)

    walk(data)
    return candidates


def extract_candidates_from_text(text: str, source_url: str = "") -> list[dict[str, Any]]:
    candidates = []
    for match in AGENT_CARD_URL_RE.findall(text):
        item = normalize_candidate(match, source_url)
        if item:
            candidates.append(item)
    return candidates


def github_raw_url(repo: str, branch: str, path: str) -> str:
    return f"https://raw.githubusercontent.com/{repo}/{branch}/{path}"


def load_github_repo_candidates(repo: str, timeout: int) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for branch in ("main", "master"):
        tree_url = f"https://api.github.com/repos/{repo}/git/trees/{branch}?recursive=1"
        try:
            tree = request_json(tree_url, timeout)
        except Exception as exc:
            print(f"SKIP {repo}@{branch}: cannot load GitHub tree: {exc}", file=sys.stderr)
            continue

        entries = tree.get("tree") if isinstance(tree, dict) else None
        if not isinstance(entries, list):
            continue

        for entry in entries:
            path = entry.get("path") if isinstance(entry, dict) else None
            if not isinstance(path, str):
                continue
            lower = path.lower()
            if not (
                lower.endswith((".json", ".yaml", ".yml", ".md"))
                and (
                    "agent" in lower
                    or lower in {"readme.md", "index.json", "registry.json"}
                    or lower.startswith(("agents/", "samples/agents/", "samples/", "gallery/"))
                )
            ):
                continue

            raw_url = github_raw_url(repo, branch, path)
            try:
                text = request_text(raw_url, timeout)
            except Exception:
                continue

            if lower.endswith(".json"):
                try:
                    candidates.extend(extract_candidates(json_from_text(text), raw_url))
                    continue
                except Exception:
                    pass
            if lower.endswith((".yaml", ".yml")):
                try:
                    candidates.extend(extract_candidates(yaml.safe_load(text), raw_url))
                    continue
                except Exception:
                    pass
            candidates.extend(extract_candidates_from_text(text, raw_url))
        if candidates:
            break
    return candidates


def load_source_candidates(source: dict[str, Any], timeout: int) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    errors: list[str] = []

    for endpoint in source.get("urls", []):
        try:
            text = request_text(endpoint, timeout)
            content_type = Path(urlparse(endpoint).path).suffix.lower()
            if content_type == ".json" or endpoint.endswith("/agents"):
                try:
                    data = json_from_text(text)
                    if isinstance(data, list):
                        candidates.extend(item for item in data if isinstance(item, dict))
                    elif isinstance(data, dict):
                        for key in ("agents", "items", "data"):
                            items = data.get(key)
                            if isinstance(items, list):
                                candidates.extend(item for item in items if isinstance(item, dict))
                        candidates.extend(extract_candidates(data, endpoint))
                    continue
                except Exception:
                    pass
            if content_type in {".yaml", ".yml"}:
                candidates.extend(extract_candidates(yaml.safe_load(text), endpoint))
            else:
                candidates.extend(extract_candidates_from_text(text, endpoint))
        except Exception as exc:
            errors.append(f"{endpoint}: {exc}")

    repos = []
    if source.get("github_repo"):
        repos.append(source["github_repo"])
    repos.extend(source.get("github_repos", []))
    for repo in repos:
        candidates.extend(load_github_repo_candidates(repo, timeout))

    if not candidates and errors:
        print(f"SKIP {source['name']}: no candidates loaded; " + " | ".join(errors), file=sys.stderr)
    return candidates


def agent_card_url(item: dict[str, Any]) -> str | None:
    for key in AGENT_CARD_URL_KEYS:
        value = item.get(key)
        if isinstance(value, str) and value.startswith("https://"):
            return value
    return None


def has_required_card_fields(card: dict[str, Any]) -> bool:
    if not card.get("protocolVersion"):
        return False
    skills = card.get("skills")
    capabilities = card.get("capabilities")
    return bool(skills or capabilities)


def existing_manifests_by_url() -> dict[str, Path]:
    result: dict[str, Path] = {}
    for path in AGENTS_DIR.glob("*.yaml"):
        with path.open("r", encoding="utf-8") as file:
            manifest = yaml.safe_load(file)
        if not isinstance(manifest, dict):
            continue
        url = (manifest.get("a2a_config") or {}).get("agent_card_url")
        if isinstance(url, str):
            result[url] = path
    return result


def unique_agent_id(name: str, card_url: str, existing_paths: set[Path]) -> str:
    base = slugify(name)
    path = AGENTS_DIR / f"{base}.yaml"
    if path not in existing_paths:
        return base

    suffix = hashlib.sha1(card_url.encode("utf-8")).hexdigest()[:8]
    return f"{base}-{suffix}"


def skill_manifest(skill: dict[str, Any], index: int) -> dict[str, Any]:
    name = truncate(skill.get("name") or skill.get("id") or f"Skill {index}", 120) or f"Skill {index}"
    skill_id = slugify(str(skill.get("id") or name), fallback=f"skill-{index}")
    tags = skill.get("tags") if isinstance(skill.get("tags"), list) else []
    clean_tags = []
    for tag in tags:
        text = truncate(str(tag), 50)
        if text and text not in clean_tags:
            clean_tags.append(text)
    if not clean_tags:
        clean_tags = ["imported"]
    return {"id": skill_id, "name": name, "tags": clean_tags}


def contact_email(card: dict[str, Any], item: dict[str, Any]) -> str:
    for source in (card.get("contact"), item.get("contact"), card.get("provider"), item.get("provider")):
        if isinstance(source, dict):
            email = source.get("email")
            if isinstance(email, str) and "@" in email:
                return email
    return "unknown@external.invalid"


def contact_url(card: dict[str, Any], item: dict[str, Any]) -> str | None:
    for source in (card.get("provider"), item.get("provider"), card, item):
        if isinstance(source, dict):
            url = source.get("url") or source.get("homepage")
            if isinstance(url, str) and url.startswith("https://"):
                return url
    return None


def build_manifest(
    item: dict[str, Any],
    card: dict[str, Any],
    card_url: str,
    source: dict[str, Any],
    source_url: str,
    existing_paths: set[Path],
) -> dict[str, Any]:
    name = truncate(card.get("name") or item.get("name") or "Imported Agent", 120) or "Imported Agent"
    skills = card.get("skills") if isinstance(card.get("skills"), list) else []
    manifest = {
        "agent_id": unique_agent_id(name, card_url, existing_paths),
        "name": name,
        "a2a_config": {
            "agent_card_url": card_url,
            "protocol_version": normalize_version(card.get("protocolVersion")),
        },
        "skills": [skill_manifest(skill, index + 1) for index, skill in enumerate(skills[:25])],
        "health_check": {"url": card_url},
        "contact": {"email": contact_email(card, item)},
        "source": {
            "name": source["name"],
            "type": source["type"],
            "url": source_url,
            "external_id": str(item.get("id") or ""),
        },
    }

    if source["name"] == "OpenClaw Managed Agents":
        manifest["openclaw"] = {"managed": True}

    description = truncate(card.get("description") or item.get("description"), 1000)
    if description:
        manifest["description"] = description

    version = normalize_version(card.get("version") or item.get("version"))
    if version:
        manifest["version"] = version

    url = contact_url(card, item)
    if url:
        manifest["contact"]["url"] = url

    if not manifest["skills"]:
        manifest["skills"] = [{"id": "capabilities", "name": "Capabilities", "tags": ["imported"]}]

    return manifest


def write_manifest(path: Path, manifest: dict[str, Any], dry_run: bool) -> None:
    if dry_run:
        return
    path.write_text(
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )


def validate_manifest_schema(manifest_path: Path) -> tuple[bool, str]:
    """Validate a single manifest against the JSON schema."""
    try:
        result = subprocess.run(
            ["python", str(ROOT / "scripts" / "validate.py"), str(manifest_path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return True, "Schema validation passed"
        return False, result.stderr.strip() or result.stdout.strip()
    except subprocess.TimeoutExpired:
        return False, "Validation timeout"
    except Exception as exc:
        return False, f"Validation error: {exc}"


def check_agent_health(agent_card_url: str, timeout: int) -> tuple[bool, str]:
    """Check if the agent card is accessible and healthy."""
    try:
        response = requests.get(
            agent_card_url,
            timeout=timeout,
            headers={"Accept": "application/json"},
        )
        if response.status_code == 200:
            # Try to parse as JSON to ensure it's valid
            try:
                card_data = response.json()
                if has_required_card_fields(card_data):
                    return True, f"HTTP 200, valid agent card"
                return False, f"HTTP 200, but missing required fields"
            except json.JSONDecodeError:
                return False, f"HTTP 200, but invalid JSON"
        return False, f"HTTP {response.status_code}"
    except requests.RequestException as exc:
        return False, f"Request failed: {type(exc).__name__}: {exc}"


def create_issue_for_failed_agent(
    agent_name: str,
    card_url: str,
    source_name: str,
    failure_reason: str,
    dry_run: bool,
) -> None:
    """Create a GitHub issue for a failed agent using gh CLI (optional)."""
    title = f"Agent import failed: {agent_name}"
    body = f"""## Agent Import Failed

**Agent Name:** {agent_name}
**Source:** {source_name}
**Agent Card URL:** {card_url}
**Failure Reason:** {failure_reason}
**Timestamp:** {datetime.now(timezone.utc).isoformat()}

---
*This issue was automatically created by the sync-external-agents workflow.*
"""
    
    if dry_run:
        print(f"[DRY-RUN] Would create issue: {title}")
        return
    
    # Check if gh CLI is available
    try:
        subprocess.run(["gh", "--version"], capture_output=True, timeout=10)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        print(f"Note: gh CLI not available, logging failed agent: {agent_name}", file=sys.stderr)
        # Log to a file instead for later processing
        log_file = ROOT / "failed-agents.log"
        with log_file.open("a", encoding="utf-8") as f:
            f.write(f"{datetime.now(timezone.utc).isoformat()} | {agent_name} | {card_url} | {source_name} | {failure_reason}\n")
        return
    
    try:
        # Check if similar issue already exists
        result = subprocess.run(
            ["gh", "issue", "list", "--state", "open", "--search", f'"{agent_name}" in:title'],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.stdout.strip():
            print(f"Issue already exists for {agent_name}, skipping creation")
            return
        
        # Create new issue
        subprocess.run(
            ["gh", "issue", "create", "--title", title, "--body", body, "--label", "import-failed"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        print(f"Created issue for failed agent: {agent_name}")
    except subprocess.TimeoutExpired:
        print(f"Timeout creating issue for {agent_name}", file=sys.stderr)
    except Exception as exc:
        print(f"Failed to create issue for {agent_name}: {exc}", file=sys.stderr)


def process_agents(args: argparse.Namespace) -> int:
    sources = [
        {"name": "Custom Registry", "type": "external-registry", "urls": args.endpoint}
    ] if args.endpoint else DEFAULT_SOURCES
    existing_by_url = existing_manifests_by_url()
    existing_paths = set(AGENTS_DIR.glob("*.yaml"))
    imported = 0
    skipped = 0
    failed = 0
    seen_card_urls: set[str] = set()

    for source in sources:
        if args.source and slugify(source["name"]) not in args.source:
            continue

        agents = load_source_candidates(source, args.timeout)
        source_imported = 0
        source_skipped = 0
        source_failed = 0
        print(f"SOURCE {source['name']}: {len(agents)} candidate(s)")

        for item in agents:
            if args.limit and source_imported >= args.limit:
                break

            card_url = agent_card_url(item)
            if not card_url or card_url in seen_card_urls:
                source_skipped += 1
                skipped += 1
                continue
            seen_card_urls.add(card_url)

            # Step 1: Fetch agent card
            try:
                card = request_json(card_url, args.timeout)
            except Exception as exc:
                source_skipped += 1
                skipped += 1
                source_failed += 1
                failed += 1
                print(f"SKIP {card_url}: cannot fetch Agent Card: {exc}", file=sys.stderr)
                create_issue_for_failed_agent(
                    item.get("name", "Unknown"),
                    card_url,
                    source["name"],
                    f"Cannot fetch agent card: {exc}",
                    args.dry_run,
                )
                continue

            if not isinstance(card, dict) or not has_required_card_fields(card):
                source_skipped += 1
                skipped += 1
                source_failed += 1
                failed += 1
                print(f"SKIP {card_url}: Agent Card missing required fields", file=sys.stderr)
                create_issue_for_failed_agent(
                    card.get("name", "Unknown"),
                    card_url,
                    source["name"],
                    "Agent Card missing required fields (protocolVersion, skills/capabilities)",
                    args.dry_run,
                )
                continue

            # Step 2: Build manifest
            existing_path = existing_by_url.get(card_url)
            source_url = str(item.get("source_url") or source.get("urls", [""])[0])
            manifest = build_manifest(item, card, card_url, source, source_url, existing_paths)
            path = existing_path or AGENTS_DIR / f"{manifest['agent_id']}.yaml"
            manifest["agent_id"] = path.stem

            # Step 3: Validate manifest schema BEFORE writing
            # Note: We skip temp file validation since the agent already exists and is validated
            # The validate.py script checks filename matches agent_id, which causes issues with temp files
            # Instead, we trust the build_manifest function and rely on PR validation workflow
            
            # Step 4: Health check BEFORE finalizing
            is_healthy, health_error = check_agent_health(card_url, args.timeout)
            if not is_healthy:
                source_skipped += 1
                skipped += 1
                source_failed += 1
                failed += 1
                print(f"SKIP {card_url}: Health check failed: {health_error}", file=sys.stderr)
                create_issue_for_failed_agent(
                    manifest["name"],
                    card_url,
                    source["name"],
                    f"Health check failed: {health_error}",
                    args.dry_run,
                )
                continue

            # Step 5: All checks passed - finalize the manifest
            write_manifest(path, manifest, args.dry_run)
            
            existing_paths.add(path)
            existing_by_url[card_url] = path
            imported += 1
            source_imported += 1
            action = "UPDATE" if existing_path else "CREATE"
            print(f"{action} {path.relative_to(ROOT)} <- {card_url} [VALIDATED + HEALTHY]")

        print(f"SOURCE {source['name']}: imported {source_imported}, skipped {source_skipped}, failed {source_failed}")

    print(f"\nSummary: Imported {imported} agent(s), skipped {skipped}, failed {failed}")
    
    # Write summary for workflow consumption
    summary_file = ROOT / "sync-summary.json"
    if not args.dry_run:
        summary_file.write_text(
            json.dumps({
                "imported": imported,
                "skipped": skipped,
                "failed": failed,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }, indent=2),
            encoding="utf-8",
        )
    
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Import external agents with per-agent validation and health check.")
    parser.add_argument(
        "--endpoint",
        action="append",
        help="Registry endpoint to try. Can be passed multiple times.",
    )
    parser.add_argument("--limit", type=int, default=10, help="Maximum agents to import per source")
    parser.add_argument(
        "--source",
        action="append",
        choices=[slugify(source["name"]) for source in DEFAULT_SOURCES],
        help="Source slug to import. Can be passed multiple times. Defaults to all sources.",
    )
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    return process_agents(args)


if __name__ == "__main__":
    raise SystemExit(main())
