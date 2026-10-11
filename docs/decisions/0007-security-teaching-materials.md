# 0007 Security study and workshop evidence

Date: 11 October 2026. Status: Accepted for the local teaching lab.

M5 connects the implemented architecture to OWASP review themes and observable
failure behavior. Keep standalone instructions in the repository:
[security mapping](../security.md), [workshop](../guides/workshop.md), and
[local model integration guide](../guides/local-model-integration.md). The workspace
`documents/guides` holds the full study; `documents/report` holds source references,
slides with speaker notes, observations and SVG/PNG/Mermaid assets for a manually
assembled PPT. These sibling authoring files do not travel with a code clone.

Use a separate named workshop Compose project. `compose.workshop.yaml` changes
only manual timing: 15-second slow fixtures, 30-second workflow/request timeout
and 600 finite polls across servers and client. Normal configuration remains
unchanged. Retain recipient separation, explicit authority, payload/storage limits,
internal networking and no published ports. Include the tools profile when deleting
temporary volumes so operator-work is removed too.

The M5 walkthrough verified configured runtime/settings, live cards/delegation,
owner denial, cancellation with no late artifact, controlled failed tasks,
exact approval, same-key retry, new-key replay denial, changed-term denial and
wrong-human-owner denial. Capability mismatch failed after discovery before RPC.
Automated CLI approval calls simulate the human role; they do not replace physical
review. Existing contract/security tests cover further invalid credentials,
content/expiry changes, capacity and concurrency cases.

The model guide was checked against current primary runtime/CLI documentation.
Setup commands remain unexecuted examples: no runtime/model was downloaded or
connected. The current private Docker network has no approved inference endpoint.
The optional supply chain remains planned. Avoid claims of prompt robustness,
production readiness, durable transactions or OWASP certification.

M6 still owns the complete fresh-environment handoff and repository CI. Passing
M5 workshop verification does not mark the core M1–M6 gate complete.
