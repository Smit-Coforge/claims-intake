# Payload Triage

Every payload in `data/fnol_edge.json` classified against `docs/api-contract.md` as you have completed it. The classification records what the contract says the service does, which is not always what the payload obviously violates.

Fill one row per payload. Where a payload is accepted, leave the rule, code, and status columns as `-`.

## Classification


| Payload | Outcome | Rule | Code                    | Status |
| ------- | ------- | ---- | ----------------------- | ------ |
| EDGE-01 | Created | -    | Created                 | 201    |
| EDGE-02 | Created | -    | Created                 | 201    |
| EDGE-03 | Created | -    | Created                 | 201    |
| EDGE-04 | refused | V-7  | `POLICY_CANCELLED`      | 422    |
| EDGE-05 | refused | V-2  | `LOSS_BEFORE_INCEPTION` | 422    |
| EDGE-06 | refused | V-4  | `AMOUNT_EXCEEDS_LIMIT`  | 422    |
| EDGE-07 |         |      |                         |        |
| EDGE-08 |         |      |                         |        |
| EDGE-09 | refused | V-5  | `TYPE_NOT_COVERED`      | 422    |
| EDGE-10 | refused | V-7  | `POLICY_CANCELLED`      | 422    |
| EDGE-11 | refused | V-5  | `TYPE_NOT_COVERED`      | 422    |
| EDGE-12 |         |      |                         |        |




## Decision log

Three payloads cannot be classified against the contract as it shipped, because the contract left a decision unmade. For each one, record the ambiguity, the decision, its authority, and the alternative you rejected.

A decision recorded here and nowhere else has not been made. Amend `docs/api-contract.md` so that a reader of the contract alone could not arrive at the other reading.

### Decision 1

**Payload. -** EDGE-07

**The ambiguity.** What the contract failed to determine, and the two readings that were both available.

**Decision.** What the service does.

**Authority.** The work item, acceptance criterion, or product rule that supports it.

**Rejected alternative.** The other reading, and why it is wrong rather than merely less preferred.

**Contract amended.** Section and what changed.

### Decision 2

**Payload. -** EDGE-08

**The ambiguity.**

**Decision.**

**Authority.**

**Rejected alternative.**

**Contract amended.**

### Decision 3

**Payload. -** EDGE-12

**The ambiguity.**

**Decision.**

**Authority.**

**Rejected alternative.**

**Contract amended.**