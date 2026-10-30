# Reuse the maintained boilerplate

Clone or copy this repository as the starting codebase. There is one maintained
implementation, with no duplicated `templates` tree. Setup, constitution,
coding skills, and exercises work without the sibling authoring documents.

## Rename deliberately

Renaming the checkout folder or Git remote does not require Python changes.
Keeping `a2a_lab` is a simple workshop starting point. For a different Python
distribution/import name, update these together:

1. Project name, CLI name/target, and Hatch package path in `pyproject.toml`.
2. `src/a2a_lab`, imports in source/tests, resource lookups such as
   `files("a2a_lab.agents")`, and installed metadata `version("a2a-lab")`.
3. `python -m a2a_lab` subprocesses, Docker entrypoints and initializer module,
   setup/exercise commands, and skill references to code paths.
4. The `A2A_LAB_` prefix and examples if changing configuration names; retain
   validation and parent-to-child settings propagation.
5. Compose project/image names if the fork must coexist with this lab. New
   names select new Docker volumes; deliberately preserve or reset lab state.

Inventory with `rg 'a2a_lab|a2a-lab|A2A_LAB_'`. Regenerate the lock after changing
the distribution, rebuild/install, and check imports from outside the source
directory to catch stale metadata. A name change does not add network identities
or authorize actions. Synthetic Alice/Bob are teaching roles, not production identity.

## Extend behavior

Follow [Lab 4](../../labs/04-boilerplate-extension/README.md): implement the domain
port in `agents`, inject it in `bootstrap`, and update the typed card and expected
skill in `a2a/cards.py`. Select behavior with validated settings, never request
text. Reuse the executor, middleware, task store, and client.

Use [a2a-implementation](../../.agents/skills/a2a-implementation/SKILL.md) for
workflows/integration and [a2a-agent-card](../../.agents/skills/a2a-agent-card/SKILL.md)
for advertised behavior. Invoke `$a2a-implementation` or `$a2a-agent-card` in a
coding agent that discovers repo skills. Otherwise read the files directly;
this guide needs no global skill installation. The
[constitution](../constitution.md) remains authoritative.

This topology has two fixed network roles with two selectable knowledge
workflows. A third peer needs explicit configuration, identity/audience issuance,
card, authorization, CLI, discovery, and supervisor/Compose wiring changes.
Workflow selection alone cannot add identities or destinations. Registry
discovery remains optional. For inference, preserve the
[local model adapter boundary](local-model-adapter.md).
