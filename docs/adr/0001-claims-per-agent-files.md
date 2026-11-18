# 1. Claims stay on one shared tip with a compare-and-swap push

## Status

Accepted (UAK-098, Nov 2026). Revisit if claims contention becomes the bottleneck again.

## Context

Every `uak` command clones the claims branch, edits it and pushes; git refuses the push if the tip moved and the command retries from a fresh clone (`transaction` in `kit/.uak/bin/lib/tx.sh`). At Reap, 12 agents retried in lockstep: one approval needed 14 attempts and a checkpoint 8, which is why the retry now has jittered backoff.

The alternative is for each agent to write only its own file (or its own ref). Its pushes never race anyone else's, so there are no retries. Readers merge all agents' files: the holder of a task is the live claim with the earliest claim time, with ties going to the lower agent. Nobody releases someone else's file. Taking over an expired claim is just a newer claim that the merge prefers.

`docs/tla/ClaimsPerAgent.tla` models that design with the same clock, bounds and safety invariants as `Claims.tla` (UAK-092). A claim counts only after the agent reads the merged view back and finds itself the holder.

## Decision

Keep one shared tip with the compare-and-swap push. TLC finds a counterexample for the per-agent design:

TLC result: HolderIsOwner is violated

The trace (2 agents, task t1, all in the same clock tick):

1. Agent 2 writes its claim and reads it back: it is the only claim, so it holds t1 and heartbeats.
2. Agent 1, whose last read was from before agent 2's write, sees nobody holding t1 and writes its own claim.
3. Both claims carry the same time. The merge gives t1 to agent 1 (lower number), yet agent 2 still works on it.

Re-reading before every heartbeat does not help: the race only moves to just after the read. A real clock with second resolution and skew between laptops makes equal or inverted claim times common, not rare.

A variant that confirms a claim only once its claim time is strictly in the past passes. It also needs a lease longer than that wait, and it then holds in 6.4M states. In real time, though, "in the past" has to mean "older than the worst clock skew between any two machines". Every claim would wait that long before work starts, and the safety would rest on a skew bound nothing enforces. The shared tip gives a total order for free.

## Consequences

- Claims keep paying retries under contention. The cost is bounded by the jittered backoff and `UAK_MAX_ATTEMPTS`, not removed.
- No engine change from this ADR.
- To revisit: per-agent files with a confirm delay larger than a measured skew bound, or per-agent files only for writes that cannot conflict (messages, checkpoints), with claims kept on the shared tip.
- The model, its config and this result are checked by `kit/.uak/tests/test_tla_check.py` (`the_per_agent_variant_is_checked`), so this line must change if TLC's answer does.
