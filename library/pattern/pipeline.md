---
name: pipeline
kind: pattern
summary: Fixed stages in order, each checked before it feeds the next.
requires_capabilities: []
conflicts_with: []
schema_version: 1
---

1. Restate the task in one line and confirm you have the inputs it needs.
2. Name the stages this task breaks into, in order, before starting any of them.
3. TODO: the work each stage does. Replace this step.
4. Run the stages in order, checking each stage's output before it becomes the
   next stage's input. A bad hand-off is cheaper to catch here than at the end.
5. Check the result against the constraints above and write the output per the
   contract above.
