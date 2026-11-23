---
name: dynamic-planner
description: Antigravity multi-step planning, live focus tracking, milestone decomposition, and iterative progress reporting.
slash_command: /plan
keywords: plan, steps, milestone, decompose, roadmap, checklist, goal, focus
---

## Dynamic Planner Directives
- **Hierarchical Step Decomposition**: Break non-trivial goals into 3 to 8 discrete, imperative milestone steps.
- **Real-Time Step Updates**: Emit `[action:update_steps:Step 1 (done)|Step 2 (in_progress)|Step 3 (pending)]` as progress evolves.
- **High-Level Focus Broadcasting**: Emit `[action:update_focus:Brief active activity]` to communicate the overarching objective.
- **Adaptability**: When an unexpected obstacle or error occurs, re-plan the remaining steps and broadcast the updated checklist.
