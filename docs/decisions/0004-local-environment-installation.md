# Standard local environment installation

Date: 11 October 2026
Status: Host repair verified; iCloud recurrence observed afterward

Keep uv's normal project `.venv` and editable source installation. Configure
`[tool.uv] link-mode = "copy"` so package installation creates independent files
rather than filesystem clones of the cache. Keep the existing lockfile and
Python 3.12.13; no dependency versions change.

## Evidence and repair

The previous `.venv` contained package files marked `hidden,compressed,dataless`.
A Python import diagnostic waited more than two minutes in file reads before
any agent communication. An environment outside Documents ran the demo quickly,
but requiring a separate environment path was an unnecessary operational burden.

A clean-cache download succeeded. Replacing the old environment in place stalled,
so the generated environment was preserved as `.runtime/venv-before-repair`.
A fresh standard `.venv` installed all 50 packages with
`uv sync --locked --link-mode copy --no-cache`. Both package files and editable
`.pth` files were locally resident without the hidden flag afterward. Ordinary
`uv sync --locked` also succeeded using the project copy-mode configuration.

Ordinary `uv run --locked a2a-lab demo` completed in 1.35 seconds, and its secure
variant in 1.05 seconds, with both owned children started and stopped. Verification
used temporary private credentials for the secure run and removed them afterward;
existing teaching credentials were preserved. All 108 behavioral tests, Ruff
lint/format checks, strict mypy, and the diff whitespace check passed.

## Limits

Copy mode does not control later macOS file offloading. This repair verifies the
current environment and normal uv workflow; it does not identify the software
that originally set the file flags or prove that cloning caused them. If the
flags recur, investigate the folder's storage policy. The README records the
standard environment repair and retains the older editable-import fallback.

The user subsequently reproduced a startup deadline failure. Dependencies,
editable `.pth` files, and credentials were again marked `dataless`, and the user
confirmed iCloud Drive manages Documents. Copy mode did not prevent recurrence.
Finder Keep Downloaded was enabled for the lab folder. The
[Docker execution decision](0005-container-lab.md) records the replacement
teaching path; the original timings above describe the repaired environment at
verification time, not a permanent resolution of iCloud storage behavior.
