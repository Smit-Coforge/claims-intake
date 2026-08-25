# Claims Intake Service: API Contract

Version 0.4. Owned by the claims intake team. Consumed by the claims portal team.

This document is the authority on what the service accepts, what it returns, and under what conditions it refuses. Where the code and this document disagree, the document is correct and the code is a defect.

Sections 1 through 3 are fixed. Do not edit them.

## 1. Purpose and scope

The claims intake service accepts a first notice of loss from the claims portal, validates it against the policy master and a table of business rules, and either records a notification and issues a claim reference or refuses the submission with a specific reason.

**In scope.** Accepting a notification, validating it, and recording it. Issuing a claim reference. Reporting the reason a notification was refused.

**Out of scope.** Adjusting, reserving, payment, and any decision about coverage beyond the rules in section 4. The service decides whether a notification is well formed and admissible. It does not decide whether the claim will be paid.

**The policy master is a dependency, not part of this service.** The service reads policy records from it and does not write to it. A policy that cannot be read is a condition this contract specifies, and it is specified separately from a policy that does not exist, because the two require different action from the caller.

**Compatibility.** Adding a field to a response is a compatible change and callers must ignore fields they do not recognize. Adding a new error code is a compatible change and callers must fall through to default handling for a code they do not recognize. Changing the meaning of an existing code, removing a field, or changing a status code for an existing condition is not compatible and does not happen without a version increment agreed with the portal team.

## 2. Request



### 2.1 Endpoint

```
POST /notifications
Content-Type: application/json
```



### 2.2 Body


| Field              | Type    | Required | Notes                                                         |
| ------------------ | ------- | -------- | ------------------------------------------------------------- |
| `policy_number`    | string  | yes      | Identifier as held in the policy master. Not empty.           |
| `loss_date`        | string  | yes      | Calendar date, `YYYY-MM-DD`.                                  |
| `claim_type`       | string  | yes      | One of the values in 2.3. Not empty.                          |
| `estimated_amount` | decimal | yes      | United States dollars, two decimal places. Greater than zero. |
| `description`      | string  | no       | Free text. Absent and `null` are equivalent.                  |


The service rejects a body carrying a field not listed above. A misspelled field name is a defect in the caller's code, and accepting the payload with the field ignored would record a notification built from data the caller did not send.

### 2.3 Claim type vocabulary

`collision`, `theft`, `glass`, `liability`, `weather`.

Which of these are admissible on a given notification depends on the product the policy is written on. The vocabulary is fixed by this contract. The permitted subset is a property of the policy record and is evaluated by rule `V-5`.

### 2.4 Well formed against acceptable

A request that cannot be interpreted is refused with status `400`. This means the body was not valid JSON, a required field was absent, a field carried a value of the wrong type, or a field was present that this contract does not define. The caller's code is wrong.

A request that was interpreted and whose content is not admissible is refused with status `422`. The caller's data is wrong, and a person needs to see the reason.

This split is stated here once and holds without exception everywhere else in this document.

## 3. Success response

A notification that passes every rule in section 4 is recorded and the service responds:

```
201 Created
Content-Type: application/json

{
  "claim_reference": "CLM-2026-000317",
  "status": "recorded"
}
```

`claim_reference` matches the pattern `CLM-YYYY-NNNNNN`, where `YYYY` is the calendar year in which the notification was recorded and `NNNNNN` is a zero padded sequence. A claim reference is unique across all recorded notifications and is never reissued. It is the value the claims handler quotes and the value every downstream system keys on.

`status` is `recorded` on every success response this contract defines. It exists because the portal displays it and because a future state that is not `recorded` is foreseeable. Callers must not treat it as constant.

A refused notification is never recorded and no claim reference is issued. There is no partial outcome: either a notification exists with a reference, or nothing was written.

## 4. Validation



### 4.1 Evaluation order

Rules are evaluated in the following order: V-6, V-1, V-2, V-7, V-3, V-4, V-5. Evaluation stops at the first rule that fails, and that rule's code is the only one returned to the caller.

V-6 is evaluated first because it does not read a policy field; it compares the submitted values against past notifications. V-1 is evaluated next. V-1 short circuits: if it fails, no rule that reads a policy field is evaluated.

V-7 is evaluated before V-3 so that a policy that is both cancelled and past its original expiry is reported as cancelled (WI-0158, AC-4), rather than expired.

A request that is not well formed never reaches this order. It is refused with `MALFORMED_REQUEST` and status `400`. A `claim_type` that is not one of the values in 2.3 is not well formed: it is not a claim type this contract defines, and V-5 is not evaluated. An `estimated_amount` that carries more than two decimal places is not well formed. The service does not round.

### 4.2 Rule table


| ID  | Condition                                                                              | Code                     | Status |
| --- | -------------------------------------------------------------------------------------- | ------------------------ | ------ |
| V-6 | no existing recorded notification matches (`policy_number`, `loss_date`, `claim_type`) | `DUPLICATE_NOTIFICATION` | 409    |
| V-1 | `policy_number` exists in the policy master                                            | `POLICY_NOT_FOUND`       | 422    |
| V-2 | `loss_date` >= policy `effective_date`                                                 | `LOSS_BEFORE_INCEPTION`  | 422    |
| V-7 | `cancellation_date` = null OR `loss_date` < `cancellation_date`                        | `POLICY_CANCELLED`       | 422    |
| V-3 | `loss_date` <= policy `expiry_date`                                                    | `LOSS_AFTER_EXPIRY`      | 422    |
| V-4 | `estimated_amount` <= policy `limit`                                                   | `AMOUNT_EXCEEDS_LIMIT`   | 422    |
| V-5 | `claim_type` permitted on the policy's product                                         | `TYPE_NOT_COVERED`       | 422    |

