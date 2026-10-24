# Policy boundaries for Phase 1

| Rule | Boundary cases | Required deterministic outcome |
|---|---|---|
| Shipping | Order value ₹499, ₹500 | Because the configured rule is `above`, ₹499 pays ₹50 and ₹500 is free. Record the literal-rule ambiguity in the ADR. |
| Returns | Exactly day 7 and day 8 after delivery | Day 7 is within the 7-day window if unopened and unused; day 8 is expired. |
| Returns | Opened item inside window | Ineligible with `ITEM_OPENED`. |
| Returns | Undelivered order | Not applicable yet; explain the next allowed action without promising a return. |
| Damage | 48 hours and 49 hours after delivery | 48 hours is within the reporting window; 49 hours is outside it. Photos are required and the agent cannot receive them. |
| COD | ₹2,500 and ₹2,501 | ₹2,500 is eligible because the limit is inclusive; ₹2,501 is blocked. |
| Cancellation | Processing versus Shipped/Out for Delivery | Processing can be cancelled; later statuses cannot and may mention refusing delivery. |
| Dates | Relative delivery dates | Use an injectable clock; never use a stale hard-coded calendar date. |
| IDs | Valid, missing, malformed, and unknown IDs | Normalize only recognized IDs; never guess; offer escalation after two failed attempts. |
