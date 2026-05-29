# Contributing to ITINAI

Thank you for helping improve the ITINAI agent directory. This repository uses a
registry-as-code workflow: every registered agent is represented by one static
YAML manifest under `agents/`.

## Add or Update an Agent

1. Create or edit `agents/<agent-id>.yaml`.
2. Keep `agent_id` in kebab-case and make it match the filename.
3. Use HTTPS URLs for Agent Cards, health checks, catalogue feeds, contact URLs,
   and negotiation endpoints.
4. Include at least one skill with `id`, `name`, and `tags`.
5. Include `contact.email` so maintainers can reach the owner.
6. Open a pull request.

## Validation

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Run local manifest validation:

```bash
python scripts/validate.py
```

Run the same Agent Card availability check used by pull requests:

```bash
python scripts/health-check.py --agent-card-only --output health-results.json
```

Run scheduled-style health checks, which prefer `health_check.url` when present:

```bash
python scripts/health-check.py --output health-results.json
```

## Review Criteria

Maintainers review pull requests for schema validity, Agent Card availability,
HTTPS-only resource links, clear skill metadata, and owner contact details.
Agents that repeatedly fail scheduled health checks may be marked offline or
removed after owner contact.
