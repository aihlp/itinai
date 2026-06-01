# ITINAI Agent Directory

[![Validate Agent Manifests](https://github.com/aihlp/itinai/actions/workflows/validate.yml/badge.svg)](https://github.com/aihlp/itinai/actions/workflows/validate.yml)
[![Health Check Agents](https://github.com/aihlp/itinai/actions/workflows/health-check.yml/badge.svg)](https://github.com/aihlp/itinai/actions/workflows/health-check.yml)

**itinai** is a registry-as-code directory for AI agents. This repository serves as the single source of truth for static agent manifests stored in `agents/*.yaml`.

## Overview

The ITINAI Agent Directory enables decentralized AI agent discovery and interoperability using the [A2A (Agent-to-Agent) Protocol](https://a2aprotocol.dev/). Rather than hosting dynamic data, the registry stores lightweight manifests that point to agent-owned endpoints where live data, pricing, availability, and negotiation state reside.

### Key Principles

- **Registry-as-Code**: All agent manifests are version-controlled YAML files
- **Decentralized Data**: Dynamic data stays with the agent owner
- **Open Standards**: Built on A2A protocol for agent discovery and task handoff
- **Automated Validation**: CI/CD pipelines validate manifests and check agent health
- **Multi-Source Import**: Aggregates agents from multiple external registries and marketplaces

## Repository Layout

```
itinai/
├── agents/                          # Agent manifest YAML files
│   ├── agent-svg-registry.yaml
│   ├── anp2-network-relay.yaml
│   └── ...
├── schemas/
│   └── agent-manifest.schema.json   # JSON Schema for manifest validation
├── scripts/
│   ├── validate.py                  # Local manifest validation script
│   ├── health-check.py              # Agent availability checker
│   ├── import-from-registry.py      # External registry importer
│   └── sync-wordpress.py            # WordPress synchronization
├── docs/
│   └── agent-card-spec.md           # Agent Card specification
├── .github/workflows/
│   ├── validate.yml                 # PR validation workflow
│   ├── health-check.yml             # Scheduled health checks
│   ├── sync-external.yml            # External registry sync
│   └── sync-wordpress.yml           # WordPress sync workflow
├── requirements.txt                 # Python dependencies
├── README.md                        # This file
├── CONTRIBUTING.md                  # Contribution guidelines
└── LICENSE                          # MIT License
```

## Quick Start

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)

### Installation

```bash
# Clone the repository
git clone https://github.com/aihlp/itinai.git
cd itinai

# Install dependencies
python -m pip install -r requirements.txt
```

### Validate Manifests

```bash
# Validate all agent manifests
python scripts/validate.py

# Validate specific manifests
python scripts/validate.py agents/my-agent.yaml
```

### Run Health Checks

```bash
# Check all registered agents
python scripts/health-check.py --output health-results.json

# Check only Agent Card URLs
python scripts/health-check.py --agent-card-only

# Custom timeout (in seconds)
python scripts/health-check.py --timeout 15
```

## Adding an Agent

### Step-by-Step Guide

1. **Create a new manifest file** in the `agents/` directory:
   ```bash
   touch agents/<your-agent-id>.yaml
   ```

2. **Follow naming conventions**:
   - Use kebab-case for `agent_id` (e.g., `my-smart-agent-v1`)
   - Filename must match `agent_id` (e.g., `my-smart-agent-v1.yaml`)

3. **Required fields**:
   - `agent_id`: Unique identifier (kebab-case string)
   - `name`: Human-readable agent name (1-120 characters)
   - `a2a_config.agent_card_url`: HTTPS URL to your Agent Card
   - `a2a_config.protocol_version`: A2A protocol version (e.g., "1.0.0")
   - `skills`: At least one skill with `id`, `name`, and `tags`
   - `contact.email`: Owner contact email

4. **Optional but recommended**:
   - `description`: Agent description (max 1000 characters)
   - `version`: Semantic version (e.g., "1.0.0")
   - `health_check.url`: Custom health check endpoint
   - `contact.url`: Agent website or documentation
   - `dynamic_data`: Catalogue feeds and negotiation endpoints

### Example Manifest

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
  - id: "check-inventory"
    name: "Check Inventory Levels"
    tags: ["inventory", "real-time", "api"]

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

5. **Validate locally** before submitting:
   ```bash
   python scripts/validate.py agents/retinol-supplier-v1.yaml
   ```

6. **Submit a Pull Request** to add your agent to the registry.

## Agent Card Specification

An Agent Card is a public JSON document that describes an agent endpoint for A2A discovery and task handoff.

### Requirements

- Must be served over **HTTPS**
- Must return **HTTP 200** during validation
- Must be valid **JSON**
- Should include:
  - Agent identity and metadata
  - Supported A2A protocol version
  - Public endpoints and capabilities
  - Owner contact/support information

### Standard Location

```
https://<your-domain>/.well-known/agent-card.json
```

For detailed specifications, see [docs/agent-card-spec.md](docs/agent-card-spec.md).

## Protocols

### A2A (Agent-to-Agent) Protocol v1.0

Used for agent discovery and task handoff. All registered agents must expose an A2A-compatible Agent Card.

### ANP (Autonomous Negotiation Protocol)

Optional protocol for deterministic commercial negotiation between agents.

### JSON-LD Feeds

Agents may expose live catalogues and services using JSON-LD formatted feeds.

> **Note**: The registry does not proxy communication between agents. All runtime interactions occur directly between agent endpoints.

## External Registry Integration

### Supported Sources

The importer can aggregate agents from these sources:

| Source | Type | Status |
|--------|------|--------|
| A2A Registry | external-registry | ✅ Active |
| Agora Registry | github-registry | ✅ Active |
| OpenClaw Managed Agents | github-registry | ✅ Active |
| LangChain Hub | hub | ✅ Active |
| CrewAI Marketplace | marketplace | ✅ Active |
| AutoGen Studio Gallery | github-gallery | ✅ Active |
| AI Agent Index | github-registry | ✅ Active |
| Venice AI Agent Marketplace | marketplace | ✅ Active |

### Import Commands

```bash
# Import from all configured sources (limit 10 per source)
python scripts/import-from-registry.py --limit 10

# Import from a specific source
python scripts/import-from-registry.py --source agora-registry

# Dry run (preview without writing)
python scripts/import-from-registry.py --source agora-registry --dry-run

# Use custom registry endpoint
python scripts/import-from-registry.py --endpoint https://my-registry.com/api/agents
```

### Automated Synchronization

External registry sync runs via GitHub Actions:
- **Manual trigger**: Can be started on-demand
- **Scheduled runs**: Periodic synchronization
- **Automatic PR creation**: Opens/updates PR when manifests change
- **Health check integration**: Validates imported agents
- **WordPress sync**: Optionally publishes to itinai.com (requires secrets)

## GitHub Actions Workflows

| Workflow | Trigger | Description |
|----------|---------|-------------|
| `validate.yml` | PR, push | Validates all agent manifests against schema |
| `health-check.yml` | Schedule, manual | Checks agent endpoint availability |
| `sync-external.yml` | Schedule, manual | Imports agents from external registries |
| `sync-wordpress.yml` | Push to main, manual | Syncs manifests to WordPress site |

### Health Check Behavior

- Results uploaded as GitHub Actions artifacts (`health-results.json`)
- Tracks consecutive failures per agent
- Automatically opens `health-check` issue after 3 consecutive failures
- Exit code 1 if any agents are unhealthy (unless `--allow-unhealthy` flag used)

## Manifest Schema

All manifests must conform to the JSON Schema defined in `schemas/agent-manifest.schema.json`.

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `agent_id` | string | Unique identifier (kebab-case pattern) |
| `name` | string | Display name (1-120 chars) |
| `a2a_config` | object | A2A configuration |
| `a2a_config.agent_card_url` | string | HTTPS URL to Agent Card |
| `a2a_config.protocol_version` | string | A2A protocol version |
| `skills` | array | List of agent skills (min 1) |
| `skills[].id` | string | Skill identifier |
| `skills[].name` | string | Skill display name |
| `skills[].tags` | array | Skill tags (min 1) |
| `contact` | object | Contact information |
| `contact.email` | string | Contact email address |

### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `description` | string | Agent description (max 1000 chars) |
| `version` | string | Semantic version |
| `dynamic_data` | object | Live data endpoints |
| `health_check` | object | Health check configuration |
| `contact.url` | string | Contact website URL |
| `openclaw` | object | OpenClaw-specific metadata |
| `source` | object | External source metadata |

For complete schema details, see [schemas/agent-manifest.schema.json](schemas/agent-manifest.schema.json).

## Scripts Reference

### validate.py

Validates agent manifests against the JSON Schema.

```bash
# Validate all manifests
python scripts/validate.py

# Validate specific files
python scripts/validate.py agents/agent1.yaml agents/agent2.yaml

# Exit codes
# 0: All manifests valid
# 1: Validation errors found
```

### health-check.py

Checks agent endpoint availability.

```bash
# Basic usage
python scripts/health-check.py --output results.json

# Options
--output FILE          Output file path (default: health-results.json)
--timeout SECONDS      Request timeout (default: 10)
--agent-card-only      Check only a2a_config.agent_card_url
--paths-file FILE      Read manifest paths from file
--allow-unhealthy      Exit 0 even if agents are unhealthy
```

### import-from-registry.py

Imports agents from external registries.

```bash
# Import with limits
python scripts/import-from-registry.py --limit 10

# Filter by source
python scripts/import-from-registry.py --source agora-registry

# Preview changes
python scripts/import-from-registry.py --dry-run

# Custom endpoint
python scripts/import-from-registry.py --endpoint https://my-api.com/agents

# Options
--limit N              Max agents per source (default: no limit)
--source NAME          Filter by source name (slugified)
--endpoint URL         Custom registry endpoint
--timeout SECONDS      Request timeout (default: 15)
--dry-run              Preview without writing files
```

## Contributing

We welcome contributions! Please read our [Contributing Guidelines](CONTRIBUTING.md) for details on:

- Code of Conduct
- How to submit agents
- Reporting issues
- Development workflow
- Pull request process

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- **Documentation**: See `/docs` directory
- **Issues**: Report bugs or request features via GitHub Issues
- **Discussions**: Join conversations in GitHub Discussions
- **Contact**: Reach out to the maintainers through GitHub

## Roadmap

- [ ] Signed Agent Cards support
- [ ] Enhanced search and filtering
- [ ] Agent rating and reputation system
- [ ] Multi-language manifest support
- [ ] GraphQL API for registry queries
- [ ] Webhook notifications for agent updates

---

**Built with ❤️ for the AI Agent ecosystem**
