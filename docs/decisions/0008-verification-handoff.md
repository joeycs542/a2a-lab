# 0008 Core lab verification and handoff

Date: 11 October 2026. Status: Accepted for the local engineering lab.

## Decision

Use the locked Docker verification stage as the common CI/local check path.
It runs Ruff lint/format, strict mypy and the existing unit, contract, integration
and security suite. Disable external networking on that verification command;
container loopback remains available for the real HTTP integration tests.
Image and package installation happen earlier with network access.

[GitHub Actions](../../.github/workflows/lab-ci.yaml) checks all pushes and pull
requests and supports manual dispatch on Ubuntu 24.04. Use read-only contents
permission, a full-SHA `actions/checkout` 7.0.1 pin and no persisted checkout token.
Do not use privileged pull-request triggers, application secrets or deployment
steps. The workflow also builds the installed runtime, exercises both supervised
profiles and release-readiness with runtime networking disabled, validates Compose
overrides, runs independent Compose agents, and always removes its teaching state.

The single-container supervised smoke uses a non-root installed wheel, read-only
root, dropped capabilities, finite CPU/memory/PIDs and temporary private writable
storage. Its 512 MB limit covers the supervisor and both children together; it is
separate from Compose's 256 MB per-container teaching limit. Temporary credentials
are generated there rather than inherited from an operator machine.

Provide a standalone [handoff guide](../guides/handoff.md) linking setup, exercises,
constitution, skills, security evidence, local-model guidance and cleanup. Keep the
full authoring study/presentation under the workspace's outer `documents`, which
remains outside Git and must be distributed separately when needed.

## Reproducibility and evidence scope

Verification uses a standalone snapshot made from Git-tracked source plus the
new M6 workflow. No host `.venv`, `.env`, `.runtime`, `.git`, source-path override
or sibling authoring documents are copied. This is a source snapshot, not a remote
clone or a hosted GitHub run. It retains the pinned SDK/protocol/runtime and lock.

A fresh macOS uv environment with a new package cache passed all 124 tests in
6.02 seconds, Ruff lint/format and strict mypy for 31 source files. Native `doctor`,
the explicitly in-process SDK probe, supervised unauthenticated and authenticated
demos, and the authenticated release-readiness extension completed. Packaged notes
were available when importing from outside the source working directory.

The installed Linux runtime also completed those smoke commands with `--network
none`, including real loopback A2A between supervised child processes. The workflow
passed actionlint 1.7.12, using the official container image digest
`sha256:b1934ee5f1c509618f2508e6eb47ee0d3520686341fec936f3b79331f9315667`.
A Docker build with cached image layers disabled passed the same 124 tests in
5.98 seconds, plus lint/format and strict mypy. Package installation could still
reuse the BuildKit package cache; it was not an empty Docker daemon or image store.
The fresh Compose workshop verified task ownership denials, cancellation without
a late artifact, controlled failure, exact approval, same-key receipt, new-key replay
denial, changed terms and wrong-owner approval denial. The worked extension
and unsuitable-card rejection were exercised after service recreation.

Hosted CI has not run: activation needs a pushed commit and Actions enabled in the
remote repository. Local Docker validation is Linux arm64 on Docker Desktop;
the configured hosted runner is Linux amd64. Do not present local outcomes as a
green hosted check or as verification of every supported hardware configuration.

## References and limits

Reviewed [checkout release/source](https://github.com/actions/checkout/commit/3d3c42e5aac5ba805825da76410c181273ba90b1),
[GitHub workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax),
[GitHub secure use](https://docs.github.com/en/actions/reference/security/secure-use),
[Docker network-disabled RUN](https://docs.docker.com/reference/dockerfile/#run---networknone),
and [actionlint usage](https://github.com/rhysd/actionlint/blob/main/docs/usage.md).

Completion concerns the reproducible core teaching lab, not production security,
model evaluation or durable commercial transactions. The optional supply chain
remains unimplemented. Preserve the [security limits](../security.md), credential
expiry/reset behavior and the distinction between simulated approver tests and
actual human review in team delivery materials.
