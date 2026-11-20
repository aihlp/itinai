#!/usr/bin/env python3
"""
Publish our own BotCore hubs (hubs.yaml) and their agents to outside channels, then read each back.

Input: the manifests the sync workflow wrote for each hub (source.type == "botcore-hub").
Channels:
  a2aregistry  one entry per agent card + the hub card; at most --per-run new registrations per run
               (a2aregistry has no self-service delete, so it is fed slowly)
  huggingface  one static Space per hub: README listing every agent (needs HF_TOKEN)
  mcpregistry  one server per ready vertical MCP endpoint (io.github.aihlp/<hub>-<vertical>) + the hub;
               writes server-*.json for the workflow's `mcp-publisher publish` step (GitHub OIDC, no DNS)
  hub repo     site/<hub>/: README + one page per vertical; the workflow pushes it to aihlp/<hub>
Gate: only verticals that pass phase 1 as an outside visitor sees it (approved catalog items and a skill
beyond the standard BotCore ones) are published anywhere -- listings are hard to roll back.
State and read-back: status/<domain>.json (committed by the workflow).
Without --live nothing is sent: every listing is validated (a2aregistry preview) and printed.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
A2A = "https://a2aregistry.org/api"
HF = "https://huggingface.co/api"
MCP = "https://registry.modelcontextprotocol.io/v0.1/servers"
NOW = datetime.now(timezone.utc).isoformat(timespec="seconds")


def hub_id(domain: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", domain.split(".")[0].lower())


STANDARD_SKILLS = {"find", "order", "order-status", "order_status", "place-order", "negotiate", "read-cv"}


def vertical_of(m: dict) -> str:
    return re.search(r"/verticals/([^/]+)/", m["a2a_config"]["agent_card_url"]).group(1)


def gate(domain: str, manifests: list[dict], state: dict) -> list[dict]:
    result = {}
    for slug in sorted({vertical_of(m) for m in manifests}):
        r = requests.get(f"https://api.{domain}/api/public/verticals/{slug}/catalog", timeout=30)
        items = len((r.json() if r.ok else {}).get("items") or [])
        own = sorted({k["id"] for m in manifests if vertical_of(m) == slug for k in m.get("skills", [])} - STANDARD_SKILLS)
        result[slug] = {"items": items, "own_skills": len(own), "ready": items > 0 and bool(own)}
        print(f"gate {slug}: items={items} own_skills={len(own)} ready={result[slug]['ready']}")
    state["gate"] = result
    return [m for m in manifests if result[vertical_of(m)]["ready"]]


def hub_manifests(domain: str) -> list[dict]:
    out = []
    for path in sorted((ROOT / "agents").glob("*.yaml")):
        m = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        src = m.get("source") or {}
        if src.get("type") == "botcore-hub" and domain in str(src.get("name", "")):
            out.append(m)
    return out


def a2a_find(card_url: str) -> str | None:
    r = requests.get(f"{A2A}/agents", params={"search": card_url.rstrip("/").split("/")[-2]}, timeout=30)
    for a in (r.json().get("agents") or []) if r.ok else []:
        if a.get("wellKnownURI") == card_url:
            return str(a.get("id") or a.get("agent_id"))
    return None


def publish_a2aregistry(domain: str, manifests: list[dict], state: dict, live: bool, per_run: int) -> None:
    cards = ([f"https://{domain}/.well-known/agent-card.json"] if manifests else []) + [m["a2a_config"]["agent_card_url"] for m in manifests]
    done = state.setdefault("a2aregistry", {})
    sent = 0
    for url in cards:
        if done.get(url, {}).get("id"):
            continue
        found = a2a_find(url)
        if found:
            done[url] = {"id": found, "read_back": NOW}
            continue
        if sent >= per_run:
            break
        sent += 1
        if not live:
            p = requests.post(f"{A2A}/agents/preview", json={"wellKnownURI": url}, timeout=60)
            ev = (p.json().get("evidence") or {}) if p.ok else {}
            print(f"DRY a2aregistry {url}: preview HTTP {p.status_code} conformant={ev.get('conformant')} errors={ev.get('errors')}")
            continue
        r = requests.post(f"{A2A}/agents/register", json={"wellKnownURI": url}, timeout=60)
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {"text": r.text[:300]}
        agent = body.get("agent") or body
        done[url] = {"id": agent.get("id") or agent.get("agent_id"), "registered": NOW, "http": r.status_code,
                     "error": None if r.ok else str(body)[:300]}
        print(f"LIVE a2aregistry {url}: HTTP {r.status_code}")
    listed = sum(1 for u in cards if done.get(u, {}).get("id"))
    print(f"a2aregistry {domain}: {listed}/{len(cards)} listed")


def readme(domain: str, manifests: list[dict]) -> str:
    lines = [f"# {domain} — agents you can call", "",
             f"Every company here is represented by its own A2A agent. Call any agent over A2A or MCP; "
             f"register once at https://api.{domain}/oauth/register.", "",
             f"- Hub: https://{domain}/ · agent card https://{domain}/.well-known/agent-card.json · "
             f"MCP https://api.{domain}/@/mcp · https://{domain}/llms.txt", "", "## Agents", ""]
    for m in manifests:
        tags = ", ".join(sorted({t for s in m.get("skills", []) for t in s.get("tags", [])})[:6])
        lines.append(f"- **{m['name']}** — {m.get('description', '')} ({tags}) · [agent card]({m['a2a_config']['agent_card_url']})")
    return "\n".join(lines) + "\n"


def write_hub_repo(domain: str, manifests: list[dict], state: dict) -> None:
    out = ROOT / "site" / hub_id(domain)
    (out / "verticals").mkdir(parents=True, exist_ok=True)
    (out / "README.md").write_text(readme(domain, manifests), encoding="utf-8")
    for slug in sorted({vertical_of(m) for m in manifests}):
        part = [m for m in manifests if vertical_of(m) == slug]
        page = [f"# {slug} on {domain}", "", f"MCP: https://api.{domain}/{slug}/mcp · https://{domain}/{slug}", ""]
        for m in part:
            page += [f"## {m['name']}", "", m.get("description", ""), "",
                     *[f"- {k['name']}" for k in m.get("skills", [])], "", f"[agent card]({m['a2a_config']['agent_card_url']})", ""]
        (out / "verticals" / f"{slug}.md").write_text("\n".join(page), encoding="utf-8")
    state["hub_repo"] = {"repo": f"aihlp/{hub_id(domain)}", "agents": len(manifests), "built": NOW}
    print(f"hub repo aihlp/{hub_id(domain)}: {len(manifests)} agents")


def publish_huggingface(domain: str, manifests: list[dict], state: dict, live: bool) -> None:
    space = f"{hub_id(domain)}-agents"
    text = f"---\ntitle: {domain} agents\nsdk: static\ntags: [a2a, mcp-server, agent-card, ai-agents]\n---\n\n" + readme(domain, manifests)
    token = os.environ.get("HF_TOKEN")
    if not manifests:
        print(f"huggingface {space}: nothing ready, skipped")
        return
    if not live or not token:
        print(f"DRY huggingface space {space}: README {len(text)} chars, {len(manifests)} agents" + ("" if token else " (no HF_TOKEN)"))
        return
    h = {"authorization": f"Bearer {token}"}
    owner = requests.get(f"{HF}/whoami-v2", headers=h, timeout=30).json()["name"]
    requests.post(f"{HF}/repos/create", headers=h, json={"type": "space", "name": space, "sdk": "static", "private": False}, timeout=60)
    nd = "\n".join(json.dumps(x) for x in [
        {"key": "header", "value": {"summary": f"Agents of {domain} ({len(manifests)})"}},
        {"key": "file", "value": {"path": "README.md", "content": base64.b64encode(text.encode()).decode(), "encoding": "base64"}},
        {"key": "file", "value": {"path": "index.html", "content": base64.b64encode(f'<meta http-equiv="refresh" content="0;url=https://{domain}/">'.encode()).decode(), "encoding": "base64"}},
    ])
    r = requests.post(f"{HF}/spaces/{owner}/{space}/commit/main", headers={**h, "content-type": "application/x-ndjson"}, data=nd, timeout=60)
    print(f"LIVE huggingface {owner}/{space}: HTTP {r.status_code}")
    state["huggingface"] = {"space": f"{owner}/{space}", "updated": NOW, "http": r.status_code}


def short(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1].rsplit(" ", 1)[0].rstrip(",.;:") + "…"


def prepare_mcpregistry(domain: str, manifests: list[dict], state: dict) -> None:
    card = requests.get(f"https://{domain}/.well-known/agent-card.json", timeout=30).json()
    targets = [("@", card.get("description") or domain)] if manifests else []
    targets += [(slug, f"{slug} on {domain}: " + ", ".join(m["name"] for m in manifests if vertical_of(m) == slug))
                for slug in sorted({vertical_of(m) for m in manifests})]
    listed = state["mcpregistry"] = {}
    for slug, desc in targets:
        name = f"io.github.aihlp/{hub_id(domain)}" + ("" if slug == "@" else f"-{slug}")
        server = {
            "$schema": "https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json",
            "name": name, "description": short(desc, 100), "version": card.get("version") or "1.0.0",
            "websiteUrl": f"https://{domain}/" + ("" if slug == "@" else slug),
            "remotes": [{"type": "streamable-http", "url": f"https://api.{domain}/{slug}/mcp"}],
        }
        (ROOT / f"server-{name.split('/')[1]}.json").write_text(json.dumps(server, indent=2), encoding="utf-8")
        r = requests.get(MCP, params={"search": name}, timeout=30)
        listed[name] = bool(r.ok and any(x.get("server", x).get("name") == name for x in r.json().get("servers") or []))
        print(f"mcpregistry {name}: listed={listed[name]}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--per-run", type=int, default=5, help="new a2aregistry registrations per run")
    args = ap.parse_args()
    hubs = (yaml.safe_load((ROOT / "hubs.yaml").read_text(encoding="utf-8")) or {}).get("hubs") or []
    (ROOT / "status").mkdir(exist_ok=True)
    for hub in hubs:
        domain = hub["domain"]
        path = ROOT / "status" / f"{domain}.json"
        state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        manifests = hub_manifests(domain)
        print(f"== {domain}: {len(manifests)} agents in agents/")
        manifests = gate(domain, manifests, state)
        print(f"== {domain}: {len(manifests)} agents in ready verticals")
        write_hub_repo(domain, manifests, state)
        publish_a2aregistry(domain, manifests, state, args.live, args.per_run)
        publish_huggingface(domain, manifests, state, args.live)
        prepare_mcpregistry(domain, manifests, state)
        state.update({"domain": domain, "ready_agents": len(manifests), "checked": NOW})
        path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
