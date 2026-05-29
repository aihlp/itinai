# Agent Manifests

Each file in this directory must be named `<agent-id>.yaml`, where `agent-id`
matches the manifest's `agent_id` field.

Required fields:

- `agent_id`
- `name`
- `a2a_config.agent_card_url`
- `a2a_config.protocol_version`
- `skills`
- `contact.email`

All URLs must use HTTPS. See
[`schemas/agent-manifest.schema.json`](../schemas/agent-manifest.schema.json)
for the authoritative structure and [`../README.md`](../README.md) for a full
example.
