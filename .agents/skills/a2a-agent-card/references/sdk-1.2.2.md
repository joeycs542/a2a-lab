# Pinned card boundary

Baseline: Python 3.12.13, `a2a-sdk` 1.2.2, A2A `1.0`, JSON-RPC. Checked against
the installed SDK and [versioned specification](https://a2a-protocol.org/v1.0.0/specification/)
on 11 October 2026. Recheck during an explicit compatibility upgrade.

The SDK uses protobuf messages: construct `AgentCard`, `AgentSkill`,
`AgentInterface`, and `AgentCapabilities` from `a2a.types`. Python uses
`supported_interfaces`/`protocol_version`; JSON uses
`supportedInterfaces`/`protocolVersion`. The URL belongs to an interface, not
the old top-level `url`/`preferredTransport` schema. Use SDK `agent_card_to_dict`
for JSON review; default false protobuf values can be omitted.

Application `version` comes from installed package metadata. The interface is
one approved JSON-RPC `1.0` URL, with text input and structured JSON output.
For knowledge, `knowledge_workflow=notes` expects `engineering-knowledge`;
`release-readiness` expects `release-readiness`. Coordinator retains
`engineering-coordination` in baseline mode; discovery selects
`engineering-discovery` or `engineering-review` from startup settings. Fixed
engineering specialists advertise `operations-runbook`, `secure-agent-design`, and
`release-readiness`. The lunch scenario advertises `lunch-food`, `lunch-budget`, and
`lunch-place` for the same fixed service IDs.
Its coordinator advertises `team-lunch-help` in single mode or `team-lunch-plan` in review mode.
`required_skill_id` selects the expected skill from trusted startup settings.

For secure cards, the `localBearer` map entry contains an
`HTTPAuthSecurityScheme` with `scheme="bearer"` and `bearer_format="opaque"`.
`SecurityRequirement.schemes` maps that name to `StringList()` for empty scopes.
Assign protobuf map messages with `CopyFrom`; cards are not Pydantic models.
Middleware independently enforces audience, expiry, role, and resource access.

Streaming, push, extended cards, and signing are absent or false. Synthetic
approval routes are operator controls outside advertised skills. Optional local-model inference is available through the Ollama adapter. MCP,
procurement, payments and open registration remain unimplemented. Curated search
and protected traces are application APIs outside advertised A2A operations.
Task reads/list/cancel
are protocol operations, not extra business skills.

Consult `tests/contract`, `tests/security`, `a2a/cards.py`, `a2a/client.py`,
`a2a/server.py`, and `security/http.py` before changing declarations.
