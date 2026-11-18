------------------------- MODULE ClaimsPerAgent -------------------------
(***************************************************************************)
(* A design the engine does NOT use, checked to decide whether to adopt   *)
(* it (docs/adr/0001-claims-per-agent-files.md).                           *)
(*                                                                         *)
(* Each agent writes only its own file (claims/<agent>/<ID>.md, or its own *)
(* ref), so a push never races another agent's and never retries. Readers  *)
(* merge every agent's file: the holder of a task is the live claim with   *)
(* the earliest claim time, ties broken by the lower agent number. A claim *)
(* is live while its Lease-Until is in the future.                         *)
(*                                                                         *)
(* Nobody can release someone else's file, so takeover of an expired claim *)
(* is just a newer claim the merge rule prefers. A claim counts only after *)
(* the agent reads the merged view back and finds itself the holder        *)
(* (Confirm); a heartbeat needs the same.                                  *)
(*                                                                         *)
(* Same clock and same invariants as Claims.tla.                           *)
(***************************************************************************)
EXTENDS Naturals, FiniteSets

CONSTANTS Agents, Tasks, Lease, MaxTime, Budget   \* Agents: a set of numbers, the tie-break order

ASSUME Agents \subseteq Nat

NoClaim == [live |-> FALSE, at |-> 0, until |-> 0]

VARIABLES
  file,    \* file[a][t]: what agent a published for task t (only a writes it)
  view,    \* view[a]: agent a's last read of every agent's files
  belief,  \* the Lease-Until an agent confirmed for a task: it works while that is in the future
  now,
  budget

vars == <<file, view, belief, now, budget>>

Records == [live : BOOLEAN, at : Nat, until : Nat]

TypeOK ==
  /\ file \in [Agents -> [Tasks -> Records]]
  /\ view \in [Agents -> [Agents -> [Tasks -> Records]]]
  /\ belief \in [Agents -> [Tasks -> Nat]]
  /\ now \in 0..MaxTime
  /\ budget \in [Agents -> 0..Budget]

(* The merge on read: live claims, earliest first, then the lower agent number. *)
Live(F, a, t) == F[a][t].live /\ F[a][t].until > now
Before(F, a, b, t) == \/ F[a][t].at < F[b][t].at
                      \/ F[a][t].at = F[b][t].at /\ a < b
Holder(F, t) ==
  IF \E a \in Agents : Live(F, a, t)
  THEN CHOOSE a \in Agents : Live(F, a, t) /\ \A b \in Agents \ {a} : Live(F, b, t) => Before(F, a, b, t)
  ELSE 0   \* 0 is not an agent: nobody holds t

Init ==
  /\ file = [a \in Agents |-> [t \in Tasks |-> NoClaim]]
  /\ view = [a \in Agents |-> file]
  /\ belief = [a \in Agents |-> [t \in Tasks |-> 0]]
  /\ now = 0
  /\ budget = [a \in Agents |-> Budget]

Read(a) ==
  /\ view[a] # file
  /\ view' = [view EXCEPT ![a] = file]
  /\ UNCHANGED <<file, belief, now, budget>>

(* claim: the agent's last read shows nobody holding t; it writes its own file, no tip check needed. *)
Claim(a, t) ==
  /\ ~file[a][t].live
  /\ Holder(view[a], t) = 0
  /\ budget[a] > 0 /\ budget' = [budget EXCEPT ![a] = @ - 1]
  /\ file' = [file EXCEPT ![a][t] = [live |-> TRUE, at |-> now, until |-> now + Lease]]
  /\ UNCHANGED <<view, belief, now>>

(* Read back after the write: the claim counts only if the merge picks this agent. *)
Confirm(a, t) ==
  /\ view[a] = file
  /\ Holder(file, t) = a
  /\ belief[a][t] # file[a][t].until
  /\ belief' = [belief EXCEPT ![a][t] = file[a][t].until]
  /\ UNCHANGED <<file, view, now, budget>>

(* heartbeat: its own file still holds the claim, and its last read still names it the holder. *)
Heartbeat(a, t) ==
  /\ file[a][t].live
  /\ Holder(view[a], t) = a
  /\ file' = [file EXCEPT ![a][t].until = now + Lease]
  /\ belief' = [belief EXCEPT ![a][t] = now + Lease]
  /\ UNCHANGED <<view, now, budget>>

Release(a, t) ==
  /\ file[a][t].live
  /\ file' = [file EXCEPT ![a][t] = NoClaim]
  /\ belief' = [belief EXCEPT ![a][t] = 0]
  /\ UNCHANGED <<view, now, budget>>

Tick ==
  /\ now < MaxTime
  /\ now' = now + 1
  /\ UNCHANGED <<file, view, belief, budget>>

Next ==
  \/ Tick
  \/ \E a \in Agents : \/ Read(a)
                       \/ \E t \in Tasks : Claim(a, t) \/ Confirm(a, t) \/ Heartbeat(a, t) \/ Release(a, t)

Spec == Init /\ [][Next]_vars

---------------------------------------------------------------------------
Holders(t) == {a \in Agents : belief[a][t] > now}

(* The same safety properties as Claims.tla. *)
NoTwoLiveHolders == \A t \in Tasks : Cardinality(Holders(t)) <= 1
HolderIsOwner == \A t \in Tasks : \A a \in Holders(t) : Holder(file, t) = a
===========================================================================
