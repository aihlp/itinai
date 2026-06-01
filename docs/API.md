# API Documentation

This document provides detailed information about the scripts and tools available in the ITINAI Agent Directory.

## Table of Contents

- [validate.py](#validatepy)
- [health-check.py](#health-checkpy)
- [import-from-registry.py](#import-from-registrypy)
- [sync-wordpress.py](#sync-wordpresspy)

---

## validate.py

**Purpose**: Validates agent manifest YAML files against the JSON Schema.

### Location
```
scripts/validate.py
```

### Dependencies
- `pyyaml` - YAML parsing
- `jsonschema` - JSON Schema validation

### Usage

```bash
# Validate all manifests in agents/ directory
python scripts/validate.py

# Validate specific manifest files
python scripts/validate.py agents/my-agent.yaml

# Validate multiple specific files
python scripts/validate.py agents/agent1.yaml agents/agent2.yaml
```

### Arguments

| Argument | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `paths` | list | No | `[]` | Optional paths to specific manifest files |

### Exit Codes

| Code | Meaning |
|------|---------|
| `0` | All manifests are valid |
| `1` | One or more manifests have validation errors |

### Output

**Success:**
```
Validated 42 manifest(s).
```

**Error:**
```
agents/bad-agent.yaml: skills: [{'id': 'test', 'name': 'Test'}] is too short
agents/bad-agent.yaml: contact.email: 'invalid-email' is not a 'email'
```

### Validation Rules

The script validates against `schemas/agent-manifest.schema.json`:

1. **Required Fields**: `agent_id`, `name`, `a2a_config`, `skills`, `contact`
2. **Field Patterns**: 
   - `agent_id` must be kebab-case (lowercase alphanumeric with hyphens)
   - `version` must follow semantic versioning
   - URLs must use HTTPS
3. **Constraints**:
   - `name` max length: 120 characters
   - `description` max length: 1000 characters
   - `skills` array minimum items: 1
   - Each skill must have `id`, `name`, and at least one `tag`
4. **Filename Match**: The filename must match `{agent_id}.yaml`

### Example Implementation

```python
from pathlib import Path
import yaml
from jsonschema import Draft202012Validator, FormatChecker

SCHEMA_PATH = Path("schemas/agent-manifest.schema.json")
AGENTS_DIR = Path("agents")

def validate_manifest(manifest_path: Path) -> list[str]:
    schema = json.loads(SCHEMA_PATH.read_text())
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    
    with manifest_path.open() as f:
        manifest = yaml.safe_load(f)
    
    errors = []
    for error in validator.iter_errors(manifest):
        field = ".".join(str(part) for part in error.absolute_path) or "<root>"
        errors.append(f"{manifest_path}: {field}: {error.message}")
    
    return errors
```

---

## health-check.py

**Purpose**: Checks the availability and health of registered agent endpoints.

### Location
```
scripts/health-check.py
```

### Dependencies
- `pyyaml` - YAML parsing
- `requests` - HTTP requests

### Usage

```bash
# Basic health check
python scripts/health-check.py

# Specify output file
python scripts/health-check.py --output results.json

# Check only Agent Card URLs (ignore custom health_check.url)
python scripts/health-check.py --agent-card-only

# Custom timeout
python scripts/health-check.py --timeout 15

# Read manifest paths from file
python scripts/health-check.py --paths-file manifests.txt

# Allow unhealthy agents without failing
python scripts/health-check.py --allow-unhealthy
```

### Arguments

| Argument | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `--output` | string | No | `health-results.json` | JSON output file path |
| `--timeout` | integer | No | `10` | Request timeout in seconds |
| `--agent-card-only` | flag | No | `False` | Check only a2a_config.agent_card_url |
| `--paths-file` | string | No | `None` | Newline-delimited file with manifest paths |
| `--allow-unhealthy` | flag | No | `False` | Exit 0 even if agents are unhealthy |

### Exit Codes

| Code | Meaning |
|------|---------|
| `0` | All agents healthy OR `--allow-unhealthy` flag used |
| `1` | One or more agents are unhealthy |

### Output Format

**Console Output:**
```
OK agent-svg-registry https://.../.well-known/agent-card.json 200
FAIL my-agent https://.../health FAIL Connection timeout
```

**JSON Report:**
```json
{
  "checked_at": "2024-01-15T10:30:00+00:00",
  "total": 42,
  "healthy": 40,
  "unhealthy": 2,
  "results": [
    {
      "agent_id": "agent-svg-registry",
      "manifest": "agents/agent-svg-registry.yaml",
      "url": "https://.../.well-known/agent-card.json",
      "ok": true,
      "status_code": 200,
      "checked_at": "2024-01-15T10:30:00+00:00",
      "error": null
    },
    {
      "agent_id": "my-agent",
      "manifest": "agents/my-agent.yaml",
      "url": "https://.../health",
      "ok": false,
      "status_code": null,
      "checked_at": "2024-01-15T10:30:01+00:00",
      "error": "Connection timeout"
    }
  ]
}
```

### Health Check Logic

1. **URL Selection**:
   - If `--agent-card-only`: Uses `a2a_config.agent_card_url`
   - Otherwise: Uses `health_check.url` if present, else `a2a_config.agent_card_url`

2. **Request**:
   - Method: GET
   - Headers: `Accept: application/json`
   - Timeout: As specified by `--timeout`

3. **Success Criteria**:
   - HTTP status code 200
   - No request exceptions

### Integration with GitHub Actions

The health check script is used in `.github/workflows/health-check.yml`:

```yaml
- name: Run health checks
  run: python scripts/health-check.py --output health-results.json

- name: Upload results
  uses: actions/upload-artifact@v4
  with:
    name: health-results
    path: health-results.json
```

---

## import-from-registry.py

**Purpose**: Imports agent manifests from external registries and marketplaces.

### Location
```
scripts/import-from-registry.py
```

### Dependencies
- `pyyaml` - YAML parsing
- `requests` - HTTP requests

### Supported Sources

| Source Name | Type | Slug |
|-------------|------|------|
| A2A Registry | external-registry | `a2a-registry` |
| Agora Registry | github-registry | `agora-registry` |
| OpenClaw Managed Agents | github-registry | `openclaw-managed-agents` |
| LangChain Hub | hub | `langchain-hub` |
| CrewAI Marketplace | marketplace | `crewai-marketplace` |
| AutoGen Studio Gallery | github-gallery | `autogen-studio-gallery` |
| AI Agent Index | github-registry | `ai-agent-index` |
| Venice AI Agent Marketplace | marketplace | `venice-ai-marketplace` |

### Usage

```bash
# Import from all sources (default limit per source)
python scripts/import-from-registry.py

# Limit imports per source
python scripts/import-from-registry.py --limit 10

# Import from specific source
python scripts/import-from-registry.py --source agora-registry

# Dry run (preview without writing)
python scripts/import-from-registry.py --source agora-registry --dry-run

# Use custom registry endpoint
python scripts/import-from-registry.py --endpoint https://my-registry.com/api/agents

# Custom timeout
python scripts/import-from-registry.py --timeout 20
```

### Arguments

| Argument | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `--limit` | integer | No | No limit | Max agents to import per source |
| `--source` | string | No | All sources | Filter by source name (slugified) |
| `--endpoint` | string | No | Built-in sources | Custom registry endpoint URL |
| `--timeout` | integer | No | `15` | Request timeout in seconds |
| `--dry-run` | flag | No | `False` | Preview without writing files |

### Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Import completed successfully |
| `1` | Import failed with errors |

### Import Process

1. **Load Candidates**: Fetches agent data from configured sources
2. **Extract Agent Card URLs**: Identifies valid Agent Card URLs from source data
3. **Fetch Agent Cards**: Downloads and validates Agent Card JSON
4. **Build Manifests**: Creates itinai-compatible manifest structure
5. **Write Files**: Saves new manifests to `agents/` directory

### Manifest Transformation

The importer transforms external agent data into itinai format:

```yaml
# Input (External Registry)
{
  "name": "My Agent",
  "agentCardUrl": "https://example.com/.well-known/agent-card.json",
  "protocolVersion": "1.0.0",
  "skills": [{"id": "skill1", "name": "Skill 1"}]
}

# Output (itinai manifest)
agent_id: "my-agent"
name: "My Agent"
a2a_config:
  agent_card_url: "https://example.com/.well-known/agent-card.json"
  protocol_version: "1.0.0"
skills:
  - id: "skill1"
    name: "Skill 1"
    tags: ["imported"]
source:
  name: "A2A Registry"
  type: "external-registry"
  url: "https://a2aregistry.org/api/agents"
  external_id: "uuid-here"
```

### Duplicate Prevention

- Tracks imported Agent Card URLs to prevent duplicates
- Generates unique `agent_id` using name slugification + URL hash if needed
- Skips agents already present in the registry

### GitHub Actions Integration

Used in `.github/workflows/sync-external.yml`:

```yaml
- name: Import from external registries
  run: |
    python scripts/import-from-registry.py --limit 10
    
- name: Validate imported manifests
  run: python scripts/validate.py
  
- name: Check imported agents health
  run: python scripts/health-check.py --output sync-health-results.json
```

---

## sync-wordpress.py

**Purpose**: Synchronizes agent manifests with WordPress site via REST API.

### Location
```
scripts/sync-wordpress.py
```

### Dependencies
- `pyyaml` - YAML parsing
- `requests` - HTTP requests

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `WP_USER` | WordPress username | Yes |
| `WP_KEY` | WordPress Application Password | Yes |
| `WP_APP` | Application Password label | Yes |
| `WP_SYNC_ENDPOINT` | WordPress REST API endpoint | Yes |

### Usage

```bash
# Sync all manifests
python scripts/sync-wordpress.py

# Sync specific manifests
python scripts/sync-wordpress.py agents/agent1.yaml agents/agent2.yaml

# Sync from paths file
python scripts/sync-wordpress.py --paths-file manifests.txt

# Custom endpoint
python scripts/sync-wordpress.py --endpoint https://my-site.com/wp-json/itinai/v1/sync

# With health report
python scripts/sync-wordpress.py --health-report health-results.json

# Custom timeout and retries
python scripts/sync-wordpress.py --timeout 30 --retries 5 --retry-delay 2
```

### Arguments

| Argument | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `paths` | list | No | All `agents/*.yaml` | Manifest paths to sync |
| `--endpoint` | string | No | `WP_SYNC_ENDPOINT` env or default | WordPress REST API endpoint |
| `--user-env` | string | No | `WP_USER` | Env var containing WordPress username |
| `--password-env` | string | No | `WP_KEY` | Env var containing app password |
| `--health-report` | string | No | `health-results.json` | Health check JSON report path |
| `--paths-file` | string | No | `None` | Newline-delimited file with manifest paths |
| `--timeout` | integer | No | `20` | Request timeout in seconds |
| `--retries` | integer | No | `3` | Retries per manifest for transient errors |
| `--retry-delay` | float | No | `2.0` | Base retry delay in seconds |
| `--limit` | integer | No | `0` (no limit) | Max manifests to sync |
| `--no-swapped-auth-retry` | flag | No | `False` | Disable auth retry with swapped credentials |

### WordPress Integration

The script posts agent manifests to a custom WordPress REST API endpoint:

```python
import requests
import yaml
import os

endpoint = os.environ["WP_SYNC_ENDPOINT"]
auth = (os.environ["WP_USER"], os.environ["WP_KEY"])

for manifest_path in manifests:
    with open(manifest_path) as f:
        manifest = yaml.safe_load(f)
    
    response = requests.post(
        endpoint,
        json=manifest,
        auth=auth,
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code == 200:
        print(f"Synced {manifest['agent_id']}")
    else:
        print(f"Failed to sync {manifest['agent_id']}: {response.text}")
```

### GitHub Actions Workflow

Configured in `.github/workflows/sync-wordpress.yml`:

```yaml
on:
  push:
    branches: [main]
    paths: ['agents/*.yaml']

jobs:
  sync-wordpress:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Sync to WordPress
        env:
          WP_USER: ${{ secrets.WP_USER }}
          WP_KEY: ${{ secrets.WP_KEY }}
          WP_APP: ${{ secrets.WP_APP }}
          WP_SYNC_ENDPOINT: ${{ secrets.WP_SYNC_ENDPOINT }}
        run: python scripts/sync-wordpress.py
```

---

## Best Practices

### Running Scripts Locally

1. **Always validate before committing**:
   ```bash
   python scripts/validate.py
   ```

2. **Test health checks locally**:
   ```bash
   python scripts/health-check.py --allow-unhealthy
   ```

3. **Preview imports before running**:
   ```bash
   python scripts/import-from-registry.py --dry-run
   ```

### CI/CD Integration

All scripts are designed to work in GitHub Actions:

- Exit codes indicate success/failure
- JSON output can be uploaded as artifacts
- Console output provides human-readable logs

### Error Handling

Scripts follow consistent error handling patterns:

- Validation errors are printed to stderr
- Network failures include exception details
- Partial failures don't stop entire batch processing

### Performance Considerations

- `--limit` flag prevents overwhelming external APIs
- `--timeout` flags control request timeouts
- Parallel processing can be added for large registries

---

## Troubleshooting

### Common Issues

**"No module named 'yaml'"**
```bash
pip install pyyaml
```

**"No module named 'jsonschema'"**
```bash
pip install jsonschema
```

**"No module named 'requests'"**
```bash
pip install requests
```

**Validation fails with "filename must be X.yaml"**
- Ensure the YAML filename matches the `agent_id` field exactly

**Health check fails with connection timeout**
- Increase timeout: `--timeout 30`
- Check network connectivity
- Verify the agent endpoint is accessible

**Import skips all candidates**
- Verify Agent Card URLs are publicly accessible
- Check that Agent Cards contain required fields (`protocolVersion`, `skills`)

---

For more information, see:
- [README.md](../README.md) - Main documentation
- [agent-card-spec.md](./agent-card-spec.md) - Agent Card specification
- [CONTRIBUTING.md](../CONTRIBUTING.md) - Contribution guidelines
