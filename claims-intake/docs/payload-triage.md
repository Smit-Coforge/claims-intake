# Payload Triage

Every payload in `data/fnol_edge.json` classified against `docs/api-contract.md` as you have completed it. The classification records what the contract says the service does, which is not always what the payload obviously violates.

Fill one row per payload. Where a payload is accepted, leave the rule, code, and status columns as `-`.

## Classification


| Payload | Outcome | Rule | Code                    | Status |
| ------- | ------- | ---- | ----------------------- | ------ |
| EDGE-01 | Created | -    | -                       | 201    |
| EDGE-02 | Created | -    | -                       | 201    |
| EDGE-03 | Created | -    | -                       | 201    |
| EDGE-04 | refused | V-7  | `POLICY_CANCELLED`      | 422    |
| EDGE-05 | refused | V-2  | `LOSS_BEFORE_INCEPTION` | 422    |
| EDGE-06 | refused | V-4  | `AMOUNT_EXCEEDS_LIMIT`  | 422    |
| EDGE-07 | refused | V-1  | `POLICY_NOT_FOUND`      | 422    |
| EDGE-08 | refused | -    | `MALFORMED_REQUEST`     | 400    |
| EDGE-09 | refused | V-5  | `TYPE_NOT_COVERED`      | 422    |
| EDGE-10 | refused | V-7  | `POLICY_CANCELLED`      | 422    |
| EDGE-11 | refused | -    | `MALFORMED_REQUEST`     | 400    |
| EDGE-12 | refused | -    | `MALFORMED_REQUEST`     | 400    |




## Decision log

Three payloads cannot be classified against the contract as it shipped, because the contract left a decision unmade. For each one, record the ambiguity, the decision, its authority, and the alternative you rejected.

A decision recorded here and nowhere else has not been made. Amend `docs/api-contract.md` so that a reader of the contract alone could not arrive at the other reading.

### Decision 1

**Payload. -** EDGE-07

**The ambiguity.** The contract never says whether policy numbers are case-sensitive, so `mot-4471` could be `MOT-4471` or a number that does not exist.

**Decision.** Treat them as different: lowercase does not match uppercase, so `mot-4471` is `POLICY_NOT_FOUND` (V-1, 422).

**Authority.** No work item addresses case sensitivity; decided from section 2.2, identifier as held in the policy master.

**Rejected alternative.** Auto-correcting case to force a match, because that records an identifier the caller did not send.

**Contract amended.** Section 4.2, note under V-1: match is exact; case is not folded; a case-only difference is `POLICY_NOT_FOUND`.

### Decision 2

**Payload. -** EDGE-11

**The ambiguity.** `flood` is not one of the five claim types, so it could be 400 (the request does not make sense) or 422 via V-5 (a type, just not covered on this policy).

**Decision.** 400 `MALFORMED_REQUEST`: `flood` is not a recognized value, so V-5 never runs.

**Authority.** Section 2.4: 400 is the caller's code; 422 is the caller's data. V-5 only checks whether a known type is permitted on the product.

**Rejected alternative.** `TYPE_NOT_COVERED` (422), because that tells the handler to pick a covered type and implies `flood` is a real type.

**Contract amended.** Section 4.1: a `claim_type` outside the 2.3 vocabulary is not well formed (`MALFORMED_REQUEST`, 400) and is refused before any rule; V-5 does not evaluate it.

### Decision 3

**Payload. -** EDGE-12

**The ambiguity.** Section 2.2 requires two decimal places; `3499.999` has three, so the service could reject it or round to two and continue.

**Decision.** Reject as 400 `MALFORMED_REQUEST`; the service does not round.

**Authority.** Sections 2.2 and 2.4: a value of the wrong shape is 400, not a figure to correct.

**Rejected alternative.** Rounding to `3500.00` and creating, because the recorded amount would not be what the caller sent.

**Contract amended.** Section 4.1: an `estimated_amount` with more than two decimal places is not well formed (`MALFORMED_REQUEST`, 400); the service does not round.

## Reconciliation

**Method.** Grepped all `raise` and error-code sites in `src/claims/models.py` and `src/claims/repository.py` (`MALFORMED_`, `POLICY_`, `LOSS_`, `AMOUNT_`, `TYPE_`, `DUPLICATE_`) and matched each against section 6.

**Codes produced.**

| Module | Code | Status in §6 |
| --- | --- | --- |
| `models.py` | `MALFORMED_REQUEST` | 400 |
| `repository.py` | *(none — no `raise`, no code token)* | — |

`models.py` raises `ValueError` / `ValidationError` when the body is not well formed. Sections 2.4 and 4.1 name that `MALFORMED_REQUEST`.

**Already covered.** `MALFORMED_REQUEST` → 400.

**Missing.** None. That row was already in section 6. No other contract code appears in those two files, so nothing was added.