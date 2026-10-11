# Docker execution for the local teaching lab

Date: 11 October 2026
Status: Implemented and verified on Docker Desktop, Linux arm64

iCloud offloaded dependencies and credentials again after the clean host
environment repair. Keep Downloaded was enabled for the outer lab folder in
Finder. Use Docker Compose as the repeatable teaching path, without binding host
source, environment, configuration, or credential directories into runtime containers.

The multi-stage image pins Python 3.12.13 and uv 0.11.14 by version and image
digest, installs dependencies from the unchanged lockfile, and installs the
application non-editably. Compose builds it once through the knowledge service
and reuses that local image for the initializer, coordinator, and client. Its
allowlisted build context excludes secrets and environments. A separate verify
stage runs the locked checks and tests; the final non-root runtime omits dev tools.

Run two agent containers with separate filesystem and process namespaces, sharing
the knowledge container's loopback network namespace. Keep all existing literal
loopback endpoints and Agent Cards truthful; publish no host ports. This avoids
expanding the existing bind/destination policy merely to accommodate container DNS.
The operator client joins that namespace to perform real A2A discovery and calls.
A private internal bridge supplies no required external runtime connectivity.

Three named Docker volumes separate operator, coordinator, and knowledge authority.
Only a non-networked initializer mounts all three writable volumes. Agents and
client mount only their respective credential files read-only. Initializer reuse
verifies matching recipient-bound tokens, identities, and expiry; partial or
expired sets require explicit reset. Application resource ownership and exact
human approval controls are unchanged. Docker ownership is not a defense against
the local operator, who can simulate all roles and inspect volumes.

Health checks and Compose dependencies replace the native process supervisor for
this execution path. Real startup errors remain visible through container logs.
Runtime containers use read-only roots, dropped capabilities, no privilege
escalation, and finite memory/CPU/PID/tmpfs limits. Shared loopback does not isolate
agent network access from one another or add TLS/server identity. Restart loses
in-memory tasks and approval state; `/work` retains operator files until volume reset.

## Verification

The runtime image built successfully, with an initial source context of about
206 KB. Compose configuration validation and both agent health checks passed.
The Linux verification image passed all 111 tests, Ruff lint/format, and strict
mypy across 29 source modules. The suite includes three new credential-volume
cases for authority separation/reuse, partial-state denial, and expired-state denial.

A real authenticated Compose CLI call succeeded. Starting a disposable client
through Compose, including dependency checks, took 5.26 seconds; an A2A exchange
inside that client took 0.20 seconds. A separate live walkthrough verified Bob's
access denial, simulated human-role approval, identical-key retry, replay denial,
and cancellation with no late artifact. An unauthenticated Compose override also
returned the expected fixture answer in a separate temporary project.

Docker inspection confirmed UID/GID 10001, read-only roots and role-specific
credential mounts, shared network namespace, and zero published ports. The
temporary verification project's containers and volumes were removed afterward;
the authenticated lab remains available. Existing host teaching credentials were
not changed. These checks retain the core lab's deterministic-policy scope and
do not evaluate any model's prompt resistance.
