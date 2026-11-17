# TLA+ model of the claims protocol

`Claims.tla` models what every `uak` command does to the claims branch: clone it (`fresh_state` in `kit/.uak/bin/lib/tx.sh`), apply one mutation, push. Git refuses the push when the remote tip moved, and the command retries from a fresh clone. One TLA+ step that changes shared state is one push in the code.

Run it with `bash scripts/tla_check.sh` (needs Java; the script downloads tla2tools.jar, pinned by version and SHA-256). The `tla` workflow runs it when this folder, `tx.sh` or `claim.sh` change.

| Config | Expected |
|---|---|
| `Claims.cfg` | no error |
| `ClaimsBroken.cfg` | a counterexample: with `CheckTip = FALSE` a push overwrites the tip, and two agents claim the same task from stale clones |

## What it checks

- `NoTwoLiveHolders`: at most one agent holds a task with a lease in the future.
- `HolderIsOwner`: an agent holding a live lease is the `Owner` on the claims tip.
- `KeepsLastHolder`, `IntegratedIsFinal`: REVIEW and INTEGRATED keep their owner, and INTEGRATED never changes.
- `ExpiredIsTakenOver`: with weak fairness on fetch and expired release, an expired claim is always released, renewed or finished.

## Bounds

3 agents, 2 tasks, a lease of 1 tick, a clock up to 3, and 1 claim or heartbeat per agent (done, release, release --expired and integrate are free). About 1.8M distinct states, a little over 2 minutes on a laptop. A budget of 2 makes it much bigger without new behavior to check.

## Not modeled

- Clock skew: all agents share one clock.
- Retry limits and backoff: a failed push is just a later fetch and push.
- Commands outside the claim lifecycle (messages, checkpoints, reviews, plan, handover), BLOCKED and CANCELLED. Review approval before integrate is assumed.
- Paths overlap, dependencies and the overlap-expired hint in `check_collisions`; the one-live-task rule is modeled.
- The tip check compares contents. Git compares commits, so it also refuses a tip that moved and came back; the retry lands on the same contents, so the outcomes match.

Last matched the code at commit `133a7895` (`tx.sh` transaction, `claim.sh` claim_mutate, heartbeat_mutate, release_mutate, `done.sh` done_mutate, integrate_mutate). Update this line when the model is checked against a newer engine.
