# Agent decision log

## Accepted — V-6 is not a POLICY_RULES function

The agent split the duplicate check into its own function, `evaluate_not_duplicate`, which talks to the repository. The policy rules (V-2, V-7, V-3, V-4, V-5) stay in `POLICY_RULES`. `evaluate_notification` still runs them in this order: V-6, then V-1, then those five.

**Why this was accepted.** Contract section 4.1 says V-6 runs first because it does not read the policy. It only compares this notice to notices already stored. If the duplicate check lived inside `POLICY_RULES`, those functions would need the repository, and they are only supposed to see the request and the policy. Calling V-6 first, then the tuple, still matches 4.1. WI-0151 AC-2 still holds: a duplicate includes the existing claim reference.

## Rejected — treat a dead policy master as "policy not found"

The first validation tests only covered "the policy number is missing." They did not cover the master being down. The agent had to add three cases: timeout, unreachable, and unparsable. V-1 still must not catch `PolicyLookupFailed`.

**Why this was rejected.** Contract section 6 maps those three conditions to 5xx (`POLICY_MASTER_TIMEOUT`, `POLICY_MASTER_UNAVAILABLE`, `POLICY_MASTER_UNREADABLE`). V-1 is 422 `POLICY_NOT_FOUND` when the master answered and the number is not there. If V-1 swallowed `PolicyLookupFailed`, a timeout on MOT-4471 would tell the handler the policy does not exist. That is false, and retrying later could succeed. WI-0142 AC-4 is only for a number that is not in the master, not for a master that did not answer.
