---------------------------- MODULE Claims ----------------------------
(***************************************************************************)
(* The claims protocol of kit/.uak/bin. Every command runs `transaction`   *)
(* (lib/tx.sh): fresh_state clones the claims branch, the command's        *)
(* mutation edits that clone, and one push to refs/heads/claims publishes  *)
(* it. Git refuses the push unless the remote tip is still the one that    *)
(* was cloned; the loser refetches and revalidates.                        *)
(*                                                                         *)
(* One TLA+ step that changes the shared state is one push. Fetch is the   *)
(* clone. A push carries the whole mutated clone, as `git push` does.      *)
(*                                                                         *)
(* The tip check compares the clone with the remote by content. A push     *)
(* git refuses because the tip moved and came back (A then B then A) is    *)
(* retried and lands on the same content, so the outcome is the same.      *)
(*                                                                         *)
(* CheckTip = FALSE is the broken variant: a push that overwrites the      *)
(* remote whatever it holds (as `git push --force` would).                 *)
(***************************************************************************)
EXTENDS Naturals, FiniteSets

CONSTANTS Agents, Tasks, Lease, MaxTime, Budget, CheckTip

None == "none"
Live == {"CLAIMED", "REVIEW"}        \* a claims/ID.md file exists
States == {"AVAILABLE"} \cup Live \cup {"INTEGRATED"}

VARIABLES
  st,      \* tasks/ID.md State on the claims tip
  own,     \* tasks/ID.md Owner
  until,   \* tasks/ID.md Lease-Until
  snap,    \* each agent's clone of claims (fresh_state)
  belief,  \* the Lease-Until each agent last pushed for a task: it works while that is in the future
  now,     \* one clock for everyone (clock skew is not modeled)
  budget   \* claims and heartbeats left per agent, so every run ends

vars == <<st, own, until, snap, belief, now, budget>>

Remote == [st |-> st, own |-> own, until |-> until]

TypeOK ==
  /\ st \in [Tasks -> States]
  /\ own \in [Tasks -> Agents \cup {None}]
  /\ until \in [Tasks -> Nat]
  /\ snap \in [Agents -> [st : [Tasks -> States], own : [Tasks -> Agents \cup {None}], until : [Tasks -> Nat]]]
  /\ belief \in [Agents -> [Tasks -> Nat]]
  /\ now \in 0..MaxTime
  /\ budget \in [Agents -> 0..Budget]

Init ==
  /\ st = [t \in Tasks |-> "AVAILABLE"]
  /\ own = [t \in Tasks |-> None]
  /\ until = [t \in Tasks |-> 0]
  /\ snap = [a \in Agents |-> Remote]
  /\ belief = [a \in Agents |-> [t \in Tasks |-> 0]]
  /\ now = 0
  /\ budget = [a \in Agents |-> Budget]

(* tx.sh fresh_state: clone the claims tip. *)
Fetch(a) ==
  /\ snap[a] # Remote
  /\ snap' = [snap EXCEPT ![a] = Remote]
  /\ UNCHANGED <<st, own, until, belief, now, budget>>

(* tx.sh transaction: commit the mutated clone S and push it. *)
Push(a, S) ==
  /\ CheckTip => snap[a] = Remote
  /\ st' = S.st /\ own' = S.own /\ until' = S.until
  /\ snap' = [snap EXCEPT ![a] = S]

Spend(a) == /\ budget[a] > 0
            /\ budget' = [budget EXCEPT ![a] = @ - 1]

(* claim.sh claim_mutate after check_collisions: no claim file, not closed, one live task per identity. *)
Claim(a, t) ==
  LET S == snap[a] IN
  /\ S.st[t] = "AVAILABLE"
  /\ ~\E u \in Tasks : S.own[u] = a /\ S.st[u] = "CLAIMED" /\ now < S.until[u]
  /\ Spend(a)
  /\ Push(a, [S EXCEPT !.st[t] = "CLAIMED", !.own[t] = a, !.until[t] = now + Lease])
  /\ belief' = [belief EXCEPT ![a][t] = now + Lease]
  /\ UNCHANGED now

(* claim.sh heartbeat_mutate: require_owner, then tx.sh refresh_lease. *)
Heartbeat(a, t) ==
  LET S == snap[a] IN
  /\ S.st[t] \in Live /\ S.own[t] = a
  /\ Spend(a)
  /\ Push(a, [S EXCEPT !.until[t] = now + Lease])
  /\ belief' = [belief EXCEPT ![a][t] = now + Lease]
  /\ UNCHANGED now

(* done.sh done_mutate: require_owner, CLAIMED -> REVIEW, lease refreshed. *)
Done(a, t) ==
  LET S == snap[a] IN
  /\ S.st[t] = "CLAIMED" /\ S.own[t] = a
  /\ Push(a, [S EXCEPT !.st[t] = "REVIEW", !.until[t] = now + Lease])
  /\ belief' = [belief EXCEPT ![a][t] = now + Lease]
  /\ UNCHANGED <<now, budget>>

(* claim.sh release_mutate by the owner: back to AVAILABLE, claim file removed. *)
Release(a, t) ==
  LET S == snap[a] IN
  /\ S.st[t] \in Live /\ S.own[t] = a
  /\ Push(a, [S EXCEPT !.st[t] = "AVAILABLE", !.own[t] = None, !.until[t] = 0])
  /\ belief' = [belief EXCEPT ![a][t] = 0]
  /\ UNCHANGED <<now, budget>>

(* claim.sh release_mutate --expired: someone else's claim once NOW >= Lease-Until. With Claim, a takeover. *)
ReleaseExpired(a, t) ==
  LET S == snap[a] IN
  /\ S.st[t] \in Live /\ S.own[t] # a /\ now >= S.until[t]
  /\ Push(a, [S EXCEPT !.st[t] = "AVAILABLE", !.own[t] = None, !.until[t] = 0])
  /\ UNCHANGED <<belief, now, budget>>

(* done.sh integrate_mutate (and review-merge.sh merge): any identity records REVIEW -> INTEGRATED; Owner stays. *)
Integrate(a, t) ==
  LET S == snap[a] IN
  /\ S.st[t] = "REVIEW"
  /\ Push(a, [S EXCEPT !.st[t] = "INTEGRATED", !.until[t] = 0])
  /\ UNCHANGED <<belief, now, budget>>

Tick ==
  /\ now < MaxTime
  /\ now' = now + 1
  /\ UNCHANGED <<st, own, until, snap, belief, budget>>

Next ==
  \/ Tick
  \/ \E a \in Agents :
       \/ Fetch(a)
       \/ \E t \in Tasks : Claim(a, t) \/ Heartbeat(a, t) \/ Done(a, t) \/ Release(a, t)
                           \/ ReleaseExpired(a, t) \/ Integrate(a, t)

Fairness == \A a \in Agents : /\ WF_vars(Fetch(a))
                              /\ WF_vars(\E t \in Tasks : ReleaseExpired(a, t))

Spec == Init /\ [][Next]_vars /\ Fairness

---------------------------------------------------------------------------
(* An agent holds a task while the lease it last pushed is in the future. *)
Holders(t) == {a \in Agents : belief[a][t] > now}

NoTwoLiveHolders == \A t \in Tasks : Cardinality(Holders(t)) <= 1

(* Whoever believes it holds a task is the Owner on the claims tip. *)
HolderIsOwner == \A t \in Tasks : \A a \in Holders(t) : own[t] = a

(* REVIEW and INTEGRATED keep their last holder; INTEGRATED is final. *)
KeepsLastHolder ==
  [][\A t \in Tasks : /\ st[t] \in {"REVIEW", "INTEGRATED"} /\ st'[t] \in {"REVIEW", "INTEGRATED"}
                         => own'[t] = own[t]]_vars
IntegratedIsFinal == [][\A t \in Tasks : st[t] = "INTEGRATED" => st'[t] = "INTEGRATED"]_vars

(* An expired claim is always released, renewed or finished: nothing keeps it stuck. *)
Expired(t) == st[t] = "CLAIMED" /\ until[t] <= now
ExpiredIsTakenOver == \A t \in Tasks : Expired(t) ~> ~Expired(t)
===========================================================================
