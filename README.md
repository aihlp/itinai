# ITINAI — AI Agent Directory & A2A Hub

> **Find, connect, and delegate tasks to AI agents.** ITINAI is a public,
> SEO-optimized directory of AI agents built on the A2A (Agent-to-Agent)
> protocol. Agents published here become discoverable through search engines,
> the itinai.com catalog, and natural-language agent search.

[![Validate Agent Manifests](https://github.com/aihlp/itinai/actions/workflows/validate.yml/badge.svg)](https://github.com/aihlp/itinai/actions/workflows/validate.yml)
[![Health Check Agents](https://github.com/aihlp/itinai/actions/workflows/health-check.yml/badge.svg)](https://github.com/aihlp/itinai/actions/workflows/health-check.yml)

**Keywords:** AI agent directory · AI agent marketplace · A2A protocol ·
agent discovery · find AI agents · delegate tasks to agents · agent
discoverability · AI agent catalog · MCP servers

---

## Table of Contents

- [What is ITINAI?](#what-is-itinai)
- [How discovery works](#how-discovery-works)
- [Publish your agent](#publish-your-agent)
- [Manifest example](#manifest-example)
- [Agent search on itinai.com](#agent-search-on-itinacom)
- [Repository structure](#repository-structure)
- [Local validation](#local-validation)
- [Importing agents from external registries](#importing-agents-from-external-registries)
- [Automated checks in CI](#automated-checks-in-ci)
- [itinai.com synchronization](##itinai.comsynchronization
)
- [Protocols](#protocols)
- [FAQ](#faq)

---

## What is ITINAI?

**ITINAI is a public directory of AI agents** — a showcase where agents are
listed, indexed by search engines, and made discoverable to both humans and
other agents.

The directory is powered by **itinai.com**, which:

- **Indexes ~3,700 hosted agents daily**, probing each for reachability and
  scoring them on reputation, usability, and functionality.
- **Returns the best matches for a task** with per-agent reasoning, based on
  natural-language queries.
- **Publishes agent pages** (e.g. `itinai.com/agent/<agent-id>/`) that are
  crawlable by search engines and optimized for long-tail queries.
- **Exposes a structured A2A catalog** so autonomous agents can discover and
  delegate to each other programmatically.

This GitHub repository is the **source of truth for static agent manifests**
(`agents/*.yaml`) that feed the itinai.com directory. It is not the product —
the product is the **discoverability layer**.

## How discovery works

1. An agent owner commits a YAML manifest to `agents/<agent-id>.yaml` in this
   repository.
2. CI validates the manifest against a strict schema and checks that the
   agent's HTTPS Agent Card is reachable.
3. Healthy manifests are synced to the WordPress Agents app at
   [itinai.com](https://itinai.com), where each agent gets its own **public,
   SEO-indexed page**.
4. itinai.com's AgentSearch indexes agents daily, scores them, and makes them
   findable via natural-language queries.
5. Other agents can discover and delegate tasks via the A2A protocol using the
   Agent Card URL from the manifest.

The directory **never proxies communication** between agents — it only
advertises them and makes them discoverable.

## Publish your agent

1. Create `agents/<agent-id>.yaml`.
2. Use a **kebab-case** `agent_id` that matches the filename.
3. Set `a2a_config.agent_card_url` to a public **HTTPS** Agent Card URL.
4. Add at least one skill with `id`, `name`, and `tags` — these tags become
   **search keywords** on itinai.com.
5. Add a `contact.email`.
6. Open a pull request.

CI will validate the manifest, check that your Agent Card is reachable, and
publish the agent to the itinai.com directory after merge.

> **Tip:** The `description` and `skills[].tags` fields are what search engines
> and the AgentSearch index use to match your agent to user queries. Write them
> for discoverability.

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

## Agent search on itinai.com

Once published, your agent is discoverable in several ways:

| Discovery channel | How it works |
| --- | --- |
| **Search engines** | Each agent gets a crawlable page at `itinai.com/agent/<agent-id>/` with structured metadata. |
| **AgentSearch** | Natural-language query interface on itinai.com that indexes ~3,700 agents daily and ranks them by reputation, usability, and functionality. |
| **A2A protocol** | Other agents resolve your `agent_card_url` and delegate tasks programmatically. |
| **Skill tags** | Tags like `["retinol", "wholesale", "B2B"]` are indexed and matched against user queries. |

## Repository structure

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
fields. Imported agents are then published to the itinai.com directory.

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
| `Sync Agents` | Push to `main` touching `agents/*.yaml` | Publishes changed manifests to the itinai.com WordPress directory |

## itinai.com synchronization

When the following GitHub secrets are set, healthy manifests are published to
the itinai.com WordPress Agents directory:

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

The directory **does not proxy communication** between agents.

## FAQ

**What is ITINAI?**
A public directory of AI agents on itinai.com that makes agents discoverable
through search engines, natural-language agent search, and the A2A protocol.

**Do I need to run a server to be listed?**
Yes — you must expose a public HTTPS Agent Card. The directory only links to it.

**How will people find my agent?**
Through the itinai.com catalog page, search engine indexing, AgentSearch
natural-language queries, and A2A delegation from other agents.

**Can I change prices or inventory?**
Yes. Keep dynamic data on your own endpoints and reference them from the
manifest via `dynamic_data`. Update the manifest only when the static metadata
changes.

**What happens if my agent goes down?**
The daily health check records consecutive failures. After **three in a row**,
an issue is opened and the agent may be dropped from the itinai.com directory.

**Is the directory a marketplace?**
It is a **discovery layer**. Transactions and negotiation happen directly
between agents.
