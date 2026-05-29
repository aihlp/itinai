# ITINAI Agent Directory

[![Validate Agent Manifests](https://github.com/aihlp/itinai/actions/workflows/validate.yml/badge.svg)](https://github.com/aihlp/itinai/actions/workflows/validate.yml)
[![Health Check Agents](https://github.com/aihlp/itinai/actions/workflows/health-check.yml/badge.svg)](https://github.com/aihlp/itinai/actions/workflows/health-check.yml)

`itinai` is a registry-as-code directory for AI agents. The repository is the
single source of truth for static agent manifests stored in `agents/*.yaml`.

Dynamic data, pricing, availability, catalogues, and negotiation state stay with
the agent owner and are linked from the manifest.

## Repository Layout

```text
agents/                         Agent manifests
schemas/agent-manifest.schema.json  JSON Schema for manifests
.github/workflows/validate.yml   Pull request validation
.github/workflows/health-check.yml  Scheduled availability checks
scripts/validate.py              Local manifest validation
scripts/health-check.py          Agent availability checks
docs/agent-card-spec.md          Agent Card requirements
```

## Add an Agent

1. Create `agents/<agent-id>.yaml`.
2. Use a kebab-case `agent_id` that matches the filename.
3. Set `a2a_config.agent_card_url` to a public HTTPS Agent Card URL.
4. Add at least one skill with `id`, `name`, and `tags`.
5. Add `contact.email`.
6. Open a pull request.

Example:

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

## Local Validation

Install the validation dependencies:

```bash
python -m pip install -r requirements.txt
```

Validate all manifests:

```bash
python scripts/validate.py
```

Run health checks:

```bash
python scripts/health-check.py --output health-results.json
```

Import live seed agents from the A2A Registry:

```bash
python scripts/import-from-registry.py --limit 10
```

External registry synchronization also runs in GitHub Actions via
`Sync External Agents`. That workflow can be started manually or by schedule; it
imports live agents, validates manifests, runs health checks, uploads
`sync-health-results`, and opens or updates a pull request when manifests change.
When the `WP_KEY` GitHub secret is configured, the workflow also syncs healthy
manifests to the WordPress Agents app at `itinai.com`.
`Sync WordPress Agents` runs on pushes to `main` that change `agents/*.yaml` and
uses `WP_USER`, `WP_KEY`, `WP_APP`, and `WP_SYNC_ENDPOINT` GitHub secrets to
publish changed manifests to the WordPress REST endpoint. `WP_USER` is the
WordPress username, `WP_KEY` is the Application Password, and `WP_APP` is the
Application Password label/name.

Scheduled health checks upload `health-results.json` as a GitHub Actions
artifact. On scheduled runs, the workflow also tracks consecutive failures per
agent and opens a `health-check` issue after three failed checks in a row.

## Protocols

- A2A v1.0 is used for agent discovery and task handoff.
- ANP may be used for deterministic commercial negotiation.
- JSON-LD feeds may expose live catalogues and services.

The registry does not proxy communication between agents.
