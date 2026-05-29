from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path
from typing import Any

import requests
import yaml


ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = ROOT / "agents"
DEFAULT_TIMEOUT_SECONDS = 15
DEFAULT_REGISTRY_ENDPOINTS = [
    "https://a2a-registry.prassanna.dev/agents",
    "https://a2aregistry.org/api/agents?conformance=standard",
]


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


def load_first_registry(endpoints: list[str], timeout: int) -> tuple[str, list[dict[str, Any]]]:
    errors: list[str] = []
    for endpoint in endpoints:
        try:
            agents = load_registry(endpoint, timeout)
            return endpoint, agents
        except Exception as exc:
            errors.append(f"{endpoint}: {exc}")
    raise RuntimeError("no registry endpoint could be loaded:\n" + "\n".join(errors))


def agent_card_url(item: dict[str, Any]) -> str | None:
    value = item.get("agent_card_url") or item.get("agentCardUrl") or item.get("wellKnownURI")
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
    source_endpoint: str,
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
            "name": "A2A Registry",
            "type": "external-registry",
            "url": source_endpoint,
            "external_id": str(item.get("id") or ""),
        },
    }

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


def import_agents(args: argparse.Namespace) -> int:
    endpoints = args.endpoint or DEFAULT_REGISTRY_ENDPOINTS
    source_endpoint, agents = load_first_registry(endpoints, args.timeout)
    existing_by_url = existing_manifests_by_url()
    existing_paths = set(AGENTS_DIR.glob("*.yaml"))
    imported = 0
    skipped = 0

    for item in agents:
        if args.limit and imported >= args.limit:
            break

        card_url = agent_card_url(item)
        if not card_url:
            skipped += 1
            continue

        try:
            card = request_json(card_url, args.timeout)
        except Exception as exc:
            skipped += 1
            print(f"SKIP {card_url}: cannot fetch Agent Card: {exc}", file=sys.stderr)
            continue

        if not isinstance(card, dict) or not has_required_card_fields(card):
            skipped += 1
            print(f"SKIP {card_url}: Agent Card missing required fields", file=sys.stderr)
            continue

        existing_path = existing_by_url.get(card_url)
        manifest = build_manifest(item, card, card_url, source_endpoint, existing_paths)
        path = existing_path or AGENTS_DIR / f"{manifest['agent_id']}.yaml"
        manifest["agent_id"] = path.stem
        write_manifest(path, manifest, args.dry_run)
        existing_paths.add(path)
        existing_by_url[card_url] = path
        imported += 1
        action = "UPDATE" if existing_path else "CREATE"
        print(f"{action} {path.relative_to(ROOT)} <- {card_url}")

    print(f"Imported {imported} agent(s), skipped {skipped}, source={source_endpoint}")
    return 0 if imported else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Import live agents from external A2A registries.")
    parser.add_argument(
        "--endpoint",
        action="append",
        help="Registry endpoint to try. Can be passed multiple times.",
    )
    parser.add_argument("--limit", type=int, default=10, help="Maximum agents to import")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    return import_agents(args)


if __name__ == "__main__":
    raise SystemExit(main())
