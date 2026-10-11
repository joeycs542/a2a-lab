# M4 Reusable boilerplate and coding skills

Date: 11 October 2026
Status: Implemented and verified

Keep one maintained repository as the boilerplate. Add repository-scoped
implementation and Agent Card skills linked to the constitution, with normal
implicit discovery metadata. Agents without automatic skill discovery can read
the files directly; no global installation is needed for the guide.

The worked `ReleaseReadinessAgent` implements the existing `KnowledgeLookup`
port in the knowledge network role. A literal setting selects notes or readiness;
bootstrap, card description/examples, and trusted expected capability agree.
Request text cannot change the choice. This adds no third peer or credential
audience. Shared transport, lifecycle, destinations, ownership, and exact approvals
remain enforced.

Extension and card exercises connect declarations to real HTTP behavior and
mismatch denial. Reuse guidance covers package renaming and explicit third-peer
wiring. Model adapter guidance identifies inference separation, typed output and
provenance, budgets, cancellation, and authority boundaries. No model or inference
adapter is installed; runtime-specific guidance remains M5 work.

## Verification

Both skills passed the bundled skill-creator frontmatter/structure validator,
using isolated PyYAML 6.0.3 without changing project dependencies. Repository
Markdown links/fences were checked in a standalone snapshot: required links stay
inside the repository and do not depend on sibling authoring documents.

The locked Docker verification stage passed all 124 tests, Ruff lint/format, and
strict mypy across 31 source files. New cases cover both workflows/profiles,
configured served endpoints, secret-free cards, runnable examples, mismatch
before RPC, unsupported streaming/extended-card operations, non-text input,
and deterministic fixture behavior. Existing lifecycle/security checks still pass.

The real Compose extension returned the readiness checklist through coordinator
and knowledge over HTTP. A client expecting notes refused the readiness card
with exit 1 and no RPC send. `[fail]` produced failed tasks at both hops with
controlled errors. A separate repository snapshot without `.git`, `.venv`, host
credentials, or sibling authoring documents built and ran the documented extension.
Temporary verification containers/volumes are cleaned up after the walkthrough.

These are deterministic policy/contract checks, not model prompt-resistance
evaluation. The boilerplate retains a fixed two-role topology; the new workflow
does not implement arbitrary agents, models, or registry discovery.
