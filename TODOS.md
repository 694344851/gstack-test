# TODOS

## Design

- [x] Create a full visual design system via `/design-consultation` before implementation starts.
  Why: The current plan defines interaction structure, Chinese copy tone, hierarchy, and anti-slop layout rules, but it does not yet lock typography, color tokens, spacing scale, radius rules, or motion guidance.
  Pros: Prevents the desktop workspace from shipping as a structurally-correct but visually generic AI panel.
  Cons: Adds one explicit pre-implementation step.
  Context: This project has no `DESIGN.md` yet, and the plan-design-review identified that gap as the biggest remaining design-system risk.
  Depends on / blocked by: None.

## Engineering

- [ ] Upgrade the linear v1 generation task model to support branch lineage after the initial release stabilizes.
  Why: Future style branches, branch comparison, and branch-specific retries will eventually require explicit parent/child lineage instead of a single linear stage record.
  Pros: Makes future migration intentional instead of reactive; preserves the reason v1 stayed linear while keeping the path to richer versioning visible.
  Cons: Adds a tracked engineering debt item that is not actionable until the v1 task model is live and understood.
  Context: The current eng review deliberately chose a single linear `generation_task` state model to minimize v1 scope, but the product plan already anticipates future style branches.
  Depends on / blocked by: v1 task model and worker flow must ship and stabilize first.

- [x] Add browser E2E coverage for the library trash lifecycle.
  Why: The library modal now spans list state, detail state, confirm layers, and destructive mutations, so the browser path needed its own regression net.
  Pros: Locks the real user journey in place; proves trash/restore/delete wiring survives future UI refactors.
  Cons: Adds Playwright setup and a second test layer to maintain.
  Context: The feature now ships with Playwright coverage for active work -> trash, trash -> restore, and trash -> permanent delete plus deleted detail becoming unreachable.
  Depends on / blocked by: None.
