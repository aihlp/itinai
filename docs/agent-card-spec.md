# Agent Card Specification

An Agent Card is a public JSON document that describes an agent endpoint for
A2A discovery and task handoff.

For `itinai` MVP, every registered agent must expose an Agent Card over HTTPS.
The manifest field `a2a_config.agent_card_url` should usually point to:

```text
https://<agent-domain>/.well-known/agent-card.json
```

## Registry Requirements

- The URL must use HTTPS.
- The URL must return HTTP 200 during pull request validation.
- The response should be JSON.
- The card should identify the agent, supported A2A protocol version, public
  endpoints, capabilities, and owner contact or support metadata.
- Signed Agent Cards may be added later; unsigned cards are accepted for MVP.

## Out of Scope

The registry stores only the URL and static metadata. It does not proxy A2A
messages, ANP negotiation traffic, catalogue feeds, payments, or runtime state.