V-1 matches `policy_number` exactly as submitted. The service does not fold case. A policy number that differs only in case from one held in the policy master does not exist (`POLICY_NOT_FOUND`).

Boundaries are inclusive as written. A loss on the inception date is
covered (WI-0142, AC-3). An amount equal to the limit is within cover.

## 5. Error envelope

Every non-2xx response returns this shape and no other.

```
{
  "code": "LOSS_BEFORE_INCEPTION",
  "message": "Loss date precedes policy inception.",
  "detail": {
    "rule": "V-2",
    "loss_date": "2026-02-11",
    "effective_date": "2026-03-01"
  }
}
```

`code` is stable and callers branch on it. `message` is for display and may change without notice. `detail` carries the values that produced the decision and its keys vary by code.

The HTTP status is not a field in the body. It is taken from section 6. When the refusal is a rule in section 4, `detail` includes `rule`. `MALFORMED_REQUEST` and the three policy-master codes are not rules and do not carry `rule`.

`MALFORMED_REQUEST` — required field absent, wrong type, extra field, or body not valid JSON.

```
{
  "code": "MALFORMED_REQUEST",
  "message": "The request could not be interpreted.",
  "detail": {
    "field": "estimated_amount"
  }
}
```

`POLICY_NOT_FOUND` — V-1. The policy number is not in the master.

```
{
  "code": "POLICY_NOT_FOUND",
  "message": "No policy exists for the submitted policy number.",
  "detail": {
    "rule": "V-1",
    "policy_number": "MOT-9999"
  }
}
```

`LOSS_BEFORE_INCEPTION` — V-2. `loss_date` is earlier than
`effective_date`.

```
{
  "code": "LOSS_BEFORE_INCEPTION",
  "message": "Loss date precedes policy inception.",
  "detail": {
    "rule": "V-2",
    "loss_date": "2026-02-11",
    "effective_date": "2026-03-01"
  }
}
```

`LOSS_AFTER_EXPIRY` — V-3. `loss_date` is later than `expiry_date`.

```
{
  "code": "LOSS_AFTER_EXPIRY",
  "message": "Loss date falls after policy expiry.",
  "detail": {
    "rule": "V-3",
    "loss_date": "2026-03-20",
    "expiry_date": "2026-02-28"
  }
}
```

`AMOUNT_EXCEEDS_LIMIT` — V-4. `estimated_amount` is above the policy
`limit`.

```
{
  "code": "AMOUNT_EXCEEDS_LIMIT",
  "message": "Estimated amount exceeds the policy limit.",
  "detail": {
    "rule": "V-4",
    "estimated_amount": "26000.00",
    "limit": "10000.00"
  }
}
```

`TYPE_NOT_COVERED` — V-5. `claim_type` is not permitted on the
product.

```
{
  "code": "TYPE_NOT_COVERED",
  "message": "Claim type is not covered on this product.",
  "detail": {
    "rule": "V-5",
    "claim_type": "collision"
  }
}
```

`DUPLICATE_NOTIFICATION` — V-6. A recorded notification already
matches `policy_number`, `loss_date`, and `claim_type`.
`detail.claim_reference` is the existing record (WI-0151, AC-2).

```
{
  "code": "DUPLICATE_NOTIFICATION",
  "message": "A notification for this loss has already been recorded.",
  "detail": {
    "rule": "V-6",
    "claim_reference": "CLM-2026-000317"
  }
}
```

`POLICY_CANCELLED` — V-7. `loss_date` falls on or after
`cancellation_date`.

```
{
  "code": "POLICY_CANCELLED",
  "message": "The policy was cancelled on or before the loss date.",
  "detail": {
    "rule": "V-7",
    "loss_date": "2026-01-15",
    "cancellation_date": "2026-01-15"
  }
}
```

`POLICY_MASTER_UNAVAILABLE` — the master could not be reached.

```
{
  "code": "POLICY_MASTER_UNAVAILABLE",
  "message": "The policy master could not be reached.",
  "detail": {
    "policy_number": "MOT-4471"
  }
}
```

`POLICY_MASTER_TIMEOUT` — the master did not answer in time.

```
{
  "code": "POLICY_MASTER_TIMEOUT",
  "message": "The policy master did not respond in time.",
  "detail": {
    "policy_number": "MOT-4471"
  }
}
```

`POLICY_MASTER_UNREADABLE` — the master answered, but the response
could not be read.

```
{
  "code": "POLICY_MASTER_UNREADABLE",
  "message": "The policy master response could not be read.",
  "detail": {
    "policy_number": "MOT-4471"
  }
}
```



## 6. Status code mapping


| Code                        | Status |
| --------------------------- | ------ |
| `MALFORMED_REQUEST`         | 400    |
| `POLICY_NOT_FOUND`          | 422    |
| `LOSS_BEFORE_INCEPTION`     | 422    |
| `LOSS_AFTER_EXPIRY`         | 422    |
| `AMOUNT_EXCEEDS_LIMIT`      | 422    |
| `TYPE_NOT_COVERED`          | 422    |
| `DUPLICATE_NOTIFICATION`    | 409    |
| `POLICY_CANCELLED`          | 422    |
| `POLICY_MASTER_UNAVAILABLE` | 503    |
| `POLICY_MASTER_TIMEOUT`     | 504    |
| `POLICY_MASTER_UNREADABLE`  | 502    |


All rule codes (V-1 through V-7) and malformed request return 4xx because the caller's data is what needs to change; retrying an identical payload will never approve. The three policy master conditions, unavailable, timeout, and unreadable return 5xx because none originate from anything wrong in the request; the same payload may approve if retried once the dependency recovers.