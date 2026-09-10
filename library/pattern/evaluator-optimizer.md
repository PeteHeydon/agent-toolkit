---
name: evaluator-optimizer
kind: pattern
summary: Draft, critique your own draft, revise. Bounded by max_cycles.
requires_capabilities: []
conflicts_with: []
schema_version: 1
---

1. Restate the task in one line and confirm you have the inputs it needs.
2. TODO: the work this agent does. Replace this step.
3. Review your own draft against the constraints above and name what is wrong
   with it. Be specific; "looks fine" is not a review.
4. Revise against that review. Repeat from step 3 at most {{MAX_CYCLES}} times,
   stopping early when a pass finds nothing worth changing.
5. Write the output per the contract above.
