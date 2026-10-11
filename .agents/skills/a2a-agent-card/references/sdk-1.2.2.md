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
`engineering-coordination`. `required_skill_id` is trusted client configuration.

For secure cards, the `localBearer` map entry contains an
`HTTPAuthSecurityScheme` with `scheme="bearer"` and `bearer_format="opaque"`.
`SecurityRequirement.schemes` maps that name to `StringList()` for empty scopes.
Assign protobuf map messages with `CopyFrom`; cards are not Pydantic models.
Middleware independently enforces audience, expiry, role, and resource access.

Streaming, push, extended cards, and signing are absent or false. Synthetic
approval routes are operator controls outside advertised skills. Models, MCP,
procurement, payments, and registries remain unimplemented. Task reads/list/cancel
are protocol operations, not extra business skills.

Consult `tests/contract`, `tests/security`, `a2a/cards.py`, `a2a/client.py`,
`a2a/server.py`, and `security/http.py` before changing declarations.
