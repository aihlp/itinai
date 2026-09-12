# ITINAI A2A Agent Hub

> **A registry-as-code directory for AI agents.** One Git repository — the single
> source of truth for static AI agent manifests, A2A Agent Cards, and agent
> discovery metadata. Built for the A2A (Agent-to-Agent) protocol ecosystem.

[![Validate Agent Manifests](https://github.com/aihlp/itinai/actions/workflows/validate.yml/badge.svg)](https://github.com/aihlp/itinai/actions/workflows/validate.yml)
[![Health Check Agents](https://github.com/aihlp/itinai/actions/workflows/health-check.yml/badge.svg)](https://github.com/aihlp/itinai/actions/workflows/health-check.yml)

**Keywords:** AI agent registry · A2A protocol · agent manifest · agent
directory · agent discovery · AI marketplace · JSON-LD catalogue · ANP
negotiation

---

## Table of Contents

- [What is ITINAI?](#what-is-itinai)
- [How it works](#how-it-works)
- [Repository layout](#repository-layout)
- [Add your agent](#add-your-agent)
- [Manifest example](#manifest-example)
- [Local validation](#local-validation)
- [Importing agents from external registries](#importing-agents-from-external-registries)
- [Automated checks in CI](#automated-checks-in-ci)
- [WordPress synchronization](#wordpress-synchronization)
- [Protocols](#protocols)
- [FAQ](#faq)

---

## What is ITINAI?

`itinai` is a **registry-as-code** directory for AI agents. Instead of storing
dynamic state (pricing, availability, negotiation), the repository holds only
**static manifests** for each agent in `agents/*.yaml`.

Dynamic data — prices, catalogues, availability, and negotiation state — stays
with the agent owner and is linked from the manifest via URLs. This keeps the
registry small, cacheable, and auditable while agents remain fully autonomous.

## How it works

1. Each agent owner commits a YAML manifest to `agents/<agent-id>.yaml`.
2. Every pull request is validated against a strict JSON Schema and an HTTPS
   Agent Card reachability check.
3. A daily scheduled workflow pings every agent, tracks consecutive failures,
   and opens an issue after **three failed checks in a row**.
4. Healthy manifests are synced to the WordPress Agents app at
   [itinai.com](https://itinai.com).
5. New live agents are pulled in automatically from external registries
   (see [Importing agents](#importing-agents-from-external-registries)).

The registry **never proxies communication** between agents — it only
advertises them.

## Repository layout

```text
agents/                              Agent manifests (YAML)
schemas/agent-manifest.schema.json   JSON Schema for manifests
.github/workflows/validate.yml       Pull request validation
.github/workflows/health-check.yml   Scheduled availability checks
scripts/validate.py                  Local manifest validation
scripts/health-check.py              Agent availability checks
scripts/import-from-registry.py      External registry importer
docs/agent-card-spec.md              Agent Card requirements
```

## Add your agent

1. Create `agents/<agent-id>.yaml`.
2. Use a **kebab-case** `agent_id` that matches the filename.
3. Set `a2a_config.agent_card_url` to a public **HTTPS** Agent Card URL.
4. Add at least one skill with `id`, `name`, and `tags`.
5. Add a `contact.email`.
6. Open a pull request.

CI will validate the manifest, check that your Agent Card is reachable, and
report the result directly on the PR.

## Manifest example

```yaml
agent_id: "retinol-supplier-v1"
name: "Retinol Wholesale Agent"
description: "B2B supplier of retinol and cosmetic ingredients"
version: "1.0.0"
a2a_config:
  agent_card_url: "https://api.retinol-supplier.com/.well-known/agent-card.json"
  protocol_version: "1.0.0"
skills:
  - id: "supply-retinol"
    name: "Supply Retinol"
    tags: ["retinol", "wholesale", "cosmetics", "B2B"]
dynamic_data:
  catalogue_feed_url: "https://api.retinol-supplier.com/catalogue.jsonld"
  negotiation_protocol: "ANP"
  negotiation_endpoint: "https://api.retinol-supplier.com/anp"
health_check:
  url: "https://api.retinol-supplier.com/.well-known/agent-card.json"
contact:
  email: "sales@retinol-supplier.com"
  url: "https://retinol-supplier.com"
```

## Local validation

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Validate every manifest against the JSON Schema:

```bash
python scripts/validate.py
```

Run reachability health checks:

```bash
python scripts/health-check.py --output health-results.json
```

## Importing agents from external registries

The importer scans external AI agent registries and writes manifests **only**
for agents whose HTTPS Agent Card is reachable and contains the required A2A
fields. It supports `--dry-run` and `--source <source-slug>` for testing.

```bash
python scripts/import-from-registry.py --limit 10
python scripts/import-from-registry.py --source agora-registry --dry-run
```

Supported sources:

- **A2A Registry**
- **Agora Registry** (`agora-protocol/agora`)
- **OpenClaw Managed Agents**
- **LangChain Hub**
- **CrewAI Marketplace**
- **AutoGen Studio Gallery** (`microsoft/autogen`)
- **AI Agent Index** (`AI-Engineer-Foundation/agent-index`)
- **Venice AI Agent Marketplace**

`--limit` is applied **per source** so one large registry cannot starve smaller
sources during scheduled synchronization.

## Automated checks in CI

| Workflow | Trigger | What it does |
| --- | --- | --- |
| `Validate Agent Manifests` | Pull request, manual | Schema validation + Agent Card reachability for changed manifests |
| `Health Check Agents` | Daily schedule, manual | Pings every agent, uploads `health-results.json`, tracks consecutive failures, opens a `health-check` issue after 3 failures |
| `Sync External Agents` | Schedule, manual | Imports live agents, validates, runs health checks, uploads `sync-health-results`, opens/updates a PR |
| `Sync WordPress Agents` | Push to `main` touching `agents/*.yaml` | Publishes changed manifests to the WordPress REST endpoint |

## WordPress synchronization

When the following GitHub secrets are set, healthy manifests are published to
the WordPress Agents app at `itinai.com`:

| Secret | Description |
| --- | --- |
| `WP_USER` | WordPress username |
| `WP_KEY` | WordPress Application Password |
| `WP_APP` | Application Password label/name |
| `WP_SYNC_ENDPOINT` | WordPress REST endpoint that receives the manifests |

## Protocols

- **A2A v1.0** — agent discovery and task handoff.
- **ANP** — deterministic commercial negotiation (optional).
- **JSON-LD** — live catalogue and service feeds (optional).

The registry **does not proxy communication** between agents.

## FAQ

**Do I need to run a server to be listed?**
Yes — you must expose a public HTTPS Agent Card. The registry only links to it.

**Can I change prices or inventory?**
Yes. Keep dynamic data on your own endpoints and reference them from the
manifest via `dynamic_data`. Update the manifest only when the static metadata
changes.

**What happens if my agent goes down?**
The daily health check records consecutive failures. After **three in a row**,
an issue is opened and the manifest may be dropped from the WordPress sync.

**Can I import agents from another registry?**
Yes — see [Importing agents](#importing-agents-from-external-registries) or open
a PR with a new source adapter.

**Is the registry a marketplace?**
No. It is a discovery and validation layer. Transactions and negotiation happen
directly between agents.
