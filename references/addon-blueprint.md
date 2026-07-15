# Original Addon Blueprint

Use this workflow when asked for a new addon or a feature not already shipped by the reviewed plugins.

## Novelty Boundary

State three things separately:

1. existing primitives supplied by plugins;
2. the new orchestration, state model, or player experience;
3. what was not proven to exist end to end in the reviewed artifacts.

Do not call a combination original merely because it has a new name. The composition must add a meaningful invariant, feedback loop, state machine, optimization, accessibility mode, or cross-plugin workflow.

## Blueprint Template

### Product Contract

- player problem and fantasy;
- core loop;
- success/failure states;
- admin controls and observability;
- non-goals.

### Technical Contract

- plugin/API/version matrix;
- authoritative state and storage key strategy;
- state machine and transitions;
- trigger, precondition, mutation, post-event sequence;
- sync/async boundaries;
- optional dependency and downgrade behavior;
- reload/disconnect/crash recovery;
- anti-duplication and reentrancy controls.

### Delivery Contract

- vertical slice;
- migration/config format;
- unit, consumer-compile, integration, restart, and load tests;
- performance budget;
- rollback behavior.

## Quality Checks

- Every named API exists in this artifact or is labeled `UNVERIFIED`.
- At least one authoritative state owner is identified.
- Economy and reward writes are idempotent.
- Player/profile identity is never inferred from display text.
- Main-thread-only mutations are scheduled correctly.
- Visual/model/UI layers can fail without corrupting gameplay state.
- Config IDs are namespaced, lowercase, and migration-friendly.
- The design avoids copying vendor implementation details.

Use the build-ready blueprints in `docs/original-addon-blueprints.md` as examples, then adapt the template to the requested server constraints.
