# Hindsight audit: credit-default-leaked-payment-event

**Release decision:** BLOCK<br>
**Verdict:** `confirmed`<br>
**Catalog write-back:** awaiting human approval

## Evidence path

`payment_events_after_decision.payment_recorded_at`
-> `feature_pipeline_leaky.days_since_last_payment`

The transformation reads the configured post-outcome source without an
`available_at <= prediction_time` cutoff.

## Point-in-time validation

| Measure | Observed | Reconstructed |
|---|---:|---:|
| AUC | 1.000000 | 0.833630 |
| Advantage over baseline | 0.301712 | 0.135342 |

The reconstruction excluded 4,000 post-cutoff records. Only 44.858% of the
observed advantage remained, satisfying the frozen majority-loss rule.

## False-positive control

The legitimate `prior_delinquencies` feature had a large 0.226554 ablation
delta, but its AUC remained 0.924842 after point-in-time reconstruction.
Hindsight returned `clear_for_release`, demonstrating that feature importance
alone cannot confirm leakage.

## Proposed remediation

Add the following predicate to the payment join:

```sql
payment.available_at <= application.prediction_time
```

The full proposal is in `examples/remediation.sql` and independently verifies
as safe. No change has been applied automatically.

## Planned approved write-back

- field tag
- `hindsight.auditVerdict` structured property
- native DataHub audit Document
- active `CUSTOM / ML_LEAKAGE` incident
