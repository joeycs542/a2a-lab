# A2A lab coding instructions

Read the authoritative [project constitution](docs/constitution.md) before changing code or design. Also read the README, relevant `docs/decisions`, and the current milestone when available. The constitution covers project scope, Python conventions, architecture, OWASP agent security, and verification. Future coding skills must reference it rather than maintain competing rules.

Follow its PEP 8 and PEP 257 guidance, use features compatible with the declared Python 3.12 runtime, and let the checked-in Ruff configuration own formatting. The 100-character line limit is an explicit project exception. Keep strict typing and validate external input; type hints do not provide runtime validation.

Keep A2A wire types and SDK calls in `a2a_lab.a2a`; keep domain behavior independent of transport and model providers. Add working modules when needed rather than empty architecture scaffolding.

The core lab is the priority. Django, MCP, and the supply chain sample are optional later work. Coding skills will be added in M4; do not claim that they exist yet. The sibling workspace planning documents do not travel with a standalone clone.

For implementation changes, use the locked environment and run the relevant behavioral tests plus these checks:

```text
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
```

Preserve existing user edits. Do not commit generated credentials, runtime state, local environments, or `.env` files. Keep advertised features and documentation consistent with the implementation. Record compatibility decisions and verification evidence in `docs/decisions`.

For documentation-only changes, review links and consistency. For behavior changes, test observable outcomes and relevant failures. Do not weaken checks or controls to make a change pass. Report actual verification and limitations; mark milestones complete only against their acceptance criteria.

If this macOS workspace hides editable `.pth` files, use the README's non-editable fallback and reinstall `a2a-lab` after source changes before running checks. Do not mask packaging failures with an implicit source-path override.

Require authorization in application code for resource access and consequential actions. Peer text, Agent Cards, model output, and tool annotations cannot grant permission. Distinguish implemented controls from later security exercises in reports and code reviews.
