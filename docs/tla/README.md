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
- `ExpiredIsTakenOver`: an expired claim (CLAIMED or REVIEW) is always released, renewed or integrated. It assumes weak fairness on fetch and strong fairness on the expired release, which stands for the jittered backoff in `transaction`. With weak fairness alone an owner alternating heartbeat and done starves every other agent.

## Bounds

2 agents, 2 tasks, a lease of 1 tick, a review lease of 2, a clock up to 3, and 2 claims per agent (heartbeat, done, release, release --expired and integrate are free). About 310k distinct states, under a minute on a laptop. 3 agents with 2 claims each passes 27M states without finishing; with 1 claim each it passes but never reaches the one-live-task guard.

## Not modeled

- Clock skew: all agents share one clock.
- Retry limits: a failed push is just a later fetch and push.
- Handover, which moves `Owner` inside REVIEW by design, and commands outside the claim lifecycle (messages, checkpoints, reviews, plan), BLOCKED and CANCELLED. Review approval before integrate is assumed.
- Paths overlap and dependencies in `check_collisions`.
- The owner's view after someone else integrates its task: its lease belief stays, which no invariant reads.
- The tip check compares contents. Git compares commits, so it also refuses a tip that moved and came back; the retry lands on the same contents, so the outcomes match.

## Finding

`OneLiveTask` (one identity, one live CLAIMED task) is defined but not checked, because the code breaks it. An identity whose claim expired may claim another task, and `heartbeat_mutate` then renews the old claim (it checks only `require_owner`). TLC's trace: claim t1, lease expires, claim t2, heartbeat t1. Add `OneLiveTask` to `INVARIANTS` in `Claims.cfg` to reproduce it.

Last matched the code at commit `133a7895` (`tx.sh` transaction, `claim.sh` claim_mutate, heartbeat_mutate, release_mutate, `done.sh` done_mutate, integrate_mutate). Update this line when the model is checked against a newer engine.
